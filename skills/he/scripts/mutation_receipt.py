#!/usr/bin/env python3
"""Pre-ship mutation receipt: runner, scope = files changed since the approval base, totals, one row per survivor."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"), str(SCRIPT_DIR)]

import bounded_run
from evidence_lib import (
    EvidenceError,
    enforcement_configured,
    load_receipt,
    plan_id,
    receipt_path,
    safe_receipt_json,
    utc_now,
    utc_text,
)
from git_env import git_env
from safe_plan_io import SafePlanIOError, lifecycle_excluded, repository_artifact

RECEIPT_NAME = "mutation.json"
SCHEMA_VERSION = 1
RUNNERS = {"stryker": {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}, "mutmut": {".py"}}
NO_RUNNER_SUFFIXES = {".dart"}
MUTABLE_SUFFIXES = set().union(*RUNNERS.values()) | NO_RUNNER_SUFFIXES
TOTALS = ("killed", "survived", "timeout", "no_coverage")
DISPOSITIONS = ("fixed", "equivalent", "invalid", "deferred")
TEST_FILE = re.compile(
    r"(^|/)(tests?|__tests__|spec)/|([-_]regression(_check)?|_test|\.test|\.spec|[-_]contract(-check)?|[-_]contracts?)\."
)


class MutationError(Exception):
    """Invalid mutation receipt or payload."""


def _text(payload: dict[str, object], key: str, label: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MutationError(f"{label}.{key} must be a nonempty string")
    return value.strip()


def _slice_receipt_paths(repo: Path, plan: Path) -> set[str]:
    paths: set[str] = set()
    for receipt in sorted((plan.parent / "receipts").glob("S-*.json")):
        if not re.fullmatch(r"S-[1-9][0-9]*\.json", receipt.name):
            continue
        try:
            data, _, _ = load_receipt(repo, plan, receipt.name)
        except EvidenceError as error:
            raise MutationError(str(error)) from error
        recorded = data.get("changed_paths")
        if not isinstance(recorded, list):
            raise MutationError(f"slice receipt {receipt.name} has no changed_paths")
        paths.update(str(item) for item in recorded)
    return paths


def _git_names(repo: Path, *args: str) -> list[str]:
    result = bounded_run.run_captured(["git", args[0], "-z", *args[1:]], 60, cwd=str(repo), env=git_env())
    if result.returncode != 0:
        raise MutationError("cannot list changed files: " + result.stderr.decode(errors="replace")[:200])
    return [os.fsdecode(raw) for raw in result.stdout.split(b"\0") if raw]


def changed_source_files(repo: Path, plan: Path) -> tuple[str, ...]:
    """Files this feature changed: every slice receipt's changed paths plus the current uncommitted work."""
    names = _slice_receipt_paths(repo, plan)
    names.update(_git_names(repo, "diff", "--name-only", "HEAD", "--"))
    names.update(_git_names(repo, "ls-files", "--others", "--exclude-standard"))
    files: set[str] = set()
    for name in names:
        relative = Path(name)
        if lifecycle_excluded(relative) or relative.suffix not in MUTABLE_SUFFIXES:
            continue
        if TEST_FILE.search(relative.as_posix()) or not (repo / relative).is_file():
            continue
        files.add(relative.as_posix())
    return tuple(sorted(files))


def _survivors(payload: dict[str, object]) -> list[dict[str, str]]:
    rows = payload.get("survivors")
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise MutationError("survivors must be a list of objects")
    ledger: list[dict[str, str]] = []
    for index, row in enumerate(rows, start=1):
        label = f"survivor {index}"
        disposition = _text(row, "disposition", label)
        if disposition not in DISPOSITIONS:
            raise MutationError(f"{label} disposition must be one of {', '.join(DISPOSITIONS)}")
        entry = {
            "mutant": _text(row, "mutant", label),
            "disposition": disposition,
            "reason": _text(row, "reason", label),
        }
        if disposition == "deferred":
            entry["consequence"] = _text(row, "consequence", label)
        ledger.append(entry)
    return ledger


def _other_runners(paths: list[str]) -> str:
    names = sorted({name for name, suffixes in RUNNERS.items() if any(Path(p).suffix in suffixes for p in paths)})
    return ", ".join(names) or "no runner"


def validate(repo: Path, plan: Path, payload: dict[str, object]) -> dict[str, object]:
    allowed = ("runner", "version", "argv", "scope", "totals", "survivors", "sensitivity_proof")
    extra = sorted(key for key in payload if key not in allowed)
    if extra:
        raise MutationError(f"mutation payload has unknown keys: {', '.join(extra)}")
    runner = _text(payload, "runner", "mutation")
    if runner not in RUNNERS and runner != "none":
        raise MutationError(f"runner must be one of {', '.join(RUNNERS)} or none")
    scope = payload.get("scope")
    if not isinstance(scope, list) or any(not isinstance(item, str) or not item for item in scope):
        raise MutationError("scope must be a list of repository paths")
    required = changed_source_files(repo, plan)
    runnable = [path for path in required if Path(path).suffix not in NO_RUNNER_SUFFIXES]
    entry: dict[str, object] = {"runner": runner, "scope": sorted(set(scope)), "required_scope": list(required)}
    if runner == "none":
        wrong = [path for path in scope if Path(path).suffix not in NO_RUNNER_SUFFIXES]
        if wrong:
            raise MutationError(f"runner none covers only Dart files; {wrong[0]} needs a runner")
        missing = [path for path in required if path not in runnable and path not in scope]
        if missing:
            raise MutationError(f"scope omits a file this feature changed: {missing[0]}")
        entry["sensitivity_proof"] = _text(payload, "sensitivity_proof", "mutation")
        entry["totals"] = dict.fromkeys(TOTALS, 0)
        entry["survivors"] = []
        return entry
    mine = [path for path in runnable if Path(path).suffix in RUNNERS[runner]]
    if not mine:
        raise MutationError(f"{runner} has nothing to mutate; changed files need {_other_runners(runnable)}")
    missing = [path for path in mine if path not in scope]
    if missing:
        raise MutationError(f"scope omits a file this feature changed: {missing[0]}")
    wrong = [path for path in scope if Path(path).suffix not in RUNNERS[runner]]
    if wrong:
        raise MutationError(f"{runner} cannot mutate {wrong[0]}; record one receipt per runner")
    argv = payload.get("argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise MutationError("argv must be the exact runner command as a nonempty list of strings")
    totals = payload.get("totals")
    if not isinstance(totals, dict) or any(not isinstance(totals.get(key), int) or totals[key] < 0 for key in TOTALS):
        raise MutationError(f"totals must carry non-negative integers for {', '.join(TOTALS)}")
    survivors = _survivors(payload)
    if totals["survived"] != len(survivors):
        raise MutationError(f"totals.survived={totals['survived']} but the ledger has {len(survivors)} rows")
    if sum(totals[key] for key in TOTALS) == 0:
        raise MutationError("a completed run mutates at least one thing; totals are all zero")
    entry.update(
        {
            "version": _text(payload, "version", "mutation"),
            "argv": list(argv),
            "totals": {key: totals[key] for key in TOTALS},
            "survivors": survivors,
        }
    )
    return entry


def load(repo: Path, plan: Path) -> dict[str, object] | None:
    path = receipt_path(plan, RECEIPT_NAME)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value, _, _ = load_receipt(repo, plan, RECEIPT_NAME)
    except EvidenceError as error:
        raise MutationError(str(error)) from error
    if value.get("schema_version") != SCHEMA_VERSION or value.get("plan_id") != plan_id(plan):
        raise MutationError("mutation receipt does not belong to this Feature Brief")
    return value


def record(repo: Path, plan: Path, payload: dict[str, object]) -> dict[str, object]:
    entry = validate(repo, plan, payload)
    existing = load(repo, plan) or {"schema_version": SCHEMA_VERSION, "plan_id": plan_id(plan), "runs": []}
    runs = existing.get("runs")
    runs = [run for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []
    try:
        artifact = repository_artifact(repo)
    except SafePlanIOError as error:
        raise MutationError(str(error)) from error
    entry["recorded_at"] = utc_text(utc_now())
    entry["artifact"] = artifact
    runs = [run for run in runs if run.get("artifact") == artifact and run.get("runner") != entry["runner"]]
    existing["runs"] = [*runs, entry]
    path = receipt_path(plan, RECEIPT_NAME)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        safe_receipt_json(repo, path, existing)
    except EvidenceError as error:
        raise MutationError(str(error)) from error
    return entry


def ship_error(repo: Path, plan: Path, artifact: str) -> str | None:
    if not enforcement_configured(repo):
        return None
    try:
        receipt = load(repo, plan)
        required = changed_source_files(repo, plan)
    except (MutationError, EvidenceError) as error:
        return str(error).replace("\n", " ")
    runs = receipt.get("runs") if isinstance(receipt, dict) else None
    rows = [run for run in runs if isinstance(run, dict)] if isinstance(runs, list) else []
    current = [run for run in rows if run.get("artifact") == artifact]
    if not current:
        return "ship requires a mutation receipt for the green tree (plan_state.py record-mutation)"
    covered: set[str] = set()
    for run in current:
        scope = run.get("scope")
        if isinstance(scope, list):
            covered.update(str(item) for item in scope)
    uncovered = [path for path in required if path not in covered]
    if uncovered:
        return f"mutation receipt does not cover {uncovered[0]}; rerun record-mutation for the green tree"
    return None


def emit_lines(repo: Path, plan: Path, artifact: str) -> list[str]:
    if not enforcement_configured(repo):
        return []
    error = ship_error(repo, plan, artifact)
    return ["mutation=current"] if error is None else [f"mutation=missing ({error})"]
