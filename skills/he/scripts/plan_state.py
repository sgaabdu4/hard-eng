#!/usr/bin/env python3
"""Initialize, inspect, and atomically checkpoint Hard Eng PLAN.md state."""
from __future__ import annotations
import argparse
import hashlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from plan_contract import (  # noqa: E402
    ITEM_KEYS,
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
from plan_items import (  # noqa: E402
    apply_item_operations,
    apply_learning_operations,
    learning_pass_binding,
    open_item_state,
    parse_active_items,
    parse_learning_candidates,
    prune_closed_records,
    replace_active_items,
    replace_learning_candidates,
    validate_learning_receipts_current,
)
from plan_reconcile import reconcile_head as reconcile_committed_head  # noqa: E402
from plan_freshness import snapshot_drift, snapshot_reconciliation  # noqa: E402
from plan_transfer import git_location, plan_writer_lock, transfer_plan  # noqa: E402
from safe_repo_io import atomic_write as repo_write, snapshot as repo_snapshot  # noqa: E402
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

def replace_state(text: str, updates: dict[str, str]) -> str:
    lines = text.splitlines()
    start = next((i + 1 for i, line in enumerate(lines) if line.strip() == "## State"), -1)
    if start < 0:
        raise PlanStateError("missing ## State")
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    counts = {key: 0 for key in updates}
    for index in range(start, end):
        line = lines[index]
        match = STATE_LINE.fullmatch(line.strip())
        if match and match.group(1) in updates:
            key = match.group(1)
            lines[index] = f"- {key} = {updates[key]}"
            counts[key] += 1
    missing = [key for key, count in counts.items() if count != 1]
    if missing:
        raise PlanStateError("state replacement count invalid: " + ",".join(missing))
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

def document_token(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def checkpoint_token(text: str) -> str:
    state = parse_state(text)
    items = parse_active_items(text)
    candidates = parse_learning_candidates(text)
    material = "\n".join(
        [*(f"{key}={state[key]}" for key in REQUIRED), *("|".join(row) for row in items.values()),
         *("|".join(row) for row in candidates.values())]
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


def validated_learning_transfers(
    root: Path, source: Path, source_state: dict[str, str], source_candidates,
    branch: str, head: str, operations: list[list[str]],
) -> list[list[str]]:
    receipts = []
    for candidate_id, destination_arg, destination_candidate_id in operations:
        source_row = source_candidates.get(candidate_id)
        if source_row is None or source_row[8] != "open":
            raise PlanStateError("learning transfer requires an open source candidate")
        destination = canonical_plan(Path(destination_arg).expanduser(), root)
        if destination == source:
            raise PlanStateError("learning transfer destination must differ from source PLAN")
        destination_text = destination.read_text(encoding="utf-8")
        destination_state = validate_document(destination, destination_text)
        if stale := freshness_errors(destination_state, root, branch, head, destination):
            raise PlanStateError("stale learning transfer destination: " + ",".join(stale))
        destination_candidates = parse_learning_candidates(destination_text)
        row = destination_candidates.get(destination_candidate_id)
        if row is None or row[8] != "open":
            raise PlanStateError("learning transfer requires an open destination candidate")
        expected_source = f"TRANSFER: {source_state['plan_id']}/{candidate_id}"
        if (
            row[1] != source_row[1]
            or row[2] != expected_source
            or row[3] != source_row[3]
            or row[4] != source_row[4]
            or row[6] != source_row[6]
        ):
            raise PlanStateError("learning transfer destination does not match source candidate")
        receipts.append([candidate_id, f"TRANSFER: {destination_state['plan_id']}/{destination_candidate_id}"])
    return receipts


def freshness_errors(state: dict[str, str], root: Path, branch: str, head: str, plan: Path) -> list[str]:
    errors: list[str] = []
    if Path(state["repository_root"]).expanduser().resolve() != root:
        errors.append("repository_root")
    if state["branch"] != branch:
        errors.append("branch")
    if state["head_sha"] != head and not plan_only_head_drift(state, root, head, plan):
        errors.append("head_sha")
    if state["base_sha"] != "UNBORN":
        exists = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f'{state["base_sha"]}^{{commit}}'],
            capture_output=True,
        )
        ancestor = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", state["base_sha"], head],
            capture_output=True,
        )
        if exists.returncode != 0 or head == "UNBORN" or ancestor.returncode != 0:
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

## Learning Candidates
| ID | Trigger | Source | Evidence | Cause | Owner | Required proof | Resolution | Status |
|---|---|---|---|---|---|---|---|---|
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
    candidates = parse_learning_candidates(text)
    validate_item_links(state, items)
    validate_transition(state)
    if state["lifecycle_status"] in {"green", "shipping", "shipped"}:
        validate_audit_reaudit_complete(items, state["snapshot_id"])
        validate_learning_receipts_current(candidates, state["snapshot_id"], state["artifact_id"])
    if state["lifecycle_status"] == "shipped" and any(row[8] == "open" for row in candidates.values()):
        raise PlanStateError("shipped state has open learning candidate")
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

def reconcile_head(repo_arg: str, plan_arg: str, expected_token: str) -> int:
    return reconcile_committed_head(
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
    learning_additions: list[list[str]] | None = None,
    learning_resolutions: list[list[str]] | None = None,
    learning_transfers: list[list[str]] | None = None,
    prune_closed: bool = False,
    learning_refreshes: list[list[str]] | None = None,
) -> int:
    try:
        root, branch, head = git_identity(Path(repo_arg).expanduser().resolve())
        path = canonical_plan(Path(plan_arg).expanduser(), root)
        relative = path.relative_to(root)
        original_bytes, plan_mode = repo_snapshot(root, relative, "PLAN")
        original = original_bytes.decode("utf-8")
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
        current_snapshot = repository_snapshot_id(root)
        current_artifact = repository_artifact_id(root)
        state_updates.update(snapshot_reconciliation(state, current_snapshot, current_artifact))
        items, added = apply_item_operations(parse_active_items(original), additions, item_updates, closures)
        source_candidates = parse_learning_candidates(original)
        target_snapshot = state_updates.get("snapshot_id", state["snapshot_id"])
        target_artifact = state_updates.get("artifact_id", state["artifact_id"])
        proof_snapshot = current_snapshot if target_snapshot == "none" else target_snapshot
        proof_artifact = current_artifact if target_artifact == "none" else target_artifact
        candidates, added_learning, resolved_learning, refreshed_learning = apply_learning_operations(
            source_candidates, learning_additions or [], learning_resolutions or [],
            validated_learning_transfers(
                root, path, state, source_candidates, branch, head, learning_transfers or []
            ),
            learning_refreshes or [], proof_snapshot, proof_artifact,
        )
        if prune_closed:
            items, candidates = prune_closed_records(items, candidates, proof_snapshot, proof_artifact)
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
        candidate = replace_learning_candidates(candidate, candidates)
        candidate_state = validate_document(path, candidate)
        validate_state_change(state, candidate_state)

        current = repo_snapshot(root, relative, "PLAN")[0].decode("utf-8")
        if document_token(current) != original_document_token:
            raise PlanStateError("PLAN.md changed during checkpoint; inspect again")
        repo_write(root, relative, candidate.encode("utf-8"), plan_mode)
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
    if added_learning:
        emit("added_learning", ",".join(added_learning))
    if resolved_learning:
        emit("resolved_learning", ",".join(resolved_learning))
    if refreshed_learning:
        emit("refreshed_learning", ",".join(refreshed_learning))
    if prune_closed:
        emit("pruned_closed", "yes")
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
    reconcile_parser = subparsers.add_parser("reconcile-head")
    reconcile_parser.add_argument("--repo", default=".")
    reconcile_parser.add_argument("--plan", required=True)
    reconcile_parser.add_argument("--expect-token", required=True)
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
    checkpoint_parser.add_argument(
        "--add-learning", action="append", nargs=6,
        metavar=("TRIGGER", "SOURCE", "EVIDENCE", "CAUSE", "OWNER", "REQUIRED_PROOF"), default=[]
    )
    checkpoint_parser.add_argument(
        "--resolve-learning", action="append", nargs=2,
        metavar=("ID", "RESOLUTION"), default=[]
    )
    checkpoint_parser.add_argument(
        "--transfer-learning", action="append", nargs=3,
        metavar=("ID", "DESTINATION_PLAN", "DESTINATION_ID"), default=[]
    )
    checkpoint_parser.add_argument(
        "--refresh-learning", action="append", nargs=2,
        metavar=("ID", "RESOLUTION"), default=[]
    )
    checkpoint_parser.add_argument("--prune-closed", action="store_true")
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
    if args.command == "reconcile-head":
        return reconcile_head(args.repo, args.plan, args.expect_token)
    if args.command == "checkpoint":
        return checkpoint(
            args.repo,
            args.plan,
            args.expect_token,
            args.updates,
            args.add_item,
            args.update_item,
            args.close_item,
            args.add_learning,
            args.resolve_learning,
            args.transfer_learning,
            args.prune_closed,
            args.refresh_learning,
        )
    return inspect(args.repo, args.plan)


if __name__ == "__main__":
    sys.exit(main())
