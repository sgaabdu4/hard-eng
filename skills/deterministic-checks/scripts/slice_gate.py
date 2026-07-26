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
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HE_SCRIPTS = SCRIPT_DIR.parents[1] / "he" / "scripts"
if str(HE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(HE_SCRIPTS))

from safe_plan_io import SafePlanIOError, lifecycle_excluded, repo_root, repository_artifact

BOUNDED = SCRIPT_DIR / "bounded_run.py"
E2E_VALIDATOR = SCRIPT_DIR.parents[1] / "e2e" / "scripts" / "visual_evidence.py"
RECEIPT_VERSION = 1
CONTEXT = "hard-eng-slice-receipt:v1"
SLICE = re.compile(r"S-[1-9][0-9]*")
BEHAVIOR_SEPARATORS = re.compile(r"\s\+\s|;|\s→\s")
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
REACT_EXT = {".jsx", ".tsx"}
REACT_DEP = re.compile(r'"(react|react-dom|next)"\s*:')
PATTERNS = {
    "targeted": re.compile(r"\S"),
    "typecheck": re.compile(r"\btsc\b|typecheck|vue-tsc"),
    "lint": re.compile(r"eslint|oxlint|biome|\blint\b"),
    "tests": re.compile(r"vitest|jest|playwright|\btest\b"),
    "fallow": re.compile(r"\bfallow\b.*\baudit\b"),
    "react-doctor": re.compile(r"react-doctor"),
    "dart-analyze": re.compile(r"\b(dart|flutter)\s+analyze\b"),
    "dart-test": re.compile(r"\b(dart|flutter)\s+test\b"),
    "dart-decimate": re.compile(r"dart_decimate_gate\.py"),
}
JS_FAMILIES = ("typecheck", "lint", "tests", "fallow")
REACT_FAMILIES = ("react-doctor",)
DART_FAMILIES = ("dart-analyze", "dart-test", "dart-decimate")


class SliceGateError(ValueError):
    """Invalid slice-gate input, execution, or receipt."""


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=False, capture_output=True, timeout=30,
    )
    if result.returncode != 0:
        raise SliceGateError(
            f"git {args[0]} failed: {result.stderr.decode(errors='replace')[:200]}"
        )
    return result.stdout


def head_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
        check=False, capture_output=True, text=True, timeout=30,
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


def applicable_families(repo: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    families: set[str] = set()
    cache: dict[Path, bool] = {}
    for raw in paths:
        relative = Path(raw)
        suffix = relative.suffix.lower()
        if suffix in JS_EXT:
            families.update(JS_FAMILIES)
            if suffix in REACT_EXT or _react_package(repo, relative, cache):
                families.update(REACT_FAMILIES)
        if suffix == ".dart" or relative.name == "pubspec.yaml":
            families.update(DART_FAMILIES)
    return tuple(sorted(families)) if families else ("targeted",)


def coverage_error(applicable: tuple[str, ...], checks: list[tuple[str, str]]) -> str | None:
    for family, command in checks:
        if family not in PATTERNS:
            return f"unknown check family: {family}"
        if not PATTERNS[family].search(command):
            return f"command does not look like a {family} check: {command}"
    supplied = {family for family, _ in checks}
    missing = [family for family in applicable if family not in supplied]
    if missing:
        return "missing required check families: " + ", ".join(missing)
    if not checks:
        return "at least one targeted check is required"
    return None


def run_checks(
    repo: Path, checks: list[tuple[str, str]], timeout: float,
) -> list[dict[str, object]]:
    deadline = time.monotonic() + timeout
    results: list[dict[str, object]] = []
    for family, command in checks:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise SliceGateError("whole-run timeout exhausted before every check ran")
        completed = subprocess.run(
            [sys.executable, str(BOUNDED), "--timeout", str(max(1, int(remaining))),
             "--", "sh", "-c", command],
            cwd=repo, check=False,
        )
        results.append({"family": family, "command": command, "exit": completed.returncode})
    return results


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
            "--e2e must be a canonical $e2e receipt with validator PASS: "
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
        checks = [(str(check.get("family")), str(check.get("command"))) for check in raw_checks]
        applicable = tuple(str(item) for item in data.get("applicable", ()))
        if error := coverage_error(applicable, checks):
            return error
        current = applicable_families(repo, changed_paths(repo, full=name == "full"))
        uncovered = [family for family in current if family not in set(applicable)]
        if uncovered:
            return "receipt does not cover affected stacks: " + ", ".join(uncovered)
        for field in ("behavior", "e2e", "security", "review", "e2e_sha256"):
            if not str(data.get(field, "")).strip():
                return f"receipt is missing its {field} record"
        if error := security_error(plan, name, str(data.get("security", ""))):
            return error
        e2e_value = str(data.get("e2e", ""))
        try:
            if e2e_sha(repo, e2e_value) != data.get("e2e_sha256"):
                return "stale receipt: the recorded $e2e receipt changed after the checks ran"
        except OSError:
            return f"recorded $e2e receipt is missing or unreadable: {e2e_value}"
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


def parse_checks(raw: list[str]) -> list[tuple[str, str]]:
    checks: list[tuple[str, str]] = []
    for item in raw:
        if "=" not in item:
            raise SliceGateError("--check requires <family>=<command>")
        family, command = item.split("=", 1)
        if not command.strip():
            raise SliceGateError(f"--check {family} has an empty command")
        checks.append((family.strip(), command.strip()))
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
    applicable = applicable_families(repo, paths)
    if error := coverage_error(applicable, checks):
        raise SliceGateError(error)
    results = run_checks(repo, checks, args.timeout)
    failed = [entry for entry in results if entry["exit"] != 0]
    if failed:
        for entry in failed:
            print(f"failed_check={entry['family']} exit={entry['exit']}", file=sys.stderr)
        raise SliceGateError("checks failed; fix the owner and rerun the slice gate")
    payload.update({
        "artifact": repository_artifact(repo),
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
    run.add_argument("--check", action="append", default=[], metavar="FAMILY=COMMAND")
    run.add_argument("--e2e", required=True)
    run.add_argument("--security", required=True)
    run.add_argument("--review", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    try:
        {"run": command_run, "status": command_status}[args.command](args)
    except (OSError, subprocess.SubprocessError, SliceGateError, SafePlanIOError) as error:
        print(f"result=fail\nerror={error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
