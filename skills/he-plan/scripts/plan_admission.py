#!/usr/bin/env python3
"""Validate executable planning evidence before Hard Eng approval."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[2] / "he" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from plan_contract import PlanStateError  # noqa: E402


TRACE_HEADER = (
    "ID", "Requirement", "Flow/state", "Contract/owner", "Proof",
    "Telemetry/rollout", "Slice",
)
FAILURE_HEADER = (
    "ID", "Boundary/transition", "Failure/interrupt", "Durable state",
    "Recovery owner", "Retry/timeout", "Observable proof",
)
CHALLENGE_HEADER = ("Perspective", "Scope", "Result", "Evidence")
PLACEHOLDER = re.compile(r"^(?:tbd|todo|pending|unknown|none|n/?a|[-?])$", re.IGNORECASE)
REFERENCE = {
    "requirement": re.compile(r"\bR-[1-9][0-9]*\b"),
    "flow": re.compile(r"\bF-[1-9][0-9]*\b"),
    "contract": re.compile(r"\bC-[1-9][0-9]*\b"),
    "proof": re.compile(r"\bT-[1-9][0-9]*\b"),
    "slice": re.compile(r"\bS-[1-9][0-9]*\b"),
}
RECEIPT = re.compile(r"^sha256:[0-9a-f]{64}$")


def _section(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    matches = [index for index, line in enumerate(lines) if line.strip() == heading]
    if len(matches) != 1:
        raise PlanStateError(f"PLAN requires exactly one {heading} section")
    start = matches[0] + 1
    end = next(
        (index for index in range(start, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    return lines[start:end]


def _table(text: str, heading: str, header: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    table = [line.strip() for line in _section(text, heading) if line.strip().startswith("|")]
    if len(table) < 3:
        raise PlanStateError(f"{heading} requires a populated table")

    def cells(line: str) -> tuple[str, ...]:
        return tuple(cell.strip() for cell in line.strip("|").split("|"))

    if cells(table[0]) != header or len(cells(table[1])) != len(header):
        raise PlanStateError(f"{heading} table header is invalid")
    rows = tuple(cells(line) for line in table[2:])
    if any(len(row) != len(header) for row in rows):
        raise PlanStateError(f"{heading} table row width is invalid")
    return rows


def _concrete(value: str, label: str) -> None:
    if not value.strip() or PLACEHOLDER.fullmatch(value.strip()):
        raise PlanStateError(f"plan admission has unresolved {label}")


def _risk_tier(text: str) -> str:
    values = [
        line.split("=", 1)[1].strip()
        for line in _section(text, "## Audit policy")
        if line.strip().startswith("- risk_tier =") and "=" in line
    ]
    if len(values) != 1 or values[0] not in {"standard", "critical"}:
        raise PlanStateError("Audit policy requires one risk_tier = standard|critical")
    return values[0]


def _references(value: str, kind: str) -> set[str]:
    return set(REFERENCE[kind].findall(value))


def validate_plan_admission(text: str) -> None:
    risk_tier = _risk_tier(text)
    traces = _table(text, "## Traceability", TRACE_HEADER)
    failures = _table(text, "## Failure Model", FAILURE_HEADER)
    challenges = _table(text, "## Plan challenge", CHALLENGE_HEADER)

    trace_ids: set[str] = set()
    requirement_refs: set[str] = set()
    flow_refs: set[str] = set()
    contract_refs: set[str] = set()
    proof_refs: set[str] = set()
    slice_refs: set[str] = set()
    for row in traces:
        trace_id, requirement, flow, contract, proof, telemetry, slice_ref = row
        if not re.fullmatch(r"TR-[1-9][0-9]*", trace_id) or trace_id in trace_ids:
            raise PlanStateError("Traceability requires unique ordered-style TR-* IDs")
        trace_ids.add(trace_id)
        for value, label in zip(row[1:], TRACE_HEADER[1:]):
            _concrete(value, f"traceability {trace_id} {label}")
        required = {
            "requirement": requirement, "flow": flow, "contract": contract,
            "proof": proof, "slice": slice_ref,
        }
        for kind, value in required.items():
            if not _references(value, kind):
                raise PlanStateError(f"traceability {trace_id} lacks {kind} ID")
        requirement_refs.update(_references(requirement, "requirement"))
        flow_refs.update(_references(flow, "flow"))
        contract_refs.update(_references(contract, "contract"))
        proof_refs.update(_references(proof, "proof"))
        slice_refs.update(_references(slice_ref, "slice"))

    owner_sections = {
        "requirement": (requirement_refs, "## Feature"),
        "flow": (flow_refs, "## Flows"),
        "contract": (contract_refs, "## Contracts"),
        "proof": (proof_refs, "## Testing"),
        "slice": (slice_refs, "## Slices"),
    }
    for kind, (references, heading) in owner_sections.items():
        owned = set(REFERENCE[kind].findall("\n".join(_section(text, heading))))
        if not references or not references.issubset(owned):
            raise PlanStateError(f"Traceability references a missing {heading} {kind} ID")

    concrete_failures = 0
    failure_ids: set[str] = set()
    for row in failures:
        failure_id = row[0]
        if failure_id == "FM-NA":
            if len(failures) != 1 or risk_tier == "critical":
                raise PlanStateError("critical or mixed Failure Model cannot use FM-NA")
            for value, label in zip(row[1:], FAILURE_HEADER[1:]):
                _concrete(value, f"FM-NA {label}")
            continue
        if not re.fullmatch(r"FM-[1-9][0-9]*", failure_id) or failure_id in failure_ids:
            raise PlanStateError("Failure Model requires unique FM-* IDs")
        failure_ids.add(failure_id)
        concrete_failures += 1
        for value, label in zip(row[1:], FAILURE_HEADER[1:]):
            _concrete(value, f"failure {failure_id} {label}")
        boundary_contracts = _references(row[1], "contract")
        failure_proofs = _references(row[6], "proof")
        if not boundary_contracts or not boundary_contracts.issubset(contract_refs):
            raise PlanStateError(f"failure {failure_id} lacks traced contract ID")
        if not failure_proofs or not failure_proofs.issubset(proof_refs):
            raise PlanStateError(f"failure {failure_id} lacks traced proof ID")
    if risk_tier == "critical" and concrete_failures == 0:
        raise PlanStateError("critical plan requires a concrete Failure Model")

    expected = {"complete"} if risk_tier == "standard" else {"owner-first", "boundary-first"}
    perspectives: set[str] = set()
    for perspective, scope, result, evidence in challenges:
        if perspective in perspectives:
            raise PlanStateError("Plan challenge has duplicate perspective")
        perspectives.add(perspective)
        _concrete(scope, f"Plan challenge {perspective} scope")
        if result != "PASS" or not RECEIPT.fullmatch(evidence):
            raise PlanStateError("Plan challenge requires PASS plus sha256 evidence")
    if perspectives != expected:
        raise PlanStateError(f"{risk_tier} Plan challenge perspectives are incomplete")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    try:
        validate_plan_admission(Path(args.plan).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, PlanStateError) as exc:
        print(f"plan-admission: FAIL | {exc}", file=sys.stderr)
        return 1
    print("plan-admission: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
