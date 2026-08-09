#!/usr/bin/env python3
"""Deterministic slice/full-gate receipts bound to the exact repository artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HE_SCRIPTS = SCRIPT_DIR.parents[1] / "he" / "scripts"
for _path in (SCRIPT_DIR, HE_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from git_env import git_env
from project_gate import ProjectGateError, load_manifest, run_families
from source_tree_coordination import CoordinationError
from safe_plan_io import SafePlanIOError, lifecycle_excluded, repo_root, repository_artifact

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
BOUNDARY_SUFFIXES = JS_EXT | {
    ".dart", ".gql", ".graphql", ".json", ".proto", ".yaml", ".yml",
}
ZOD_RANGE_MAJOR = re.compile(r"(?<![\w.-])(\d+)(?=(?:\.\d+)*(?:\b|$))")
ZOD_VERSION = re.compile(r"^4(?:\.\d+){0,2}(?:[-+][0-9A-Za-z.-]+)?$")
JS_STACK_DEPENDENCIES = frozenset({
    "@types/react", "next", "react", "react-dom", "ts-node", "tsx", "typescript", "zod",
})


class SliceGateError(ValueError):
    """Invalid slice-gate input, execution, or receipt."""


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False, capture_output=True, timeout=30, env=git_env(),
    )
    if result.returncode != 0:
        raise SliceGateError(
            f"git {args[0]} failed: {result.stderr.decode(errors='replace')[:200]}"
        )
    return result.stdout


def head_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
        check=False, capture_output=True, text=True, timeout=30, env=git_env(),
    )
    return result.stdout.strip() if result.returncode == 0 else "none"


def changed_paths(repo: Path, *, full: bool) -> tuple[str, ...]:
    if full:
        names = _git(repo, "ls-files", "-c", "-o", "--exclude-standard", "-z").split(b"\0")
    else:
        tracked = (
            _git(repo, "diff", "--name-only", "-z", "HEAD", "--")
            if head_commit(repo) != "none" else _git(repo, "ls-files", "-c", "-z")
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
        raw = json.loads(
            (repo / "hard-eng.gates.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return False
    families = raw.get("families") if isinstance(raw, dict) else None
    return isinstance(families, dict) and BOUNDARY_FAMILY in families


def _zod_range_is_4(value: object) -> bool:
    if not isinstance(value, str):
        return False
    majors = [int(item) for item in ZOD_RANGE_MAJOR.findall(value)]
    return bool(majors) and all(major == 4 for major in majors)


def _zod_version_is_4(value: object) -> bool:
    return isinstance(value, str) and bool(ZOD_VERSION.fullmatch(value.strip()))


def _zod_dependency_error(repo: Path) -> str | None:
    manifest = repo / "package.json"
    if not manifest.is_file():
        return "marked TypeScript/React boundary project requires package.json with direct zod@4"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return f"package.json cannot prove direct zod@4: {error}"
    if not isinstance(data, dict):
        return "package.json cannot prove direct zod@4: expected an object"
    specs = []
    for section in ("dependencies", "devDependencies"):
        values = data.get(section)
        if isinstance(values, dict) and "zod" in values:
            specs.append(values["zod"])
    if not specs or not all(_zod_range_is_4(spec) for spec in specs):
        return "marked TypeScript/React boundary project requires a direct zod@4 dependency"
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


def _lockfile_zod_error(repo: Path) -> str | None:
    lockfiles = [
        repo / "package-lock.json",
        repo / "pnpm-lock.yaml",
        repo / "yarn.lock",
    ]
    present = [path for path in lockfiles if path.is_file()]
    if len(present) != 1:
        return (
            "marked TypeScript/React boundary project requires exactly one recognized "
            "lockfile with a Zod 4 entry"
        )
    lockfile = present[0]
    try:
        text = lockfile.read_text(encoding="utf-8")
    except OSError as error:
        return f"lockfile cannot prove Zod 4: {error}"
    if lockfile.name == "package-lock.json":
        try:
            version = _package_lock_zod_version(json.loads(text))
        except ValueError as error:
            return f"package-lock.json cannot prove Zod 4: {error}"
        if not _zod_version_is_4(version):
            return "package-lock.json must resolve direct zod to version 4.x"
        return None
    if lockfile.name == "pnpm-lock.yaml":
        found = re.search(
            r"(?m)^\s*(?:/)?zod@4(?:\.\d+){0,2}(?:[-+][^:\n]*)?:\s*$",
            text,
        )
    else:
        found = re.search(
            r"(?ms)^\s*\"?zod@[^:\n]+\"?:\s*\n"
            r"\s+version(?:\s+|:\s*)[\"']?4(?:\.\d+){0,2}\b",
            text,
        )
    if not found:
        return f"{lockfile.name} must resolve direct zod to version 4.x"
    return None


def _package_is_js_stack(repo: Path) -> bool:
    try:
        data = json.loads((repo / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        values = data.get(section)
        if isinstance(values, dict) and JS_STACK_DEPENDENCIES.intersection(values):
            return True
    return any(repo.glob("tsconfig*.json"))


def _typescript_boundary(repo: Path, paths: tuple[str, ...], applicable: tuple[str, ...]) -> bool:
    js_path = any(Path(raw).suffix.lower() in JS_EXT for raw in paths)
    if js_path or any(family in applicable for family in REACT_FAMILIES):
        return True
    if any(Path(raw).suffix.lower() == ".dart" for raw in paths):
        return False
    return _package_is_js_stack(repo)


def boundary_contract_error(
    repo: Path, paths: tuple[str, ...], applicable: tuple[str, ...]
) -> str | None:
    if BOUNDARY_FAMILY not in applicable or not _typescript_boundary(repo, paths, applicable):
        return None
    return _zod_dependency_error(repo) or _lockfile_zod_error(repo)


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
    for raw in paths:
        relative = Path(raw)
        suffix = relative.suffix.lower()
        if suffix in JS_EXT:
            families.update(JS_FAMILIES)
            if suffix in REACT_EXT or _react_package(repo, relative, cache):
                families.update(REACT_FAMILIES)
        if relative.name == "pubspec.yaml" or (
            suffix == ".dart" and _dart_package(repo, relative, dart_cache)
        ):
            families.update(DART_FAMILIES)
        if boundary_declared and suffix in BOUNDARY_SUFFIXES:
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
    return "sha256:" + hashlib.sha256(f"{CONTEXT}\0{canonical}".encode("utf-8")).hexdigest()


def receipt_file(plan: Path, name: str) -> Path:
    return plan.parent / "receipts" / f"{name}.json"


def plan_risk(plan: Path) -> tuple[str, str]:
    try:
        text = plan.read_text(encoding="utf-8")
    except OSError:
        return "standard", "none"
    level = re.search(r"(?m)^- risk_level = (.+)$", text)
    overlay = re.search(r"(?m)^- critical_overlay = (.+)$", text)
    return (
        level.group(1).strip() if level else "standard",
        overlay.group(1).strip() if overlay else "none",
    )


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
        return (
            f"critical overlay covers {name}: record the protected-boundary "
            "review summary instead of not-applicable"
        )
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
    result = subprocess.run(
        [sys.executable, str(E2E_VALIDATOR), "--receipt", str(path), "--repo", str(repo)],
        check=False, capture_output=True, text=True, timeout=900,
    )
    if result.returncode != 0:
        raise SliceGateError(
            "--e2e must be a canonical e2e receipt with validator PASS: "
            + (result.stdout.strip() or result.stderr.strip())[:300]
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
    if (
        len(relative.parts) != 3
        or relative.parts[0] != "features"
        or relative.parts[2] != "PLAN.md"
    ):
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
            plan, tuple(str(item) for item in data.get("changed_paths", ())),
            str(data.get("e2e", "")),
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
            raise SliceGateError(
                "--check accepts a family name only; commands come from hard-eng.gates.json"
            )
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
            "--behavior must state one observable behavior; split the additional "
            "behaviors into their own slices"
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
    payload.update({
        "artifact": artifact_before,
        "head": head_commit(repo),
        "e2e_sha256": e2e_sha(repo, e2e_value),
        "changed_paths": list(paths),
        "applicable": list(applicable),
        "checks": results,
    })
    payload["integrity"] = payload_hash(
        {key: value for key, value in payload.items() if key != "integrity"}
    )
    target.parent.mkdir(mode=0o755, exist_ok=True)
    temporary = target.parent / f".{target.name}.tmp"
    temporary.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(temporary, target)
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
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        {"run": command_run, "status": command_status}[args.command](args)
    except (
        OSError,
        subprocess.SubprocessError,
        CoordinationError,
        ProjectGateError,
        SliceGateError,
        SafePlanIOError,
    ) as error:
        print(f"result=fail\nerror={error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
