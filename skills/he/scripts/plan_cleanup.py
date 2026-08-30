#!/usr/bin/env python3
"""Exact-inventory cleanup for tracked terminal and invalid legacy PLAN files."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from evidence_lib import invalidate_direct_receipt
from lifecycle_excludes import exclude_terminal_artifacts
from plan_paths import safe_plan_path
from plan_sections import PlanError, token_for
from safe_plan_io import _git, consume_if_unchanged, read_snapshot, replace_if_unchanged, repo_root

SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup import safe_file

ITEM = re.compile(r"(features/[a-z0-9]+(?:-[a-z0-9]+)*/PLAN\.md)=(?:sha256:)?([0-9a-f]{64})")
STATUS = re.compile(r"(?m)^- lifecycle_status = ([a-z-]+)$")
TERMINAL = {"shipped", "cancelled"}
STATE_START = "<!-- hard-eng-state:v1 -->"
STATE_END = "<!-- /hard-eng-state -->"
MAX_DRAFT_BYTES = 1024 * 1024


class CleanupCandidate(TypedDict):
    path: Path
    relative: Path
    before: bytes
    before_hash: str
    mode: int
    source_status: str
    validation_error: str
    terminal: bytes
    terminal_hash: str
    terminal_status: str
    route: str


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _action_digest(repo: Path, decision: str, items: list[tuple[Path, str]]) -> str:
    payload = {
        "decision": decision,
        "items": [{"path": path.as_posix(), "sha256": expected} for path, expected in items],
        "operation": "hard-eng-plan-cleanup-v1",
        "repo": str(repo),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return _digest(encoded)


def _parse_items(values: list[str]) -> list[tuple[Path, str]]:
    parsed: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for value in values:
        match = ITEM.fullmatch(value)
        if match is None:
            raise PlanError("--item must be features/<slug>/PLAN.md=SHA256")
        relative, digest = Path(match.group(1)), "sha256:" + match.group(2)
        if relative in seen:
            raise PlanError(f"duplicate cleanup item: {relative}")
        seen.add(relative)
        parsed.append((relative, digest))
    return parsed


def _lock(repo: Path):
    identity = hashlib.sha256(str(repo).encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / f"hard-eng-plan-cleanup-{identity}.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    metadata = os.fstat(descriptor)
    if metadata.st_uid != os.getuid() or not stat.S_ISREG(metadata.st_mode):
        os.close(descriptor)
        raise PlanError("cleanup lock is not a private current-user file")
    return descriptor


def _head_preimage(repo: Path, relative: Path, current: bytes) -> None:
    result = _git(repo, "show", f"HEAD:{relative.as_posix()}", check=False, timeout=10)
    if result.returncode != 0 or result.stdout != current:
        raise PlanError(f"tracked HEAD preimage mismatch: {relative}")


def _git_common_dir(repo: Path) -> Path:
    result = _git(repo, "rev-parse", "--git-common-dir", timeout=10)
    value = Path(result.stdout.decode("utf-8", "replace").strip())
    return (value if value.is_absolute() else repo / value).resolve()


def _note_path(repo: Path, action: str) -> Path:
    owner = _git_common_dir(repo) / "hard-eng"
    try:
        owner.mkdir(mode=0o700)
    except FileExistsError:
        pass
    metadata = os.lstat(owner)
    if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode) or metadata.st_uid != os.getuid():
        raise PlanError("Git-private recovery directory is unsafe")
    return owner / f"plan-cleanup-{action.removeprefix('sha256:')[:20]}.json"


def _note_bytes(note: dict[str, object]) -> bytes:
    return (json.dumps(note, indent=2, sort_keys=True) + "\n").encode()


def _write_note(path: Path, note: dict[str, object], previous: bytes | None = None) -> bytes:
    replacement = _note_bytes(note)
    if previous is None:
        if path.exists() or path.is_symlink():
            raise PlanError(f"recovery note already exists: {path}")
        safe_file.create_path(path, replacement, 0o600)
    else:
        safe_file.replace_path_if_unchanged(path, previous, 0o600, replacement, replacement_mode=0o600)
    return replacement


def _read_draft(value: str, repo: Path) -> str:
    path = Path(value)
    if not path.is_absolute():
        raise PlanError("--candidate must be an absolute staging path")
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(repo)
    except ValueError:
        pass
    else:
        raise PlanError("--candidate must stay outside the repository")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise PlanError("draft candidate must be a current-user regular file")
        data = os.read(descriptor, MAX_DRAFT_BYTES + 1)
        if len(data) > MAX_DRAFT_BYTES or os.read(descriptor, 1):
            raise PlanError("draft candidate exceeds 1 MiB")
    finally:
        os.close(descriptor)
    try:
        return data.decode("utf-8")
    except UnicodeError as error:
        raise PlanError("draft candidate must be UTF-8") from error


def _state_block(text: str) -> str:
    if text.count(STATE_START) != 1 or text.count(STATE_END) != 1:
        raise PlanError("draft requires exactly one v1 State block")
    start = text.index(STATE_START)
    end = text.index(STATE_END, start) + len(STATE_END)
    return text[start:end]


def draft(args, validate_plan: Callable[..., dict[str, str]], emit_plan: Callable[..., None]) -> None:
    repo = repo_root(args.repo)
    path = safe_plan_path(repo, args.plan)
    descriptor = _lock(repo)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        relative = path.relative_to(repo)
        before, mode = read_snapshot(repo, relative)
        current = before.decode("utf-8")
        state = validate_plan(current)
        if state["lifecycle_status"] in TERMINAL:
            raise PlanError("terminal PLAN content is immutable")
        actual_token = token_for(current)
        if args.expect_token != actual_token:
            raise PlanError(f"stale plan token; expected current token {actual_token}")
        candidate = _read_draft(args.candidate, repo)
        if candidate.splitlines()[:1] != current.splitlines()[:1] or _state_block(candidate) != _state_block(current):
            raise PlanError("draft candidate must preserve the exact title and State block")
        updated = validate_plan(candidate)
        replace_if_unchanged(repo, relative, before, mode, candidate.encode("utf-8"))
        emit_plan(path, candidate, updated)
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def run(
    args,
    validate_plan: Callable[..., dict[str, str]],
    render_template: Callable[[str, str], str],
    render_state: Callable[[str, dict[str, str]], str],
) -> None:
    repo = repo_root(args.repo)
    decision = args.decision.strip()
    if not decision or "\n" in args.decision or "\r" in args.decision:
        raise PlanError("--decision must be one nonempty line")
    items = _parse_items(args.item)
    action = _action_digest(repo, decision, items)
    candidates: list[CleanupCandidate] = []
    descriptor = _lock(repo)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        for relative, expected in items:
            path = safe_plan_path(repo, repo / relative)
            data, mode = read_snapshot(repo, relative)
            actual = _digest(data)
            if actual != expected:
                raise PlanError(f"cleanup hash mismatch: {relative}; expected {expected}; actual {actual}")
            _head_preimage(repo, relative, data)
            try:
                text = data.decode("utf-8")
            except UnicodeError as error:
                raise PlanError(f"PLAN is not UTF-8: {relative}") from error
            source_match = STATUS.search(text)
            source_status = source_match.group(1) if source_match else "unknown"
            validation_error = "none"
            try:
                state = validate_plan(text, allow_legacy_missing_ux_reference=True)
            except PlanError as error:
                validation_error = str(error)
                slug = relative.parts[1]
                terminal_text = render_template(slug, f"legacy-cleanup-{actual[-12:]}")
                terminal_text = render_state(
                    terminal_text,
                    {
                        "lifecycle_status": "cancelled",
                        "approval_status": "pending",
                        "approval_fingerprint": "none",
                        "approval_provenance": "none",
                        "green_artifact": "none",
                        "active_slice": "none",
                        "completed_slices": "none",
                        "next_action": f"Cancelled by exact user decision: {decision}",
                        "replan_reason": "none",
                    },
                )
                terminal_state = validate_plan(terminal_text)
                terminal = terminal_text.encode()
                route = "invalid->cancelled->removed"
            else:
                if state["lifecycle_status"] in TERMINAL:
                    terminal_state = state
                    terminal = data
                    route = "terminal->removed"
                else:
                    terminal_text = render_state(
                        text,
                        {
                            "lifecycle_status": "cancelled",
                            "green_artifact": "none",
                            "active_slice": "none",
                            "next_action": f"Cancelled by exact user decision: {decision}",
                        },
                    )
                    terminal_state = validate_plan(terminal_text)
                    terminal = terminal_text.encode()
                    route = "nonterminal->cancelled->removed"
            candidates.append(
                {
                    "path": path,
                    "relative": relative,
                    "before": data,
                    "before_hash": actual,
                    "mode": mode,
                    "source_status": source_status,
                    "validation_error": validation_error,
                    "terminal": terminal,
                    "terminal_hash": _digest(terminal),
                    "terminal_status": terminal_state["lifecycle_status"],
                    "route": route,
                }
            )
        needs_cancel = any(row["route"] != "terminal->removed" for row in candidates)
        if not args.apply:
            print("result=preview")
            print(f"action_digest={action}")
            for row in candidates:
                print(f"item={row['relative']}|{row['before_hash']}|{row['route']}")
            print(f"requires_confirm_cancel={'yes' if needs_cancel else 'no'}")
            print("requires_confirm_delete=yes")
            return
        if not args.confirm_delete:
            raise PlanError("cleanup apply requires --confirm-delete")
        if needs_cancel and not args.confirm_cancel:
            raise PlanError("invalid legacy cleanup requires --confirm-cancel")
        entries = [
            {
                "before_hash": row["before_hash"],
                "mode": oct(int(row["mode"])),
                "path": str(row["relative"]),
                "restore_command": f"{'git'} {'restore'} --source=HEAD -- {row['relative']}",
                "route": row["route"],
                "source_status": row["source_status"],
                "terminal_hash": row["terminal_hash"],
                "terminal_status": row["terminal_status"],
                "validation_error": row["validation_error"],
            }
            for row in candidates
        ]
        note = {
            "action_digest": action,
            "completed": [],
            "decision": decision,
            "entries": entries,
            "operation": "hard-eng-plan-cleanup",
            "repo": str(repo),
            "schema_version": 1,
            "status": "running",
        }
        note_path = _note_path(repo, action)
        note_preimage = _write_note(note_path, note)
        try:
            invalidate_direct_receipt(repo)
            for row in candidates:
                relative = row["relative"]
                current = row["before"]
                if row["terminal"] != current:
                    replace_if_unchanged(repo, relative, current, int(row["mode"]), row["terminal"])
                    current, current_mode = read_snapshot(repo, relative)
                    if current != row["terminal"] or current_mode != row["mode"]:
                        raise PlanError(f"terminal migration verification failed: {relative}")
                exclude_terminal_artifacts(repo, row["path"], str(row["terminal_status"]))
                consume_if_unchanged(repo, relative, current, int(row["mode"]))
                note["completed"].append(str(relative))
                note_preimage = _write_note(note_path, note, note_preimage)
        except BaseException:
            note["status"] = "partial" if note["completed"] else "failed"
            _write_note(note_path, note, note_preimage)
            raise
        note["status"] = "completed"
        _write_note(note_path, note, note_preimage)
        print("result=removed")
        print(f"action_digest={action}")
        print(f"removed_count={len(candidates)}")
        print(f"recovery_note={note_path}")
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)
