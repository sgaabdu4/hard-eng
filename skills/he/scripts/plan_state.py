#!/usr/bin/env python3
"""Initialize, inspect, and atomically checkpoint Hard Eng PLAN.md state."""
from __future__ import annotations
import argparse
import hashlib
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from plan_contract import (  # noqa: E402
    ITEM_FIELD_INDEX,
    ITEM_HEADER,
    ITEM_KEYS,
    ITEM_STATUS,
    LIFECYCLE,
    MUTABLE_STATE_KEYS,
    PLAN_STAGES,
    REQUIRED,
    ROUTE_TARGETS,
    SLUG,
    STATE_LINE,
    TERMINAL,
    PlanStateError,
    validate_state_change,
    validate_audit_items,
    validate_audit_reaudit_complete,
    validate_transition,
    validate_values,
)
from plan_adopt import adopt_head as adopt_committed_head  # noqa: E402
from plan_freshness import snapshot_drift, snapshot_reconciliation  # noqa: E402
from plan_transfer import atomic_write as atomic_write_bytes, git_location, plan_writer_lock, transfer_plan  # noqa: E402
from repository_snapshot import artifact_id as repository_artifact_id, snapshot_id as repository_snapshot_id  # noqa: E402
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
    validate_audit_items(items)
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


def locked_plan_writer(action):
    def locked(repo_arg, *args, **kwargs):
        try:
            root, _, _ = git_identity(Path(repo_arg).expanduser().resolve())
            with plan_writer_lock(git_location(root, "--git-common-dir")):
                return action(repo_arg, *args, **kwargs)
        except (OSError, subprocess.CalledProcessError, PlanStateError) as exc:
            emit("result", "invalid")
            emit("error", str(exc))
            return 4
    return locked


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
- state_version = 3
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
- active_slice = none
- slice_count = none
- completed_slices = none
- build_round = 0
- snapshot_id = none
- artifact_id = none
- build_axes = none
- build_readiness = none
- build_evidence = none

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


def slice_inventory(text: str) -> tuple[str, ...]:
    lines = text.splitlines()
    headings = [index for index, line in enumerate(lines) if line.strip() == "## Slices"]
    if not headings:
        return ()
    if len(headings) != 1:
        raise PlanStateError("duplicate ## Slices")
    table: list[str] = []
    for line in lines[headings[0] + 1 :]:
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            table.append(line.strip())
        elif table:
            break
    if len(table) < 2:
        raise PlanStateError("Slices requires one inventory table")
    cells = lambda line: tuple(cell.strip() for cell in line.strip("|").split("|"))
    if not cells(table[0]) or cells(table[0])[0] != "ID":
        raise PlanStateError("Slices inventory requires ID as the first column")
    ids = tuple(cells(line)[0] for line in table[2:])
    if any(not re.fullmatch(r"S-[1-9][0-9]*", item) for item in ids):
        raise PlanStateError("Slices inventory has invalid ID")
    return ids


def validate_document(path: Path, text: str) -> dict[str, str]:
    state = parse_state(text)
    items = parse_active_items(text)
    validate_item_links(state, items)
    validate_transition(state)
    if state["lifecycle_status"] in {"green", "shipping", "learning", "shipped"}:
        validate_audit_reaudit_complete(items)
    if state["slice_count"] != "none":
        count = int(state["slice_count"])
        expected = tuple(f"S-{index}" for index in range(1, count + 1))
        if slice_inventory(text) != expected:
            raise PlanStateError("slice_count differs from Slices inventory")
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


def transfer(
    repo_arg: str,
    destination_arg: str,
    plan_arg: str,
    expected_token: str,
    includes: list[str],
) -> int:
    return transfer_plan(
        repo_arg,
        destination_arg,
        plan_arg,
        expected_token,
        includes,
        git_identity=git_identity,
        canonical_plan=canonical_plan,
        checkpoint_token=checkpoint_token,
        document_token=document_token,
        validate_document=validate_document,
        freshness_errors=freshness_errors,
        replace_state=replace_state,
        emit=emit,
    )

@locked_plan_writer
def adopt_head(repo_arg: str, plan_arg: str, expected_token: str) -> int:
    return adopt_committed_head(
        repo_arg,
        plan_arg,
        expected_token,
        git_identity=git_identity,
        canonical_plan=canonical_plan,
        checkpoint_token=checkpoint_token,
        document_token=document_token,
        validate_document=validate_document,
        validate_state_change=validate_state_change,
        replace_state=replace_state,
        emit=emit,
    )


@locked_plan_writer
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
        state_updates.update(
            snapshot_reconciliation(state, repository_snapshot_id(root), repository_artifact_id(root))
        )
        items, added = apply_item_operations(parse_active_items(original), additions, item_updates, closures)
        state_updates.update(open_item_state(items))
        updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        recorded_head = (
            state["head_sha"]
            if state["head_sha"] != head and plan_only_head_drift(state, root, head, path)
            else head
        )
        state_updates.update(
            repository_root=str(root),
            branch=branch,
            head_sha=recorded_head,
            updated_at_utc=updated,
        )
        candidate = replace_state(original, state_updates)
        candidate = replace_active_items(candidate, items)
        candidate_state = validate_document(path, candidate)
        validate_state_change(state, candidate_state)

        if document_token(path.read_text(encoding="utf-8")) != original_document_token:
            raise PlanStateError("PLAN.md changed during checkpoint; inspect again")
        atomic_write_bytes(path, candidate.encode("utf-8"), stat.S_IMODE(path.stat().st_mode))
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
    if snapshot_drift(state, repository_snapshot_id(root), repository_artifact_id(root)):
        stale.append("snapshot_id")
    plan_only_drift = state["head_sha"] != head and "head_sha" not in stale
    emit("result", "stale" if stale else "selected")
    emit("plan", str(path))
    for key in REQUIRED:
        emit(key, state[key])
    emit("route_target", "$he-build" if "snapshot_id" in stale else ROUTE_TARGETS[state["lifecycle_status"]])
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
    transfer_parser = subparsers.add_parser("transfer")
    transfer_parser.add_argument("--repo", default=".")
    transfer_parser.add_argument("--to-repo", required=True)
    transfer_parser.add_argument("--plan", required=True)
    transfer_parser.add_argument("--expect-token", required=True)
    transfer_parser.add_argument("--include", action="append", default=[])
    adopt_parser = subparsers.add_parser("adopt-head")
    adopt_parser.add_argument("--repo", default=".")
    adopt_parser.add_argument("--plan", required=True)
    adopt_parser.add_argument("--expect-token", required=True)
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
    if args.command == "transfer":
        return transfer(
            args.repo,
            args.to_repo,
            args.plan,
            args.expect_token,
            args.include,
        )
    if args.command == "adopt-head":
        return adopt_head(args.repo, args.plan, args.expect_token)
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
