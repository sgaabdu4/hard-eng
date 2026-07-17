#!/usr/bin/env python3
"""Run and bind final-convergence proof to the exact repository artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_DIR = SCRIPT_DIR.parents[1] / "he/scripts"
if str(STATE_DIR) not in sys.path:
    sys.path.insert(0, str(STATE_DIR))

from plan_approval import validate_approval_receipt  # noqa: E402
from plan_contract import (
    BUILD_AXES,
    SLUG,
    PlanStateError,
    parse_build_axes,
)  # noqa: E402
from plan_git import git_identity  # noqa: E402
from plan_state import canonical_plan, validate_document  # noqa: E402
from plan_transfer import git_location  # noqa: E402
from repository_snapshot import artifact_id, snapshot_id  # noqa: E402


RECEIPT_AXES = (
    "deterministic",
    "tests",
    "security",
    "ui-design",
    "e2e-runtime",
    "docs-context",
)
KINDS = {"full-matrix", "specialist", "focused"}
RECEIPT_KEYS = {
    "version",
    "plan_id",
    "plan_digest",
    "axis",
    "kind",
    "snapshot_id",
    "artifact_id",
    "command_digest",
    "elapsed_ms",
    "recorded_at_utc",
    "result",
}
SHA256 = "sha256:"
BOUNDED_RUN = SCRIPT_DIR.parents[1] / "deterministic-checks/scripts/bounded_run.py"


class BuildEvidenceError(ValueError):
    pass


def valid_utc(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return False
    return True


def command_digest(command: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for argument in command:
        encoded = argument.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return SHA256 + digest.hexdigest()


def receipt_path(root: Path, plan_id: str, axis: str) -> Path:
    return (
        git_location(root, "--git-common-dir")
        / "hard-eng/build-evidence"
        / plan_id
        / f"{axis}.json"
    )


def receipt_payload(
    plan_id: str,
    plan_digest: str,
    axis: str,
    kind: str,
    snapshot: str,
    artifact: str,
    command: Sequence[str],
    elapsed_ms: int,
) -> dict[str, object]:
    return {
        "version": 1,
        "plan_id": plan_id,
        "plan_digest": plan_digest,
        "axis": axis,
        "kind": kind,
        "snapshot_id": snapshot,
        "artifact_id": artifact,
        "command_digest": command_digest(command),
        "elapsed_ms": elapsed_ms,
        "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "result": "pass",
    }


def validate_receipt(receipt: object, plan_id: str, axis: str) -> dict[str, object]:
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS:
        raise BuildEvidenceError(f"BUILD_EVIDENCE_INVALID: axis={axis}; invalid keys")
    valid = (
        type(receipt["version"]) is int
        and receipt["version"] == 1
        and isinstance(receipt["plan_id"], str)
        and SLUG.fullmatch(receipt["plan_id"]) is not None
        and receipt["plan_id"] == plan_id
        and axis in RECEIPT_AXES
        and receipt["axis"] == axis
        and receipt["kind"] in KINDS
        and receipt["result"] == "pass"
        and type(receipt["elapsed_ms"]) is int
        and receipt["elapsed_ms"] >= 0
        and all(
            isinstance(receipt[key], str)
            and len(receipt[key]) == 71
            and receipt[key].startswith(SHA256)
            and all(character in "0123456789abcdef" for character in receipt[key][7:])
            for key in ("plan_digest", "snapshot_id", "artifact_id", "command_digest")
        )
        and valid_utc(receipt["recorded_at_utc"])
    )
    if not valid:
        raise BuildEvidenceError(
            f"BUILD_EVIDENCE_INVALID: axis={axis}; invalid receipt"
        )
    return receipt


def write_receipt(root: Path, receipt: dict[str, object]) -> None:
    axis = str(receipt.get("axis", ""))
    plan_id = str(receipt.get("plan_id", ""))
    validated = validate_receipt(receipt, plan_id, axis)
    destination = receipt_path(root, plan_id, axis)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(validated, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def load_receipt(root: Path, plan_id: str, axis: str) -> dict[str, object]:
    path = receipt_path(root, plan_id, axis)
    if path.is_symlink() or not path.is_file():
        raise BuildEvidenceError(
            f"BUILD_EVIDENCE_MISSING: axis={axis}; run build_evidence.py on the current artifact"
        )
    try:
        return validate_receipt(
            json.loads(path.read_text(encoding="utf-8")), plan_id, axis
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BuildEvidenceError(
            f"BUILD_EVIDENCE_INVALID: axis={axis}; unreadable receipt"
        ) from exc


def validate_current_build_evidence(
    root: Path,
    state: dict[str, str],
    snapshot: str,
    artifact: str,
) -> tuple[dict[str, object], ...]:
    axes = parse_build_axes(state["build_axes"])
    if axes is None:
        raise BuildEvidenceError("BUILD_EVIDENCE_INVALID: build axes are missing")
    validated: list[dict[str, object]] = []
    for axis in BUILD_AXES:
        if axis not in RECEIPT_AXES or axes[axis] != "pass":
            continue
        receipt = load_receipt(root, state["plan_id"], axis)
        if receipt["snapshot_id"] != snapshot or receipt["artifact_id"] != artifact:
            raise BuildEvidenceError(
                f"BUILD_EVIDENCE_STALE: axis={axis}; rerun current proof"
            )
        if receipt["plan_digest"] != state["approved_plan_digest"]:
            raise BuildEvidenceError(
                f"BUILD_EVIDENCE_STALE: axis={axis}; approved plan changed"
            )
        if receipt["kind"] == "focused" or (
            axis == "deterministic" and receipt["kind"] != "full-matrix"
        ):
            raise BuildEvidenceError(
                f"BUILD_EVIDENCE_FOCUSED_ONLY: axis={axis}; full convergence proof required"
            )
        validated.append(receipt)
    if axes["intent-spec"] != "pass" or axes["unknowns"] != "pass":
        raise BuildEvidenceError(
            "BUILD_EVIDENCE_INVALID: derived pre-review axis is incomplete"
        )
    return tuple(validated)


def build_evidence_provenance(receipts: Sequence[dict[str, object]]) -> str:
    lines = (
        "authority = parent-validated exact-current admission receipts",
        "older PLAN prose/history cannot negate these receipts",
    )
    return "\n".join((*lines, *(
        "receipt = " + "; ".join((
            f"snapshot_id={receipt['snapshot_id']}",
            f"artifact_id={receipt['artifact_id']}",
            f"approved_plan_digest={receipt['plan_digest']}",
            f"axis={receipt['axis']}",
            f"kind={receipt['kind']}",
            f"result={receipt['result']}",
        ))
        for receipt in receipts
    )))


def parse_axes(raw: str) -> tuple[str, ...]:
    axes = tuple(part.strip() for part in raw.split(",") if part.strip())
    if (
        not axes
        or len(axes) != len(set(axes))
        or any(axis not in RECEIPT_AXES for axis in axes)
    ):
        raise BuildEvidenceError("axes must be unique final-convergence evidence axes")
    if tuple(sorted(axes, key=BUILD_AXES.index)) != axes:
        raise BuildEvidenceError("axes must follow canonical build-axis order")
    return axes


def record(
    repo: Path,
    plan_arg: Path,
    axes: tuple[str, ...],
    kind: str,
    timeout: float,
    command: Sequence[str],
) -> dict[str, object]:
    try:
        root, _, _ = git_identity(repo.expanduser().resolve())
        plan = canonical_plan(plan_arg.expanduser(), root)
        plan_text = plan.read_text(encoding="utf-8")
        state = validate_document(plan, plan_text)
        validate_approval_receipt(root, state)
    except (
        OSError,
        UnicodeError,
        subprocess.CalledProcessError,
        PlanStateError,
    ) as exc:
        raise BuildEvidenceError(f"invalid PLAN state: {exc}") from exc
    if kind not in KINDS:
        raise BuildEvidenceError("invalid build evidence kind")
    if "deterministic" in axes and kind != "full-matrix":
        raise BuildEvidenceError(
            "deterministic final evidence requires kind=full-matrix"
        )
    if state["lifecycle_status"] != "building" or state["active_slice"] != "final":
        raise BuildEvidenceError("build evidence requires final convergence")
    snapshot = snapshot_id(root)
    artifact = artifact_id(root)
    if state["snapshot_id"] != snapshot or state["artifact_id"] != artifact:
        raise BuildEvidenceError("PLAN repository identity is stale")
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(BOUNDED_RUN), "--timeout", str(timeout), "--", *command],
        cwd=root,
        check=False,
    )
    elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
    if result.returncode != 0:
        raise BuildEvidenceError(
            f"BUILD_EVIDENCE_COMMAND_FAILED: exit={result.returncode}"
        )
    if plan.read_text(encoding="utf-8") != plan_text:
        raise BuildEvidenceError("BUILD_EVIDENCE_STALE: PLAN changed during proof")
    if snapshot_id(root) != snapshot or artifact_id(root) != artifact:
        raise BuildEvidenceError(
            "BUILD_EVIDENCE_STALE: repository changed during proof"
        )
    receipts = tuple(
        receipt_payload(
            state["plan_id"],
            state["approved_plan_digest"],
            axis,
            kind,
            snapshot,
            artifact,
            command,
            elapsed_ms,
        )
        for axis in axes
    )
    for receipt in receipts:
        write_receipt(root, receipt)
    return {
        "result": "recorded",
        "snapshot_id": snapshot,
        "artifact_id": artifact,
        "axes": list(axes),
        "kind": kind,
        "elapsed_ms": elapsed_ms,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--axes", required=True)
    parser.add_argument("--kind", choices=sorted(KINDS), required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if args.timeout <= 0 or not command:
        parser.error("positive --timeout and command after -- are required")
    try:
        result = record(
            Path(args.repo),
            Path(args.plan),
            parse_axes(args.axes),
            args.kind,
            args.timeout,
            command,
        )
    except BuildEvidenceError as exc:
        print(f"build-evidence: FAIL | {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
