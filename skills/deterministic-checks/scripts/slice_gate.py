#!/usr/bin/env python3
"""Deterministic slice/full-gate receipts bound to the exact repository artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HE_SCRIPTS = SCRIPT_DIR.parents[1] / "he" / "scripts"
for _path in (SCRIPT_DIR, HE_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from bounded_run import run_captured
from execution_evidence import refresh_execution_state
from git_env import git_env
from project_gate import ProjectGateError, load_manifest, run_families
from safe_plan_io import SafePlanIOError, lifecycle_excluded, repo_root, repository_artifact
from source_tree_coordination import CoordinationError, atomic_json

E2E_VALIDATOR = SCRIPT_DIR.parents[1] / "e2e" / "scripts" / "visual_evidence.py"
RECEIPT_VERSION = 2
CONTEXT = "hard-eng-slice-receipt:v2"
SLICE = re.compile(r"S-[1-9][0-9]*")
BEHAVIOR_SEPARATORS = re.compile(r"\s\+\s|;|\s→\s")
UI_EXT = {".tsx", ".jsx", ".dart"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
REACT_EXT = {".jsx", ".tsx"}
REACT_DEP = re.compile(r'"(react|react-dom|next)"\s*:')
JS_FAMILIES = ("typecheck", "format", "lint", "tests", "fallow")
REACT_FAMILIES = ("react-doctor",)
DART_FAMILIES = ("dart-analyze", "dart-test", "dart-decimate")
BOUNDARY_FAMILY = "boundary-contracts"
BOUNDARY_SUFFIXES = JS_EXT | {".dart", ".gql", ".graphql", ".json", ".proto", ".yaml", ".yml"}
BOUNDARY_SCOPE_KEY = "boundary_contracts"
APPLICATION_ROOTS_KEY = "application_roots"
LOCAL_PACKAGE_ROOTS_KEY = "local_package_roots"
LOCKFILE_NAMES = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
EXTERNAL_PATH_PARTS = frozenset({"node_modules"})
SEMVER_HELPER = SCRIPT_DIR.parents[2] / "scripts" / "semver-contract.mjs"
JS_STACK_DEPENDENCIES = frozenset({"@types/react", "next", "react", "react-dom", "ts-node", "tsx", "typescript", "zod"})


class SliceGateError(ValueError):
    """Invalid slice-gate input, execution, or receipt."""


def _git(repo: Path, *args: str) -> bytes:
    result = run_captured(["git", "-C", str(repo), *args], 30, env=git_env())
    if result.returncode != 0:
        raise SliceGateError(f"git {args[0]} failed: {result.stderr.decode(errors='replace')[:200]}")
    return result.stdout


def head_commit(repo: Path) -> str:
    result = run_captured(["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"], 30, env=git_env())
    return result.stdout.decode("utf-8", "replace").strip() if result.returncode == 0 else "none"


def changed_paths(repo: Path, *, full: bool) -> tuple[str, ...]:
    if full:
        names = _git(repo, "ls-files", "-c", "-o", "--exclude-standard", "-z").split(b"\0")
    else:
        tracked = (
            _git(repo, "diff", "--name-only", "-z", "HEAD", "--")
            if head_commit(repo) != "none"
            else _git(repo, "ls-files", "-c", "-z")
        )
        untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z")
        names = tracked.split(b"\0") + untracked.split(b"\0")
    paths = sorted({os.fsdecode(name) for name in names if name})
    return tuple(path for path in paths if not lifecycle_excluded(Path(path)))


def _react_package(repo: Path, relative: Path, cache: dict[Path, bool]) -> bool:
    directory = (repo / relative).parent
    visited: list[Path] = []
    found = False
    while True:
        if directory in cache:
            found = cache[directory]
            break
        visited.append(directory)
        manifest = directory / "package.json"
        if manifest.is_file():
            try:
                found = bool(REACT_DEP.search(manifest.read_text(encoding="utf-8")))
            except OSError:
                found = False
            break
        if directory == repo or directory.parent == directory:
            break
        directory = directory.parent
    for entry in visited:
        cache[entry] = found
    return found


def _boundary_declared(repo: Path) -> bool:
    try:
        raw = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    families = raw.get("families") if isinstance(raw, dict) else None
    return isinstance(families, dict) and BOUNDARY_FAMILY in families


def _manifest_data(repo: Path) -> dict | None:
    try:
        raw = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return raw if isinstance(raw, dict) else None


def _scope_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    return Path(os.path.normpath(candidate.as_posix()))


def _boundary_scope_config(repo: Path) -> tuple[tuple[Path, ...], tuple[Path, ...], str | None]:
    data = _manifest_data(repo)
    if data is None:
        return (), (), "hard-eng.gates.json is missing or invalid"
    scope = data.get(BOUNDARY_SCOPE_KEY)
    if not isinstance(scope, dict):
        return (), (), "boundary_contracts requires application_roots"
    parsed: dict[str, tuple[Path, ...]] = {}
    for key in (APPLICATION_ROOTS_KEY, LOCAL_PACKAGE_ROOTS_KEY):
        values = scope.get(key, [])
        if not isinstance(values, list):
            return (), (), f"boundary_contracts.{key} must be an array"
        roots = tuple(_scope_path(value) for value in values)
        if any(root is None for root in roots):
            return (), (), f"boundary_contracts.{key} contains an invalid root"
        parsed[key] = tuple(root for root in roots if root is not None)
    if not parsed[APPLICATION_ROOTS_KEY]:
        return (), (), "boundary_contracts.application_roots must not be empty"
    all_roots = parsed[APPLICATION_ROOTS_KEY] + parsed[LOCAL_PACKAGE_ROOTS_KEY]
    if len(set(all_roots)) != len(all_roots):
        return (), (), "boundary_contracts roots must be unique"
    return (parsed[APPLICATION_ROOTS_KEY], parsed[LOCAL_PACKAGE_ROOTS_KEY], None)


def _under_root(relative: Path, root: Path) -> bool:
    try:
        relative.relative_to(root)
        return True
    except ValueError:
        return False


def _scope_root(
    relative: Path, application_roots: tuple[Path, ...], local_package_roots: tuple[Path, ...]
) -> Path | None:
    roots = application_roots + local_package_roots
    matches = [root for root in roots if _under_root(relative, root)]
    return max(matches, key=lambda root: len(root.parts)) if matches else None


def _external_path(relative: Path) -> bool:
    return bool(EXTERNAL_PATH_PARTS.intersection(relative.parts))


def _zod_range_is_4(value: object) -> bool:
    if not isinstance(value, str):
        return False
    result = run_captured(["node", str(SEMVER_HELPER), "range-major", value, "4"], 10)
    return result.returncode == 0


def _zod_version_is_4(value: object) -> bool:
    if not isinstance(value, str):
        return False
    result = run_captured(["node", str(SEMVER_HELPER), "stable-major", value, "4"], 10)
    return result.returncode == 0


def _package_manifest(repo: Path, package_root: Path) -> Path:
    return repo / package_root / "package.json"


def _zod_dependency_error(repo: Path, package_root: Path) -> str | None:
    manifest = _package_manifest(repo, package_root)
    scope = package_root.as_posix()
    if not manifest.is_file():
        return f"scoped TypeScript/React root {scope} requires package.json with direct zod@4"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return f"{scope}/package.json cannot prove direct zod@4: {error}"
    if not isinstance(data, dict):
        return f"{scope}/package.json cannot prove direct zod@4: expected an object"
    specs = []
    for section in ("dependencies", "devDependencies"):
        values = data.get(section)
        if isinstance(values, dict) and "zod" in values:
            specs.append(values["zod"])
    if not specs or not all(_zod_range_is_4(spec) for spec in specs):
        return f"scoped TypeScript/React root {scope} requires a direct zod@4 dependency"
    return None


def _package_lock_zod_version(data: object) -> object | None:
    if not isinstance(data, dict):
        return None
    packages = data.get("packages")
    if isinstance(packages, dict):
        package = packages.get("node_modules/zod")
        if isinstance(package, dict) and "version" in package:
            return package["version"]
    dependencies = data.get("dependencies")
    if isinstance(dependencies, dict):
        package = dependencies.get("zod")
        if isinstance(package, dict):
            return package.get("version")
    return None


def _lockfile_zod_error(repo: Path, package_root: Path) -> str | None:
    directories = []
    current = repo / package_root
    while True:
        directories.append(current)
        if current == repo:
            break
        current = current.parent
    present: list[Path] = []
    for directory in directories:
        present = [directory / name for name in LOCKFILE_NAMES if (directory / name).is_file()]
        if present:
            break
    scope = package_root.as_posix()
    if len(present) != 1:
        return f"scoped TypeScript/React root {scope} requires exactly one recognized lockfile with a Zod 4 entry"
    lockfile = present[0]
    try:
        text = lockfile.read_text(encoding="utf-8")
    except OSError as error:
        return f"{lockfile} cannot prove Zod 4: {error}"
    if lockfile.name == "package-lock.json":
        try:
            version = _package_lock_zod_version(json.loads(text))
        except ValueError as error:
            return f"{lockfile} cannot prove Zod 4: {error}"
        if not _zod_version_is_4(version):
            return f"{lockfile} must resolve direct zod to version 4.x"
        return None
    if lockfile.name == "pnpm-lock.yaml":
        match = re.search(r"(?m)^\s*(?:/)?zod@([^:\s]+):\s*$", text)
        version = match.group(1) if match else None
    else:
        match = re.search(
            r"(?ms)^\s*\"?zod@[^:\n]+\"?:\s*\n"
            r"\s+version(?:\s+|:\s*)[\"']?([^\"'\s]+)",
            text,
        )
        version = match.group(1) if match else None
    if not _zod_version_is_4(version):
        return f"{lockfile} must resolve direct zod to version 4.x"
    return None


def _package_is_js_stack(repo: Path, package_root: Path) -> bool:
    try:
        data = json.loads(_package_manifest(repo, package_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        values = data.get(section)
        if isinstance(values, dict) and JS_STACK_DEPENDENCIES.intersection(values):
            return True
    return any((repo / package_root).glob("tsconfig*.json"))


def _affected_scope_roots(
    repo: Path, paths: tuple[str, ...], application_roots: tuple[Path, ...], local_package_roots: tuple[Path, ...]
) -> tuple[Path, ...]:
    roots: set[Path] = set()
    for raw in paths:
        relative = Path(raw)
        if _external_path(relative):
            continue
        if (
            relative.name == "hard-eng.gates.json"
            or relative.as_posix() in LOCKFILE_NAMES
            or relative.as_posix() == "package.json"
        ):
            roots.update(application_roots)
            roots.update(local_package_roots)
            continue
        root = _scope_root(relative, application_roots, local_package_roots)
        if root is not None:
            roots.add(root)
    return tuple(sorted(roots, key=lambda root: root.as_posix()))


def _typescript_boundary(repo: Path, paths: tuple[str, ...], applicable: tuple[str, ...]) -> bool:
    js_path = any(Path(raw).suffix.lower() in JS_EXT for raw in paths)
    if js_path or any(family in applicable for family in REACT_FAMILIES):
        return True
    if any(Path(raw).suffix.lower() == ".dart" for raw in paths):
        return False
    application_roots, local_package_roots, _ = _boundary_scope_config(repo)
    return any(
        _package_is_js_stack(repo, root)
        for root in _affected_scope_roots(repo, paths, application_roots, local_package_roots)
    )


def boundary_contract_error(repo: Path, paths: tuple[str, ...], applicable: tuple[str, ...]) -> str | None:
    if BOUNDARY_FAMILY not in applicable:
        return None
    application_roots, local_package_roots, scope_error = _boundary_scope_config(repo)
    js_path = any(Path(raw).suffix.lower() in JS_EXT for raw in paths)
    if scope_error and js_path:
        return scope_error
    if not _typescript_boundary(repo, paths, applicable):
        return None
    roots = _affected_scope_roots(repo, paths, application_roots, local_package_roots)
    if not roots:
        return "TypeScript/React boundary changes must be under a declared application or local package root"
    for root in roots:
        if error := _zod_dependency_error(repo, root):
            return error
        if error := _lockfile_zod_error(repo, root):
            return error
    return None


def _dart_package(repo: Path, relative: Path, cache: dict[Path, bool]) -> bool:
    directory = (repo / relative).parent
    visited: list[Path] = []
    found = False
    while True:
        if directory in cache:
            found = cache[directory]
            break
        visited.append(directory)
        if (directory / "pubspec.yaml").is_file():
            found = True
            break
        if directory == repo or directory.parent == directory:
            break
        directory = directory.parent
    for entry in visited:
        cache[entry] = found
    return found


def applicable_families(repo: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    families: set[str] = set()
    cache: dict[Path, bool] = {}
    dart_cache: dict[Path, bool] = {}
    boundary_declared = _boundary_declared(repo)
    application_roots, local_package_roots, scope_error = _boundary_scope_config(repo)
    for raw in paths:
        relative = Path(raw)
        if _external_path(relative):
            continue
        suffix = relative.suffix.lower()
        if suffix in JS_EXT:
            families.update(JS_FAMILIES)
            if suffix in REACT_EXT or _react_package(repo, relative, cache):
                families.update(REACT_FAMILIES)
        if relative.name == "pubspec.yaml" or (suffix == ".dart" and _dart_package(repo, relative, dart_cache)):
            families.update(DART_FAMILIES)
        scoped = _scope_root(relative, application_roots, local_package_roots)
        control_file = (
            relative.name == "hard-eng.gates.json"
            or relative.as_posix() in LOCKFILE_NAMES
            or (relative.name == "package.json" and bool(application_roots))
        )
        boundary_relevant = (
            scope_error is not None or not application_roots or suffix == ".dart" or scoped is not None or control_file
        )
        if boundary_declared and suffix in BOUNDARY_SUFFIXES and boundary_relevant:
            families.add(BOUNDARY_FAMILY)
    return tuple(sorted(families)) if families else ("targeted",)


def coverage_error(applicable: tuple[str, ...], checks: list[str]) -> str | None:
    supplied = set(checks)
    missing = [family for family in applicable if family not in supplied]
    if missing:
        return "missing required check families: " + ", ".join(missing)
    if not checks:
        return "at least one targeted check is required"
    return None


def payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(f"{CONTEXT}\0{canonical}".encode()).hexdigest()


def receipt_file(plan: Path, name: str) -> Path:
    return plan.parent / "receipts" / f"{name}.json"


def plan_risk(plan: Path) -> tuple[str, str]:
    try:
        text = plan.read_text(encoding="utf-8")
    except OSError:
        return "standard", "none"
    level = re.search(r"(?m)^- risk_level = (.+)$", text)
    overlay = re.search(r"(?m)^- critical_overlay = (.+)$", text)
    return (level.group(1).strip() if level else "standard", overlay.group(1).strip() if overlay else "none")


def security_required(plan: Path, name: str) -> bool:
    level, overlay = plan_risk(plan)
    if level != "critical":
        return False
    if name == "full":
        return True
    named = SLICE.findall(overlay)
    return not named or name in named


def security_error(plan: Path, name: str, value: str) -> str | None:
    if value.startswith("not-applicable:") and security_required(plan, name):
        return f"critical overlay covers {name}: record the protected-boundary review summary instead of not-applicable"
    return None


def media_error(plan: Path, paths: tuple[str, ...], e2e_value: str) -> str | None:
    if not e2e_value.startswith("not-applicable:"):
        return None
    try:
        text = plan.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"(?m)^- ux_reference = (.+)$", text)
    ux = match.group(1).strip() if match else "n/a"
    if ux in {"n/a", "TBD"}:
        return None
    if any(Path(path).suffix.lower() in UI_EXT for path in paths):
        return (
            "ux_reference is set and this slice changes UI files: provide an "
            "actual-media e2e receipt instead of --e2e not-applicable"
        )
    return None


def e2e_sha(repo: Path, value: str) -> str:
    if value.startswith("not-applicable:"):
        return "none"
    path = Path(value) if Path(value).is_absolute() else repo / value
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def validate_e2e_receipt(repo: Path, value: str) -> None:
    if value.startswith("not-applicable:"):
        return
    path = Path(value) if Path(value).is_absolute() else repo / value
    result = run_captured([sys.executable, str(E2E_VALIDATOR), "--receipt", str(path), "--repo", str(repo)], 900)
    if result.returncode != 0:
        raise SliceGateError(
            "--e2e must be a canonical e2e receipt with validator PASS: "
            + (result.stdout.decode("utf-8", "replace").strip() or result.stderr.decode("utf-8", "replace").strip())[
                :300
            ]
        )


def plan_info(repo: Path, value: str) -> tuple[Path, str]:
    plan = Path(value)
    if not plan.is_absolute():
        plan = repo / plan
    plan = Path(os.path.abspath(plan))
    try:
        relative = plan.relative_to(repo)
    except ValueError as error:
        raise SliceGateError("PLAN must be inside the repository") from error
    if len(relative.parts) != 3 or relative.parts[0] != "features" or relative.parts[2] != "PLAN.md":
        raise SliceGateError("PLAN path must be features/<feature-slug>/PLAN.md")
    try:
        text = plan.read_text(encoding="utf-8")
    except OSError as error:
        raise SliceGateError(f"PLAN is unreadable: {error}") from error
    match = re.search(r"(?m)^- plan_id = (\S+)$", text)
    if not match:
        raise SliceGateError("PLAN has no plan_id row")
    return plan, match.group(1)


def load_receipt(path: Path) -> dict:
    if not path.is_file():
        raise SliceGateError(f"receipt missing: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise SliceGateError(f"receipt unreadable: {path}: {error}") from error
    if not isinstance(data, dict):
        raise SliceGateError(f"receipt malformed: {path}")
    integrity = data.pop("integrity", None)
    if data.get("receipt_version") != RECEIPT_VERSION:
        raise SliceGateError(f"unsupported receipt version: {path}")
    if integrity != payload_hash(data):
        raise SliceGateError(f"receipt integrity mismatch: {path}")
    return data


def receipt_error(repo: Path, plan: Path, plan_id: str, name: str) -> str | None:
    try:
        data = load_receipt(receipt_file(plan, name))
        expected_kind = "full" if name == "full" else "slice"
        if data.get("kind") != expected_kind or data.get("slice") != name:
            return f"receipt identity does not match {name}"
        if data.get("plan_id") != plan_id:
            return f"receipt belongs to another plan: {data.get('plan_id')}"
        if data.get("artifact") != repository_artifact(repo):
            return f"stale receipt: repository changed after the {name} checks ran"
        if data.get("head") != head_commit(repo):
            return f"stale receipt: HEAD changed after the {name} checks ran"
        raw_checks = data.get("checks", ())
        if not isinstance(raw_checks, list) or any(
            not isinstance(check, dict) or check.get("exit") != 0 for check in raw_checks
        ):
            return "receipt contains failed or malformed checks"
        checks = [str(check.get("family")) for check in raw_checks]
        applicable = tuple(str(item) for item in data.get("applicable", ()))
        if error := coverage_error(applicable, checks):
            return error
        commands = load_manifest(repo)
        for check in raw_checks:
            family = str(check.get("family"))
            if family not in commands or check.get("command") != list(commands[family]):
                return f"receipt command no longer matches {family} in hard-eng.gates.json"
        current_paths = changed_paths(repo, full=name == "full")
        current = applicable_families(repo, current_paths)
        uncovered = [family for family in current if family not in set(applicable)]
        if uncovered:
            return "receipt does not cover affected stacks: " + ", ".join(uncovered)
        if error := boundary_contract_error(repo, current_paths, current):
            return error
        for field in ("behavior", "e2e", "security", "review", "e2e_sha256"):
            if not str(data.get(field, "")).strip():
                return f"receipt is missing its {field} record"
        if error := security_error(plan, name, str(data.get("security", ""))):
            return error
        if error := media_error(
            plan, tuple(str(item) for item in data.get("changed_paths", ())), str(data.get("e2e", ""))
        ):
            return error
        e2e_value = str(data.get("e2e", ""))
        try:
            if e2e_sha(repo, e2e_value) != data.get("e2e_sha256"):
                return "stale receipt: the recorded e2e receipt changed after the checks ran"
        except OSError:
            return f"recorded e2e receipt is missing or unreadable: {e2e_value}"
        return None
    except (SliceGateError, SafePlanIOError) as error:
        return str(error).replace("\n", " ")


def receipt_status(repo: Path, plan: Path, plan_id: str, name: str) -> str:
    if not receipt_file(plan, name).is_file():
        return "missing"
    error = receipt_error(repo, plan, plan_id, name)
    return "current" if error is None else f"stale ({error})"


def checkpoint_error(repo: Path, plan: Path, plan_id: str, name: str) -> str | None:
    error = receipt_error(repo, plan, plan_id, name)
    if error is None:
        return None
    scope = "full pre-ship gate" if name == "full" else f"slice {name} completion"
    return (
        f"{scope} requires a current slice-gate receipt ({error}); run "
        "skills/deterministic-checks/scripts/slice_gate.py run on the final tree first"
    )


def parse_checks(raw: list[str]) -> list[str]:
    checks: list[str] = []
    for family in raw:
        family = family.strip()
        if not family or "=" in family:
            raise SliceGateError("--check accepts a family name only; commands come from hard-eng.gates.json")
        if family in checks:
            raise SliceGateError(f"duplicate --check family: {family}")
        checks.append(family)
    return checks


def evidence_value(label: str, value: str, repo: Path) -> str:
    value = value.strip()
    if not value:
        raise SliceGateError(f"--{label} requires a value")
    if value.startswith("not-applicable:"):
        if not value.split(":", 1)[1].strip():
            raise SliceGateError(f"--{label} not-applicable requires a reason")
        return value
    if label == "e2e":
        media = Path(value) if Path(value).is_absolute() else repo / value
        if not media.is_file():
            raise SliceGateError(f"--e2e receipt file does not exist: {value}")
    return value


def command_run(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    plan, plan_id = plan_info(repo, args.plan)
    name = "full" if args.full else args.slice
    if name != "full" and not SLICE.fullmatch(name or ""):
        raise SliceGateError("--slice must be S-N, or pass --full")
    target = receipt_file(plan, name)
    target.unlink(missing_ok=True)
    checks = parse_checks(args.check)
    behavior = (args.behavior or ("full repository gate" if name == "full" else "")).strip()
    if not behavior:
        raise SliceGateError("--behavior must state the one demonstrated observable behavior")
    if name != "full" and BEHAVIOR_SEPARATORS.search(behavior):
        raise SliceGateError(
            "--behavior must state one observable behavior; split the additional behaviors into their own slices"
        )
    security = evidence_value("security", args.security, repo)
    if error := security_error(plan, name, security):
        raise SliceGateError(error)
    e2e_value = evidence_value("e2e", args.e2e, repo)
    validate_e2e_receipt(repo, e2e_value)
    payload = {
        "receipt_version": RECEIPT_VERSION,
        "kind": "full" if name == "full" else "slice",
        "plan_id": plan_id,
        "slice": name,
        "behavior": behavior,
        "e2e": e2e_value,
        "security": security,
        "review": evidence_value("review", args.review, repo),
    }
    paths = changed_paths(repo, full=name == "full")
    if error := media_error(plan, paths, e2e_value):
        raise SliceGateError(error)
    applicable = applicable_families(repo, paths)
    if error := coverage_error(applicable, checks):
        raise SliceGateError(error)
    if error := boundary_contract_error(repo, paths, applicable):
        raise SliceGateError(error)
    artifact_before = repository_artifact(repo)
    results = run_families(repo, checks, args.timeout)
    failed = [entry for entry in results if entry["exit"] != 0]
    if failed:
        for entry in failed:
            print(f"failed_check={entry['family']} exit={entry['exit']}", file=sys.stderr)
        raise SliceGateError("checks failed; fix the owner and rerun the slice gate")
    if repository_artifact(repo) != artifact_before:
        raise SliceGateError(
            "checks mutated the repository tree; gate checks are read-only — "
            "capture media/codegen before the gate, then rerun"
        )
    payload.update(
        {
            "artifact": artifact_before,
            "head": head_commit(repo),
            "e2e_sha256": e2e_sha(repo, e2e_value),
            "changed_paths": list(paths),
            "applicable": list(applicable),
            "checks": results,
        }
    )
    payload["integrity"] = payload_hash({key: value for key, value in payload.items() if key != "integrity"})
    target.parent.mkdir(mode=0o755, exist_ok=True)
    atomic_json(target, payload)
    fingerprints = re.findall(r"(?m)^- approval_fingerprint = (sha256:[0-9a-f]{64})$", plan.read_text(encoding="utf-8"))
    if len(fingerprints) != 1:
        raise SliceGateError("approved plan requires exactly one fingerprint")
    refresh_execution_state(
        repo,
        plan,
        fingerprints[0],
        args.session_id or os.environ.get("HARD_ENG_SESSION_ID", ""),
        args.request_digest or os.environ.get("HARD_ENG_REQUEST_DIGEST", ""),
    )
    print("result=pass")
    print(f"receipt={target}")
    print(f"artifact={payload['artifact']}")
    print(f"applicable={','.join(applicable)}")
    print(f"checks={len(results)}")


def command_status(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    plan, plan_id = plan_info(repo, args.plan)
    name = "full" if args.full else args.slice
    if name != "full" and not SLICE.fullmatch(name or ""):
        raise SliceGateError("--slice must be S-N, or pass --full")
    print(f"receipt_status={receipt_status(repo, plan, plan_id, name)}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for command_name in ("run", "status"):
        command = commands.add_parser(command_name)
        command.add_argument("--repo", required=True)
        command.add_argument("--plan", required=True)
        command.add_argument("--slice")
        command.add_argument("--full", action="store_true")
    run = commands.choices["run"]
    run.add_argument("--timeout", type=float, required=True)
    run.add_argument("--behavior")
    run.add_argument("--check", action="append", default=[], metavar="FAMILY")
    run.add_argument("--e2e", required=True)
    run.add_argument("--security", required=True)
    run.add_argument("--review", required=True)
    run.add_argument("--session-id")
    run.add_argument("--request-digest")
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        {"run": command_run, "status": command_status}[args.command](args)
    except (OSError, CoordinationError, ProjectGateError, SliceGateError, SafePlanIOError) as error:
        print(f"result=fail\nerror={error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
