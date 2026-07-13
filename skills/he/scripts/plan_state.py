#!/usr/bin/env python3
"""Initialize, inspect, and atomically checkpoint Hard Eng PLAN.md state."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = (
    "state_version",
    "plan_id",
    "feature_slug",
    "repository_root",
    "branch",
    "base_sha",
    "head_sha",
    "updated_at_utc",
    "lifecycle_status",
    "current_stage",
    "plan_stage",
    "approved_plan_stages",
    "skipped_plan_stages",
    "stage_status",
    "next_action",
    "waiting_for",
    "plan_approved",
    "open_blockers",
    "open_issues",
    "open_unknowns",
)
TERMINAL = {"shipped", "cancelled"}
LIFECYCLE = {"planning", "build-ready", "building", "green", "shipping", "learning", *TERMINAL}
STAGES = {"plan", "build", "ship", "learn"}
ROUTE_TARGETS = {
    "planning": "$he-plan",
    "build-ready": "$he-build",
    "building": "$he-build",
    "green": "$he-ship",
    "shipping": "$he-ship",
    "learning": "$he-learn",
    "shipped": "none",
    "cancelled": "none",
}
PLAN_STAGES = (
    "repository",
    "research",
    "feature",
    "flows",
    "ux",
    "contracts",
    "technical",
    "testing",
    "rollout",
    "slices",
    "consistency",
    "approval",
)
STAGE_STATUS = {"pending", "in-progress", "awaiting-user", "blocked", "complete"}
WAITING_FOR = {"agent", "user", "external", "none"}
ITEM_KEYS = {
    "open_blockers": ("B", "blocker"),
    "open_issues": ("I", "issue"),
    "open_unknowns": ("U", "unknown"),
}
MUTABLE_STATE_KEYS = {
    "lifecycle_status",
    "current_stage",
    "plan_stage",
    "approved_plan_stages",
    "skipped_plan_stages",
    "stage_status",
    "next_action",
    "waiting_for",
    "plan_approved",
}
ITEM_FIELD_INDEX = {"evidence": 2, "impact": 3, "owner": 4, "next-action": 5}
ITEM_STATUS = {"open", "closed"}
STATE_LINE = re.compile(r"^- ([a-z][a-z0-9_]*) = (.+)$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SHA = re.compile(r"^(?:[0-9a-f]{40}|UNBORN)$")
ITEM_HEADER = ("ID", "Type", "Evidence", "Impact", "Owner", "Next proof/action", "Status")


class PlanStateError(ValueError):
    pass


def parse_state(text: str) -> dict[str, str]:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## State") + 1
    except StopIteration as exc:
        raise PlanStateError("missing ## State") from exc

    state: dict[str, str] = {}
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if not line.strip():
            continue
        match = STATE_LINE.fullmatch(line.strip())
        if not match:
            raise PlanStateError(f"invalid state line: {line.strip()}")
        key, value = match.groups()
        if key in state:
            raise PlanStateError(f"duplicate state key: {key}")
        state[key] = value.strip()

    missing = [key for key in REQUIRED if not state.get(key)]
    extra = sorted(set(state) - set(REQUIRED))
    if missing:
        raise PlanStateError("missing keys: " + ",".join(missing))
    if extra:
        raise PlanStateError("unknown keys: " + ",".join(extra))
    validate_values(state)
    return state


def validate_values(state: dict[str, str]) -> None:
    if state["state_version"] != "2":
        raise PlanStateError("unsupported state_version")
    for key in ("plan_id", "feature_slug"):
        if not SLUG.fullmatch(state[key]):
            raise PlanStateError(f"invalid {key}")
    for key in ("base_sha", "head_sha"):
        if not SHA.fullmatch(state[key]):
            raise PlanStateError(f"invalid {key}")
    if state["lifecycle_status"] not in LIFECYCLE:
        raise PlanStateError("invalid lifecycle_status")
    if state["current_stage"] not in STAGES:
        raise PlanStateError("invalid current_stage")
    if state["plan_stage"] != "none" and state["plan_stage"] not in PLAN_STAGES:
        raise PlanStateError("invalid plan_stage")
    if state["stage_status"] not in STAGE_STATUS:
        raise PlanStateError("invalid stage_status")
    if state["waiting_for"] not in WAITING_FOR:
        raise PlanStateError("invalid waiting_for")
    if state["plan_approved"] not in {"yes", "no"}:
        raise PlanStateError("invalid plan_approved")
    try:
        datetime.strptime(state["updated_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PlanStateError("invalid updated_at_utc") from exc
    for key, (prefix, _) in ITEM_KEYS.items():
        value = state[key]
        if value == "none":
            continue
        ids = [item.strip() for item in value.split(",")]
        if not ids or any(not re.fullmatch(rf"{prefix}-[0-9]+", item) for item in ids):
            raise PlanStateError(f"invalid {key}")


def parse_plan_stage_list(state: dict[str, str], key: str) -> tuple[str, ...]:
    value = state[key]
    if value == "none":
        return ()
    stages = tuple(item.strip() for item in value.split(","))
    if not stages or any(stage not in PLAN_STAGES for stage in stages):
        raise PlanStateError(f"invalid {key}")
    if len(stages) != len(set(stages)):
        raise PlanStateError(f"duplicate {key}")
    positions = tuple(PLAN_STAGES.index(stage) for stage in stages)
    if positions != tuple(sorted(positions)):
        raise PlanStateError(f"unordered {key}")
    return stages


def parse_active_items(text: str) -> dict[str, tuple[str, ...]]:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == "## Active items") + 1
    except StopIteration as exc:
        raise PlanStateError("missing ## Active items") from exc

    table: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            table.append(line.strip())
    if len(table) < 2:
        raise PlanStateError("missing active-items table")

    def cells(line: str) -> tuple[str, ...]:
        return tuple(cell.strip() for cell in line.strip("|").split("|"))

    if cells(table[0]) != ITEM_HEADER:
        raise PlanStateError("invalid active-items header")
    if len(cells(table[1])) != len(ITEM_HEADER) or any(
        not re.fullmatch(r":?-{3,}:?", cell) for cell in cells(table[1])
    ):
        raise PlanStateError("invalid active-items separator")

    items: dict[str, tuple[str, ...]] = {}
    for line in table[2:]:
        row = cells(line)
        if len(row) != len(ITEM_HEADER):
            raise PlanStateError("invalid active-items row")
        item_id = row[0]
        if not item_id:
            raise PlanStateError("empty active-item ID")
        if item_id in items:
            raise PlanStateError(f"duplicate active-item ID: {item_id}")
        matching_types = [
            item_type
            for prefix, item_type in ITEM_KEYS.values()
            if re.fullmatch(rf"{prefix}-[0-9]+", item_id)
        ]
        if len(matching_types) != 1 or row[1] != matching_types[0]:
            raise PlanStateError(f"active-item ID/type mismatch: {item_id}")
        if row[6] not in ITEM_STATUS:
            raise PlanStateError(f"invalid active-item status: {item_id}")
        items[item_id] = row
    return items


def clean_item_value(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or "|" in cleaned or "\n" in cleaned or "\r" in cleaned:
        raise PlanStateError("item values must be non-empty single-line text without pipes")
    return cleaned


def parse_state_updates(assignments: list[str]) -> dict[str, str]:
    updates: dict[str, str] = {}
    for assignment in assignments:
        key, separator, value = assignment.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            raise PlanStateError("state update requires key=value")
        if key not in MUTABLE_STATE_KEYS:
            raise PlanStateError(f"checkpoint cannot set state key: {key}")
        if key in updates:
            raise PlanStateError(f"duplicate state update: {key}")
        updates[key] = value
    return updates


def next_item_id(items: dict[str, tuple[str, ...]], item_type: str) -> str:
    prefixes = {value: prefix for prefix, value in ITEM_KEYS.values()}
    if item_type not in prefixes:
        raise PlanStateError(f"invalid active-item type: {item_type}")
    prefix = prefixes[item_type]
    numbers = [int(item_id.split("-", 1)[1]) for item_id in items if item_id.startswith(f"{prefix}-")]
    return f"{prefix}-{max(numbers, default=0) + 1}"


def apply_item_operations(
    items: dict[str, tuple[str, ...]],
    additions: list[list[str]],
    updates: list[list[str]],
    closures: list[str],
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    changed = dict(items)
    touched: set[tuple[str, str]] = set()
    for item_id, field, value in updates:
        if item_id not in changed:
            raise PlanStateError(f"active item not found: {item_id}")
        if field not in ITEM_FIELD_INDEX:
            raise PlanStateError(f"invalid active-item field: {field}")
        marker = (item_id, field)
        if marker in touched:
            raise PlanStateError(f"duplicate active-item update: {item_id}/{field}")
        touched.add(marker)
        row = list(changed[item_id])
        row[ITEM_FIELD_INDEX[field]] = clean_item_value(value)
        changed[item_id] = tuple(row)

    for item_id in closures:
        if item_id not in changed:
            raise PlanStateError(f"active item not found: {item_id}")
        marker = (item_id, "status")
        if marker in touched:
            raise PlanStateError(f"duplicate active-item close: {item_id}")
        touched.add(marker)
        row = list(changed[item_id])
        if row[6] != "open":
            raise PlanStateError(f"active item is not open: {item_id}")
        row[6] = "closed"
        changed[item_id] = tuple(row)

    added: list[str] = []
    for values in additions:
        item_type, evidence, impact, owner, next_action = values
        item_id = next_item_id(changed, item_type)
        changed[item_id] = (
            item_id,
            item_type,
            clean_item_value(evidence),
            clean_item_value(impact),
            clean_item_value(owner),
            clean_item_value(next_action),
            "open",
        )
        added.append(item_id)
    return changed, tuple(added)


def open_item_state(items: dict[str, tuple[str, ...]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, (prefix, item_type) in ITEM_KEYS.items():
        ids = [
            item_id
            for item_id, row in items.items()
            if row[1] == item_type and row[6] == "open"
        ]
        ids.sort(key=lambda item_id: int(item_id.removeprefix(f"{prefix}-")))
        values[key] = ",".join(ids) or "none"
    return values


def replace_state(text: str, updates: dict[str, str]) -> str:
    lines = text.splitlines()
    counts = {key: 0 for key in updates}
    for index, line in enumerate(lines):
        match = STATE_LINE.fullmatch(line.strip())
        if match and match.group(1) in updates:
            key = match.group(1)
            lines[index] = f"- {key} = {updates[key]}"
            counts[key] += 1
    missing = [key for key, count in counts.items() if count != 1]
    if missing:
        raise PlanStateError("state replacement count invalid: " + ",".join(missing))
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def replace_active_items(text: str, items: dict[str, tuple[str, ...]]) -> str:
    lines = text.splitlines()
    try:
        heading = next(i for i, line in enumerate(lines) if line.strip() == "## Active items")
        table_start = next(i for i in range(heading + 1, len(lines)) if lines[i].strip().startswith("|"))
    except StopIteration as exc:
        raise PlanStateError("missing active-items table") from exc
    table_end = table_start
    while table_end + 1 < len(lines) and lines[table_end + 1].strip().startswith("|"):
        table_end += 1
    table = [
        "| " + " | ".join(ITEM_HEADER) + " |",
        "|---|---|---|---|---|---|---|",
        *("| " + " | ".join(row) + " |" for row in items.values()),
    ]
    lines[table_start : table_end + 1] = table
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def document_token(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def checkpoint_token(text: str) -> str:
    state = parse_state(text)
    items = parse_active_items(text)
    material = "\n".join(
        [*(f"{key}={state[key]}" for key in REQUIRED), *("|".join(row) for row in items.values())]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_item_links(state: dict[str, str], items: dict[str, tuple[str, ...]]) -> None:
    expected: dict[str, str] = {}
    for key, (_, item_type) in ITEM_KEYS.items():
        if state[key] == "none":
            continue
        for item_id in (value.strip() for value in state[key].split(",")):
            expected[item_id] = item_type

    for item_id, item_type in expected.items():
        row = items.get(item_id)
        if row is None:
            raise PlanStateError(f"missing active-item row: {item_id}")
        if row[1] != item_type or row[6] != "open":
            raise PlanStateError(f"invalid active-item link: {item_id}")

    tracked_types = {item_type for _, item_type in ITEM_KEYS.values()}
    for item_id, row in items.items():
        if row[1] in tracked_types and row[6] == "open" and item_id not in expected:
            raise PlanStateError(f"unlisted open active item: {item_id}")


def validate_transition(state: dict[str, str]) -> None:
    lifecycle = state["lifecycle_status"]
    stage = state["current_stage"]
    approved = state["plan_approved"]
    approved_stages = parse_plan_stage_list(state, "approved_plan_stages")
    skipped_stages = parse_plan_stage_list(state, "skipped_plan_stages")
    overlap = set(approved_stages) & set(skipped_stages)
    if overlap:
        raise PlanStateError("plan stage both approved and skipped")
    if "approval" in skipped_stages:
        raise PlanStateError("approval plan stage cannot be skipped")
    accounted = set(approved_stages) | set(skipped_stages)
    expected_stage = {
        "planning": "plan",
        "build-ready": "build",
        "building": "build",
        "green": "ship",
        "shipping": "ship",
        "learning": "learn",
    }
    if lifecycle in expected_stage and stage != expected_stage[lifecycle]:
        raise PlanStateError("lifecycle/current_stage mismatch")
    if lifecycle == "planning":
        if approved != "no":
            raise PlanStateError("planning state cannot be approved")
        if state["plan_stage"] == "none":
            raise PlanStateError("planning state requires plan_stage")
        current_index = PLAN_STAGES.index(state["plan_stage"])
        if accounted != set(PLAN_STAGES[:current_index]):
            raise PlanStateError("planning stages are not an exact completed prefix")
    elif state["plan_stage"] != "none":
        raise PlanStateError("non-planning state requires plan_stage=none")
    if lifecycle in {"build-ready", "building", "green", "shipping", "learning", "shipped"} and approved != "yes":
        raise PlanStateError("post-plan lifecycle requires approval")
    if lifecycle in {"build-ready", "building", "green", "shipping", "learning", "shipped"}:
        if accounted != set(PLAN_STAGES) or "approval" not in approved_stages:
            raise PlanStateError("post-plan lifecycle requires every plan stage accounted and approval approved")
    if lifecycle == "build-ready":
        if any(state[key] != "none" for key in ITEM_KEYS):
            raise PlanStateError("build-ready state has open blockers/issues/unknowns")
        if state["stage_status"] != "pending":
            raise PlanStateError("build-ready state requires pending build stage")
    if lifecycle == "shipped" and (stage != "ship" or state["stage_status"] != "complete"):
        raise PlanStateError("shipped state is incomplete")


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def git_identity(repo: Path) -> tuple[Path, str, str]:
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    try:
        branch = git(root, "symbolic-ref", "--short", "HEAD")
    except subprocess.CalledProcessError:
        branch = "DETACHED"
    try:
        head = git(root, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        head = "UNBORN"
    return root, branch, head


def plan_only_head_drift(state: dict[str, str], root: Path, head: str, plan: Path) -> bool:
    recorded = state["head_sha"]
    if recorded in {"UNBORN", head}:
        return False
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", recorded, head],
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        return False
    changed = {line for line in git(root, "diff", "--name-only", f"{recorded}..{head}").splitlines() if line}
    return changed <= {str(plan.relative_to(root))}


def freshness_errors(state: dict[str, str], root: Path, branch: str, head: str, plan: Path) -> list[str]:
    errors: list[str] = []
    if Path(state["repository_root"]).expanduser().resolve() != root:
        errors.append("repository_root")
    if state["branch"] != branch:
        errors.append("branch")
    if state["head_sha"] != head and not plan_only_head_drift(state, root, head, plan):
        errors.append("head_sha")
    if state["base_sha"] != "UNBORN":
        try:
            git(root, "cat-file", "-e", f'{state["base_sha"]}^{{commit}}')
        except subprocess.CalledProcessError:
            errors.append("base_sha")
    return errors


def emit(key: str, value: str) -> None:
    clean = value.replace("\n", " ").replace("\r", " ")
    print(f"{key}={clean}")


def initialize(repo_arg: str, feature_slug: str, plan_id: str | None) -> int:
    try:
        root, branch, head = git_identity(Path(repo_arg).expanduser().resolve())
    except (subprocess.CalledProcessError, FileNotFoundError):
        emit("result", "invalid")
        emit("error", "repository is not a readable Git worktree")
        return 4
    resolved_plan_id = plan_id or feature_slug
    if not SLUG.fullmatch(feature_slug) or not SLUG.fullmatch(resolved_plan_id):
        emit("result", "invalid")
        emit("error", "feature_slug and plan_id require lowercase letters, digits, or hyphens")
        return 4
    path = root / "features" / feature_slug / "PLAN.md"
    if path.exists():
        emit("result", "invalid")
        emit("error", "canonical PLAN.md already exists")
        emit("plan", str(path))
        return 4
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = f"""# {feature_slug}

## State
- state_version = 2
- plan_id = {resolved_plan_id}
- feature_slug = {feature_slug}
- repository_root = {root}
- branch = {branch}
- base_sha = {head}
- head_sha = {head}
- updated_at_utc = {updated}
- lifecycle_status = planning
- current_stage = plan
- plan_stage = repository
- approved_plan_stages = none
- skipped_plan_stages = none
- stage_status = in-progress
- next_action = Establish repository identity and research scope.
- waiting_for = agent
- plan_approved = no
- open_blockers = none
- open_issues = none
- open_unknowns = none

## Active items
| ID | Type | Evidence | Impact | Owner | Next proof/action | Status |
|---|---|---|---|---|---|---|
"""
    try:
        state = parse_state(text)
        validate_item_links(state, parse_active_items(text))
        validate_transition(state)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(text)
    except (OSError, UnicodeError, PlanStateError) as exc:
        emit("result", "invalid")
        emit("error", str(exc))
        return 4
    emit("result", "initialized")
    emit("plan", str(path))
    emit("plan_id", resolved_plan_id)
    emit("updated_at_utc", updated)
    return 0


def load_plan(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise PlanStateError("PLAN.md not found")
    text = path.read_text(encoding="utf-8")
    return validate_document(path, text)


def validate_document(path: Path, text: str) -> dict[str, str]:
    state = parse_state(text)
    validate_item_links(state, parse_active_items(text))
    validate_transition(state)
    if path.parent.name != state["feature_slug"]:
        raise PlanStateError("feature_slug/path mismatch")
    return state


def canonical_plan(path: Path, root: Path) -> Path:
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise PlanStateError("plan is outside repository") from exc
    if len(relative.parts) != 3 or relative.parts[0] != "features" or relative.name != "PLAN.md":
        raise PlanStateError("plan is outside features/<feature-slug>/PLAN.md")
    return resolved


def atomic_write(path: Path, text: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(path.stat().st_mode)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def checkpoint(
    repo_arg: str,
    plan_arg: str,
    expected_token: str,
    assignments: list[str],
    additions: list[list[str]],
    item_updates: list[list[str]],
    closures: list[str],
) -> int:
    try:
        root, branch, head = git_identity(Path(repo_arg).expanduser().resolve())
        path = canonical_plan(Path(plan_arg).expanduser(), root)
        original = path.read_text(encoding="utf-8")
        original_document_token = document_token(original)
        if not re.fullmatch(r"[0-9a-f]{64}", expected_token):
            raise PlanStateError("invalid checkpoint token")
        if checkpoint_token(original) != expected_token:
            raise PlanStateError("stale checkpoint token; inspect again")
        state = validate_document(path, original)
        stale = freshness_errors(state, root, branch, head, path)
        if stale:
            raise PlanStateError("stale state fields: " + ",".join(stale))

        state_updates = parse_state_updates(assignments)
        items, added = apply_item_operations(parse_active_items(original), additions, item_updates, closures)
        state_updates.update(open_item_state(items))
        updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        state_updates.update(
            repository_root=str(root),
            branch=branch,
            head_sha=head,
            updated_at_utc=updated,
        )
        candidate = replace_state(original, state_updates)
        candidate = replace_active_items(candidate, items)
        candidate_state = validate_document(path, candidate)

        if document_token(path.read_text(encoding="utf-8")) != original_document_token:
            raise PlanStateError("PLAN.md changed during checkpoint; inspect again")
        atomic_write(path, candidate)
    except (OSError, UnicodeError, subprocess.CalledProcessError, PlanStateError) as exc:
        emit("result", "invalid")
        emit("error", str(exc))
        return 4

    emit("result", "checkpointed")
    emit("plan", str(path))
    emit("updated_at_utc", updated)
    emit("checkpoint_token", checkpoint_token(candidate))
    emit("route_target", ROUTE_TARGETS[candidate_state["lifecycle_status"]])
    if added:
        emit("added_items", ",".join(added))
    return 0


def inspect(repo_arg: str, plan_arg: str | None) -> int:
    try:
        root, branch, head = git_identity(Path(repo_arg).expanduser().resolve())
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        emit("result", "invalid")
        emit("error", "repository is not a readable Git worktree")
        return 4

    raw_paths = [Path(plan_arg).expanduser()] if plan_arg else sorted(root.glob("features/**/PLAN.md"))
    records: list[tuple[Path, dict[str, str], str]] = []
    invalid: list[tuple[Path, str]] = []
    for raw_path in raw_paths:
        try:
            path = canonical_plan(raw_path, root)
            text = path.read_text(encoding="utf-8")
            records.append((path, validate_document(path, text), checkpoint_token(text)))
        except (OSError, UnicodeError, PlanStateError) as exc:
            invalid.append((raw_path, str(exc)))

    if invalid:
        emit("result", "invalid")
        for index, (path, error) in enumerate(invalid, start=1):
            emit(f"invalid_{index}", f"{path}|{error}")
        return 4

    active = records if plan_arg else [item for item in records if item[1]["lifecycle_status"] not in TERMINAL]
    if not active:
        emit("result", "none")
        return 2
    if len(active) > 1:
        emit("result", "multiple")
        for index, (path, state, _) in enumerate(active, start=1):
            emit(
                f"candidate_{index}",
                f'{path}|{state["lifecycle_status"]}|{state["current_stage"]}|{state["next_action"]}',
            )
        return 3

    path, state, token = active[0]
    stale = freshness_errors(state, root, branch, head, path)
    plan_only_drift = state["head_sha"] != head and "head_sha" not in stale
    emit("result", "stale" if stale else "selected")
    emit("plan", str(path))
    for key in REQUIRED:
        emit(key, state[key])
    emit("route_target", ROUTE_TARGETS[state["lifecycle_status"]])
    emit("checkpoint_token", token)
    emit("repository_head_sha", head)
    if plan_only_drift:
        emit("plan_only_head_drift", "yes")
    if stale:
        emit("stale_fields", ",".join(stale))
        return 5
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--repo", default=".")
    inspect_parser.add_argument("--plan")
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--repo", default=".")
    init_parser.add_argument("--feature-slug", required=True)
    init_parser.add_argument("--plan-id")
    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_parser.add_argument("--repo", default=".")
    checkpoint_parser.add_argument("--plan", required=True)
    checkpoint_parser.add_argument("--expect-token", required=True)
    checkpoint_parser.add_argument("--set", dest="updates", action="append", default=[])
    checkpoint_parser.add_argument(
        "--add-item",
        action="append",
        nargs=5,
        metavar=("TYPE", "EVIDENCE", "IMPACT", "OWNER", "NEXT_ACTION"),
        default=[],
    )
    checkpoint_parser.add_argument(
        "--update-item",
        action="append",
        nargs=3,
        metavar=("ID", "FIELD", "VALUE"),
        default=[],
    )
    checkpoint_parser.add_argument("--close-item", action="append", default=[])
    args = parser.parse_args()
    if args.command == "init":
        return initialize(args.repo, args.feature_slug, args.plan_id)
    if args.command == "checkpoint":
        return checkpoint(
            args.repo,
            args.plan,
            args.expect_token,
            args.updates,
            args.add_item,
            args.update_item,
            args.close_item,
        )
    return inspect(args.repo, args.plan)


if __name__ == "__main__":
    sys.exit(main())
