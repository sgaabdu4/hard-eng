#!/usr/bin/env python3
"""Parse and atomically update Hard Eng active items and learning candidates."""

from __future__ import annotations

import hashlib
import re

from plan_contract import ITEM_FIELD_INDEX, ITEM_HEADER, ITEM_KEYS, ITEM_STATUS, PlanStateError, audit_receipt_snapshot


LEARNING_HEADER = (
    "ID", "Trigger", "Source", "Evidence", "Cause", "Owner", "Required proof", "Resolution", "Status"
)
LEARNING_TRIGGERS = {
    "recurrence", "user-correction", "systemic-critical-gap", "false-gate", "repeated-manual-waste"
}
LEARNING_STATUS = {"open", "closed"}
SHA256 = r"sha256:[0-9a-f]{64}"
LEARNING_PASS_INPUT = re.compile(r"^PASS: ([^;]+)$")
LEARNING_PASS = re.compile(
    rf"^PASS: (?P<summary>[^;]+); required-proof=(?P<proof>{SHA256}); "
    rf"snapshot=(?P<snapshot>{SHA256}); artifact=(?P<artifact>{SHA256})$"
)
LEARNING_TRANSFER = re.compile(r"^TRANSFER: [a-z0-9][a-z0-9-]*/L-[1-9][0-9]*$")


def proof_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def learning_pass_binding(receipt: str) -> tuple[str, str, str] | None:
    match = LEARNING_PASS.fullmatch(receipt)
    return match.group("proof", "snapshot", "artifact") if match else None


def bound_learning_receipt(summary: str, required_proof: str, snapshot: str, artifact: str) -> str:
    match = LEARNING_PASS_INPUT.fullmatch(clean_value(summary))
    if not match or not re.fullmatch(SHA256, snapshot) or not re.fullmatch(SHA256, artifact):
        raise PlanStateError("invalid learning proof receipt")
    return (
        f"PASS: {match.group(1)}; required-proof={proof_digest(required_proof)}; "
        f"snapshot={snapshot}; artifact={artifact}"
    )


def table_rows(text: str, heading: str, header: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    lines = text.splitlines()
    headings = [i for i, line in enumerate(lines) if line.strip() == heading]
    if len(headings) != 1:
        raise PlanStateError(f"{heading} requires exactly one owner")
    start = headings[0] + 1
    table = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            table.append(line.strip())
    cells = lambda line: tuple(cell.strip() for cell in line.strip("|").split("|"))
    if len(table) < 2 or cells(table[0]) != header:
        raise PlanStateError(f"invalid {heading.removeprefix('## ').lower()} table")
    if len(cells(table[1])) != len(header) or any(
        not re.fullmatch(r":?-{3,}:?", cell) for cell in cells(table[1])
    ):
        raise PlanStateError(f"invalid {heading.removeprefix('## ').lower()} separator")
    rows = tuple(cells(line) for line in table[2:])
    if any(len(row) != len(header) for row in rows):
        raise PlanStateError(f"invalid {heading.removeprefix('## ').lower()} row")
    return rows


def parse_active_items(text: str) -> dict[str, tuple[str, ...]]:
    items = {}
    for row in table_rows(text, "## Active items", ITEM_HEADER):
        item_id = row[0]
        if not item_id or item_id in items:
            raise PlanStateError(f"invalid or duplicate active-item ID: {item_id}")
        matching = [kind for prefix, kind in ITEM_KEYS.values() if re.fullmatch(rf"{prefix}-[0-9]+", item_id)]
        if len(matching) != 1 or row[1] != matching[0]:
            raise PlanStateError(f"active-item ID/type mismatch: {item_id}")
        if row[6] not in ITEM_STATUS:
            raise PlanStateError(f"invalid active-item status: {item_id}")
        items[item_id] = row
    return items


def parse_learning_candidates(text: str) -> dict[str, tuple[str, ...]]:
    candidates = {}
    identities = set()
    for index, row in enumerate(table_rows(text, "## Learning Candidates", LEARNING_HEADER), start=1):
        candidate_id = row[0]
        if candidate_id != f"L-{index}" or any(not value for value in row):
            raise PlanStateError("learning candidate IDs must be a complete contiguous sequence")
        if row[1] not in LEARNING_TRIGGERS:
            raise PlanStateError(f"invalid learning trigger: {candidate_id}")
        if not row[3].startswith("Verified: "):
            raise PlanStateError(f"invalid learning evidence: {candidate_id}")
        identity = candidate_identity(row[2], row[4])
        if identity in identities:
            raise PlanStateError(f"duplicate learning candidate: {candidate_id}")
        identities.add(identity)
        if row[8] not in LEARNING_STATUS:
            raise PlanStateError(f"invalid learning status: {candidate_id}")
        if row[8] == "open" and row[7] != "pending":
            raise PlanStateError(f"open learning candidate has resolution: {candidate_id}")
        if row[8] == "closed":
            binding = learning_pass_binding(row[7])
            if binding and binding[0] != proof_digest(row[6]):
                raise PlanStateError(f"learning proof does not bind required proof: {candidate_id}")
            if not binding and not LEARNING_TRANSFER.fullmatch(row[7]):
                raise PlanStateError(f"closed learning candidate lacks verified proof: {candidate_id}")
        candidates[candidate_id] = row
    return candidates


def closed_plan_authority(text: str) -> str:
    headings = set(text.splitlines())
    items = parse_active_items(text) if "## Active items" in headings else {}
    candidates = parse_learning_candidates(text) if "## Learning Candidates" in headings else {}
    lines = [
        f"- {row[0]} | type={row[1]} | evidence={row[2]} | impact={row[3]} | closure={row[5]}"
        for row in items.values() if row[6] == "closed"
    ]
    lines.extend(
        f"- {row[0]} | trigger={row[1]} | source={row[2]} | evidence={row[3]} | cause={row[4]} | "
        f"required-proof={row[6]} | resolution={row[7]}"
        for row in candidates.values() if row[8] == "closed"
    )
    return "\n".join(lines) or "<none>"


def clean_value(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or "|" in cleaned or "\n" in cleaned or "\r" in cleaned:
        raise PlanStateError("table values must be non-empty single-line text without pipes")
    return cleaned


def candidate_identity(source: str, cause: str) -> tuple[str, str]:
    normalize = lambda value: " ".join(value.casefold().split())
    return normalize(source), normalize(cause)


def next_item_id(items: dict[str, tuple[str, ...]], item_type: str) -> str:
    prefixes = {value: prefix for prefix, value in ITEM_KEYS.values()}
    if item_type not in prefixes:
        raise PlanStateError(f"invalid active-item type: {item_type}")
    prefix = prefixes[item_type]
    numbers = [int(item_id.split("-", 1)[1]) for item_id in items if item_id.startswith(f"{prefix}-")]
    return f"{prefix}-{max(numbers, default=0) + 1}"


def apply_item_operations(items, additions, updates, closures):
    changed = dict(items)
    touched = set()
    for item_id, field, value in updates:
        if item_id not in changed or field not in ITEM_FIELD_INDEX or (item_id, field) in touched:
            raise PlanStateError(f"invalid active-item update: {item_id}/{field}")
        touched.add((item_id, field))
        row = list(changed[item_id])
        row[ITEM_FIELD_INDEX[field]] = clean_value(value)
        changed[item_id] = tuple(row)
    for item_id in closures:
        if item_id not in changed or changed[item_id][6] != "open" or (item_id, "status") in touched:
            raise PlanStateError(f"active item is not open: {item_id}")
        touched.add((item_id, "status"))
        row = list(changed[item_id])
        row[6] = "closed"
        changed[item_id] = tuple(row)
    added = []
    for item_type, evidence, impact, owner, next_action in additions:
        item_id = next_item_id(changed, item_type)
        changed[item_id] = (
            item_id, item_type, clean_value(evidence), clean_value(impact), clean_value(owner),
            clean_value(next_action), "open",
        )
        added.append(item_id)
    return changed, tuple(added)


def apply_learning_operations(
    candidates, additions, resolutions, transfers=(), refreshes=(),
    current_snapshot: str | None = None, current_artifact: str | None = None,
):
    changed = dict(candidates)
    added = []
    identities = {candidate_identity(row[2], row[4]) for row in changed.values()}
    for trigger, source, evidence, cause, owner, proof in additions:
        cleaned = tuple(clean_value(value) for value in (trigger, source, evidence, cause, owner, proof))
        if cleaned[0] not in LEARNING_TRIGGERS:
            raise PlanStateError("invalid learning trigger")
        if not cleaned[2].startswith("Verified: "):
            raise PlanStateError("learning candidate requires Verified evidence")
        identity = candidate_identity(cleaned[1], cleaned[3])
        if identity in identities:
            raise PlanStateError("duplicate learning candidate")
        identities.add(identity)
        candidate_id = f"L-{len(changed) + 1}"
        changed[candidate_id] = (
            candidate_id, *cleaned, "pending", "open",
        )
        added.append(candidate_id)
    resolved = []
    touched = set()
    for candidate_id, resolution in resolutions:
        if candidate_id in touched or candidate_id not in changed or changed[candidate_id][8] != "open":
            raise PlanStateError(f"learning candidate is not open: {candidate_id}")
        touched.add(candidate_id)
        receipt = bound_learning_receipt(
            resolution, changed[candidate_id][6], current_snapshot or "", current_artifact or ""
        )
        row = list(changed[candidate_id])
        row[7:9] = [receipt, "closed"]
        changed[candidate_id] = tuple(row)
        resolved.append(candidate_id)
    refreshed = []
    for candidate_id, resolution in refreshes:
        if candidate_id in touched or candidate_id not in changed or changed[candidate_id][8] != "closed":
            raise PlanStateError(f"learning candidate is not closed: {candidate_id}")
        if not learning_pass_binding(changed[candidate_id][7]):
            raise PlanStateError(f"learning candidate is not locally resolved: {candidate_id}")
        touched.add(candidate_id)
        row = list(changed[candidate_id])
        row[7] = bound_learning_receipt(
            resolution, row[6], current_snapshot or "", current_artifact or ""
        )
        changed[candidate_id] = tuple(row)
        refreshed.append(candidate_id)
    for candidate_id, receipt in transfers:
        if candidate_id in touched or candidate_id not in changed or changed[candidate_id][8] != "open":
            raise PlanStateError(f"learning candidate is not open: {candidate_id}")
        touched.add(candidate_id)
        if not LEARNING_TRANSFER.fullmatch(receipt):
            raise PlanStateError(f"invalid learning transfer receipt: {candidate_id}")
        row = list(changed[candidate_id])
        row[7:9] = [receipt, "closed"]
        changed[candidate_id] = tuple(row)
        resolved.append(candidate_id)
    parse_learning_candidates(render_table("## Learning Candidates", LEARNING_HEADER, changed))
    return changed, tuple(added), tuple(resolved), tuple(refreshed)


def validate_learning_receipts_current(candidates, current_snapshot: str, current_artifact: str) -> None:
    for candidate_id, row in candidates.items():
        binding = learning_pass_binding(row[7]) if row[8] == "closed" else None
        if binding and binding[1:] != (current_snapshot, current_artifact):
            raise PlanStateError(f"stale learning proof receipt: {candidate_id}")


def rebind_learning_receipts(text: str, current_snapshot: str, current_artifact: str) -> str:
    candidates = parse_learning_candidates(text)
    changed = dict(candidates)
    for candidate_id, row in candidates.items():
        if not learning_pass_binding(row[7]):
            continue
        updated = list(row)
        summary = row[7].split("; required-proof=", 1)[0]
        updated[7] = bound_learning_receipt(summary, row[6], current_snapshot, current_artifact)
        changed[candidate_id] = tuple(updated)
    return replace_learning_candidates(text, changed)


def rebind_audit_receipts(text: str, previous_snapshot: str, current_snapshot: str) -> str:
    if not re.fullmatch(SHA256, previous_snapshot) or not re.fullmatch(SHA256, current_snapshot):
        raise PlanStateError("invalid audit receipt reconciliation snapshot")
    items = parse_active_items(text)
    changed = dict(items)
    for item_id, row in items.items():
        if not row[2].startswith("audit="):
            continue
        if row[6] != "closed" or audit_receipt_snapshot(row) != previous_snapshot:
            raise PlanStateError(f"audit receipt cannot reconcile: {item_id}")
        updated = list(row)
        updated[5] = re.sub(
            rf"re-audit=pass@{re.escape(previous_snapshot)}$",
            f"re-audit=pass@{current_snapshot}",
            row[5],
        )
        changed[item_id] = tuple(updated)
    return replace_active_items(text, changed)


def prune_closed_records(items, candidates, current_snapshot: str, current_artifact: str):
    if any(row[8] == "open" for row in candidates.values()):
        raise PlanStateError("closed chronology prune requires zero open learning candidate")
    validate_learning_receipts_current(candidates, current_snapshot, current_artifact)
    retained = {
        item_id: row for item_id, row in items.items()
        if row[6] == "open" or (row[2].startswith("audit=") and audit_receipt_snapshot(row) != current_snapshot)
    }
    return retained, {}


def open_item_state(items: dict[str, tuple[str, ...]]) -> dict[str, str]:
    values = {}
    for key, (prefix, item_type) in ITEM_KEYS.items():
        ids = [item_id for item_id, row in items.items() if row[1] == item_type and row[6] == "open"]
        ids.sort(key=lambda item_id: int(item_id.removeprefix(f"{prefix}-")))
        values[key] = ",".join(ids) or "none"
    return values


def render_table(heading: str, header: tuple[str, ...], rows) -> str:
    separator = "|" + "---|" * len(header)
    body = "\n".join("| " + " | ".join(row) + " |" for row in rows.values())
    return f"{heading}\n| " + " | ".join(header) + f" |\n{separator}\n{body}\n"


def replace_table(text: str, heading: str, header: tuple[str, ...], rows) -> str:
    lines = text.splitlines()
    try:
        heading_index = next(i for i, line in enumerate(lines) if line.strip() == heading)
        table_start = next(i for i in range(heading_index + 1, len(lines)) if lines[i].strip().startswith("|"))
    except StopIteration as exc:
        raise PlanStateError(f"missing {heading} table") from exc
    table_end = table_start
    while table_end + 1 < len(lines) and lines[table_end + 1].strip().startswith("|"):
        table_end += 1
    rendered = render_table(heading, header, rows).splitlines()[1:]
    lines[table_start:table_end + 1] = rendered
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def replace_active_items(text: str, items) -> str:
    return replace_table(text, "## Active items", ITEM_HEADER, items)


def replace_learning_candidates(text: str, candidates) -> str:
    return replace_table(text, "## Learning Candidates", LEARNING_HEADER, candidates)
