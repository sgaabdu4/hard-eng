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
    "ID", "Requirement", "Decision", "Flow/state", "Contract/owner",
    "Proof", "Telemetry/rollout", "Slice",
)
DECISION_HEADER = (
    "ID", "Decision/default", "Alternatives", "Selected behavior", "Authority",
    "Evidence", "Consequences/revisit",
)
FAILURE_HEADER = (
    "ID", "Boundary/transition", "Failure/interrupt", "Durable state",
    "Recovery owner", "Retry/timeout", "Observable proof",
)
CHALLENGE_HEADER = ("Perspective", "Scope", "Result", "Evidence")
GUARANTEE_HEADER = ("ID", "Type", "Contract", "Trace")
GUARANTEE_COMMON = {"owner", "authority", "authority_ref", "evidence"}
GUARANTEE_SCHEMAS = {
    "membership": GUARANTEE_COMMON | {
        "snapshot", "capture", "high_water", "order", "query_index", "completion",
    },
    "identity-access": GUARANTEE_COMMON | {
        "permission", "enumeration", "cursor", "completeness", "order",
        "credential_match", "expiry", "incomplete",
    },
    "exhaustive": GUARANTEE_COMMON | {
        "inventory", "partition", "query_index", "cursor", "orphan", "completion",
    },
    "external-effect": GUARANTEE_COMMON | {
        "intent", "resource_id", "id_policy", "retry_key", "version", "scope_key",
        "precall_fence", "stale", "cleanup", "cutover",
    },
    "irreversible": GUARANTEE_COMMON | {
        "capability_owner", "created_before", "server_storage", "lost_response",
    },
    "time-bound": GUARANTEE_COMMON | {
        "lease_ms", "execution_ms", "recovery_ms", "jitter_ms", "relation",
    },
    "configuration": GUARANTEE_COMMON | {
        "mode", "scope", "baseline", "preserve", "proof",
    },
    "dependency": GUARANTEE_COMMON | {
        "provider_slice", "consumer_slice", "foundation", "relation",
    },
    "retention": GUARANTEE_COMMON | {
        "active", "terminal", "retention_ms", "deletion_override", "proof",
    },
    "reconciliation": GUARANTEE_COMMON | {
        "trigger", "inventory", "query_index", "cursor", "version", "overdue", "lease_ms", "completion",
    },
}
GUARANTEE_AUTHORITIES = {"database", "provider", "permission", "configuration", "client", "server"}
CONTRACT_KEY = re.compile(r"^[a-z][a-z0-9_]*$")
CONTRACT_VALUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:,-]*$")
PLACEHOLDER = re.compile(r"^(?:tbd|todo|pending|unknown|none|n/?a|[-?])$", re.IGNORECASE)
REFERENCE = {
    "requirement": re.compile(r"\bR-[1-9][0-9]*\b"),
    "decision": re.compile(r"\bD-[1-9][0-9]*\b"),
    "flow": re.compile(r"\bF-[1-9][0-9]*\b"),
    "contract": re.compile(r"\bC-[1-9][0-9]*\b"),
    "proof": re.compile(r"\bT-[1-9][0-9]*\b"),
    "slice": re.compile(r"\bS-[1-9][0-9]*\b"),
    "failure": re.compile(r"\bFM-[1-9][0-9]*\b"),
}
RECEIPT = re.compile(r"^sha256:[0-9a-f]{64}$")
USER_EVIDENCE = re.compile(r"^user:\s*(.+)$", re.IGNORECASE)
GENERIC_USER_DECISION = re.compile(
    r"^(?:yes(?: please)?|sure|approve(?:d)?|continue|go ahead|do it|ok(?:ay)?)$",
    re.IGNORECASE,
)


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


def _parse_guarantee_contract(guarantee_id: str, guarantee_type: str, value: str) -> dict[str, str]:
    if guarantee_type not in GUARANTEE_SCHEMAS:
        raise PlanStateError(f"guarantee {guarantee_id} type is invalid")
    contract: dict[str, str] = {}
    for token in value.split(";"):
        parts = token.strip().split("=", 1)
        if len(parts) != 2 or not CONTRACT_KEY.fullmatch(parts[0]) or not CONTRACT_VALUE.fullmatch(parts[1]):
            raise PlanStateError(f"guarantee {guarantee_id} contract token is invalid")
        key, item = parts
        _concrete(item, f"guarantee {guarantee_id} {key}")
        if key in contract:
            raise PlanStateError(f"guarantee {guarantee_id} contract key is duplicated: {key}")
        contract[key] = item
    expected = GUARANTEE_SCHEMAS[guarantee_type]
    if set(contract) != expected:
        raise PlanStateError(f"guarantee {guarantee_id} contract keys differ for {guarantee_type}")
    if not re.fullmatch(r"C-[1-9][0-9]*", contract["owner"]):
        raise PlanStateError(f"guarantee {guarantee_id} owner must be C-*")
    if contract["authority"] not in GUARANTEE_AUTHORITIES:
        raise PlanStateError(f"guarantee {guarantee_id} authority is invalid")
    if not RECEIPT.fullmatch(contract["evidence"]):
        raise PlanStateError(f"guarantee {guarantee_id} evidence must be sha256")
    return contract


def _positive_int(guarantee_id: str, contract: dict[str, str], key: str, *, zero: bool = False) -> int:
    value = contract[key]
    if not value.isdigit() or (int(value) < 0 if zero else int(value) <= 0):
        raise PlanStateError(f"guarantee {guarantee_id} {key} must be a positive integer")
    return int(value)


def _validate_guarantee_contract(guarantee_id: str, guarantee_type: str, contract: dict[str, str]) -> None:
    if guarantee_type == "membership":
        if (contract["authority"] != "database" or contract["capture"] != "transactional_once"
                or contract["completion"] != "cursor_exhausted_at_high_water"):
            raise PlanStateError(f"guarantee {guarantee_id} membership contract is not finite")
        if len({contract[key] for key in ("snapshot", "high_water", "order", "query_index")}) != 4:
            raise PlanStateError(f"guarantee {guarantee_id} membership owners must be distinct")
    elif guarantee_type == "identity-access":
        mode = contract["enumeration"]
        complete = contract["completeness"]
        valid_enumeration = (
            (mode == "exhaustive_cursor" and complete == "cursor_exhausted")
            or (mode == "complete_response" and complete == "total_eq_length")
        )
        if (contract["authority"] not in {"provider", "server"}
                or not valid_enumeration
                or contract["cursor"] == contract["order"]
                or contract["credential_match"] not in {"hash_canonical_id", "exact_id"}
                or contract["incomplete"] != "deny"):
            raise PlanStateError(f"guarantee {guarantee_id} identity-access contract is not fail-closed")
    elif guarantee_type == "exhaustive":
        if (contract["authority"] != "database" or contract["orphan"] != "include"
                or contract["completion"] != "zero_remaining"):
            raise PlanStateError(f"guarantee {guarantee_id} exhaustive contract can omit owned rows")
        if len({contract[key] for key in ("inventory", "partition", "query_index", "cursor")}) != 4:
            raise PlanStateError(f"guarantee {guarantee_id} exhaustive owners must be distinct")
    elif guarantee_type == "external-effect":
        if (contract["authority"] not in {"provider", "client", "server"}
                or contract["precall_fence"] != "required" or contract["stale"] != "reject"
                or contract["cutover"] != "drain_then_activate"):
            raise PlanStateError(f"guarantee {guarantee_id} external effect is not fenced")
        id_policy = contract["id_policy"]
        retry_key = contract["retry_key"]
        valid_id_policy = (
            id_policy in {"provider_unique_once", "provider_authorized_deterministic"}
            and retry_key == "resource_id"
        ) or (id_policy == "provider_returned" and retry_key == "intent")
        if not valid_id_policy or contract["intent"] == contract["resource_id"]:
            raise PlanStateError(f"guarantee {guarantee_id} external effect identity is conflated")
        if len({contract[key] for key in ("intent", "resource_id", "version", "scope_key", "cleanup")}) != 5:
            raise PlanStateError(f"guarantee {guarantee_id} external-effect owners must be distinct")
    elif guarantee_type == "irreversible":
        if (contract["capability_owner"] not in {"client", "server_acknowledged"}
                or contract["created_before"] != "request"
                or contract["server_storage"] != "hash_only"
                or contract["lost_response"] != "same_capability_retry"):
            raise PlanStateError(f"guarantee {guarantee_id} irreversible receipt can be lost")
    elif guarantee_type == "time-bound":
        lease = _positive_int(guarantee_id, contract, "lease_ms")
        execution = _positive_int(guarantee_id, contract, "execution_ms")
        recovery = _positive_int(guarantee_id, contract, "recovery_ms", zero=True)
        jitter = _positive_int(guarantee_id, contract, "jitter_ms")
        if contract["relation"] != "strict_gt_sum" or lease <= execution + recovery + jitter:
            raise PlanStateError(f"guarantee {guarantee_id} lease lacks strict safety margin")
    elif guarantee_type == "configuration":
        if contract["authority"] != "configuration" or not re.fullmatch(r"T-[1-9][0-9]*", contract["proof"]):
            raise PlanStateError(f"guarantee {guarantee_id} configuration proof is invalid")
        if contract["mode"] == "full":
            if not RECEIPT.fullmatch(contract["baseline"]) or contract["preserve"] != "all_unrelated":
                raise PlanStateError(f"guarantee {guarantee_id} full manifest does not preserve unrelated entries")
        elif contract["mode"] == "overlay":
            if contract["baseline"] != "scope_digest" or contract["preserve"] != "outside_scope_unchanged":
                raise PlanStateError(f"guarantee {guarantee_id} overlay scope is not isolated")
        else:
            raise PlanStateError(f"guarantee {guarantee_id} configuration mode is invalid")
    elif guarantee_type == "dependency":
        provider = contract["provider_slice"]
        consumer = contract["consumer_slice"]
        if (not re.fullmatch(r"S-[1-9][0-9]*", provider)
                or not re.fullmatch(r"S-[1-9][0-9]*", consumer)
                or not re.fullmatch(r"C-[1-9][0-9]*", contract["foundation"])
                or contract["relation"] != "precedes_or_same"
                or int(provider[2:]) > int(consumer[2:])):
            raise PlanStateError(f"guarantee {guarantee_id} dependency foundation follows its consumer")
    elif guarantee_type == "retention":
        if (contract["authority"] != "database" or contract["active"] != "zero"
                or contract["terminal"] != "retained"
                or contract["deletion_override"] not in {"retain", "explicit_exhaustive"}
                or not re.fullmatch(r"T-[1-9][0-9]*", contract["proof"])):
            raise PlanStateError(f"guarantee {guarantee_id} retention assertion is invalid")
        _positive_int(guarantee_id, contract, "retention_ms")
    elif guarantee_type == "reconciliation":
        if (contract["authority"] != "database" or contract["overdue"] != "mark_missed"
                or contract["completion"] != "zero_remaining"):
            raise PlanStateError(f"guarantee {guarantee_id} reconciliation is not exhaustive")
        if len({contract[key] for key in ("trigger", "inventory", "query_index", "cursor", "version")}) != 5:
            raise PlanStateError(f"guarantee {guarantee_id} reconciliation owners must be distinct")
        _positive_int(guarantee_id, contract, "lease_ms")


def validate_plan_admission(text: str) -> None:
    risk_tier = _risk_tier(text)
    decisions = _table(text, "## Decision Model", DECISION_HEADER)
    traces = _table(text, "## Traceability", TRACE_HEADER)
    failures = _table(text, "## Failure Model", FAILURE_HEADER)
    has_concrete_failure = any(row[0] != "FM-NA" for row in failures)
    guarantees = (
        _table(text, "## Guarantee Model", GUARANTEE_HEADER)
        if has_concrete_failure else ()
    )
    challenges = _table(text, "## Plan challenge", CHALLENGE_HEADER)

    decision_ids: set[str] = set()
    for row in decisions:
        decision_id, subject, alternatives, selected, authority, evidence, consequences = row
        if not re.fullmatch(r"D-[1-9][0-9]*", decision_id) or decision_id in decision_ids:
            raise PlanStateError("Decision Model requires unique D-* IDs")
        decision_ids.add(decision_id)
        for value, label in zip(row[1:], DECISION_HEADER[1:]):
            _concrete(value, f"decision {decision_id} {label}")
        if authority not in {"user", "engineering", "external"}:
            raise PlanStateError(f"decision {decision_id} authority is invalid")
        if authority == "user":
            match = USER_EVIDENCE.fullmatch(evidence)
            decision = match.group(1).strip().strip("\"'") if match else ""
            if not match or len(decision.split()) < 3 or GENERIC_USER_DECISION.fullmatch(decision):
                raise PlanStateError(f"decision {decision_id} lacks concrete user evidence")
        elif not RECEIPT.fullmatch(evidence):
            raise PlanStateError(f"decision {decision_id} requires sha256 evidence")

    trace_ids: set[str] = set()
    requirement_refs: set[str] = set()
    decision_refs: set[str] = set()
    flow_refs: set[str] = set()
    contract_refs: set[str] = set()
    proof_refs: set[str] = set()
    slice_refs: set[str] = set()
    for row in traces:
        trace_id, requirement, decision, flow, contract, proof, telemetry, slice_ref = row
        if not re.fullmatch(r"TR-[1-9][0-9]*", trace_id) or trace_id in trace_ids:
            raise PlanStateError("Traceability requires unique ordered-style TR-* IDs")
        trace_ids.add(trace_id)
        for value, label in zip(row[1:], TRACE_HEADER[1:]):
            _concrete(value, f"traceability {trace_id} {label}")
        required = {
            "requirement": requirement, "decision": decision, "flow": flow,
            "contract": contract, "proof": proof, "slice": slice_ref,
        }
        for kind, value in required.items():
            if not _references(value, kind):
                raise PlanStateError(f"traceability {trace_id} lacks {kind} ID")
        requirement_refs.update(_references(requirement, "requirement"))
        decision_refs.update(_references(decision, "decision"))
        flow_refs.update(_references(flow, "flow"))
        contract_refs.update(_references(contract, "contract"))
        proof_refs.update(_references(proof, "proof"))
        slice_refs.update(_references(slice_ref, "slice"))

    owner_sections = {
        "requirement": (requirement_refs, "## Feature"),
        "decision": (decision_refs, "## Decision Model"),
        "flow": (flow_refs, "## Flows"),
        "contract": (contract_refs, "## Contracts"),
        "proof": (proof_refs, "## Testing"),
        "slice": (slice_refs, "## Slices"),
    }
    for kind, (references, heading) in owner_sections.items():
        owned = set(REFERENCE[kind].findall("\n".join(_section(text, heading))))
        if not references or references != owned:
            raise PlanStateError(f"Traceability and {heading} {kind} IDs differ")

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

    covered_failures: set[str] = set()
    guarantee_ids: set[str] = set()
    for guarantee_id, guarantee_type, encoded_contract, trace in guarantees:
        if not re.fullmatch(r"G-[1-9][0-9]*", guarantee_id) or guarantee_id in guarantee_ids:
            raise PlanStateError("Guarantee Model requires unique G-* IDs")
        guarantee_ids.add(guarantee_id)
        contract = _parse_guarantee_contract(guarantee_id, guarantee_type, encoded_contract)
        _validate_guarantee_contract(guarantee_id, guarantee_type, contract)
        required_trace = {
            "requirement": requirement_refs,
            "contract": contract_refs,
            "failure": failure_ids,
            "proof": proof_refs,
            "slice": slice_refs,
        }
        for kind, owned in required_trace.items():
            references = _references(trace, kind)
            if not references or not references.issubset(owned):
                raise PlanStateError(f"guarantee {guarantee_id} lacks traced {kind} ID")
        if contract["owner"] not in _references(trace, "contract"):
            raise PlanStateError(f"guarantee {guarantee_id} owner is not traced")
        for key in ("proof", "provider_slice", "consumer_slice", "foundation"):
            if key in contract and contract[key] not in trace:
                raise PlanStateError(f"guarantee {guarantee_id} {key} is not traced")
        covered_failures.update(_references(trace, "failure"))
    if has_concrete_failure and covered_failures != failure_ids:
        raise PlanStateError("Guarantee Model must cover every concrete FM-* row")

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
