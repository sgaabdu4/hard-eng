#!/usr/bin/env python3
"""Materialize a claimed ticket's isolated worktree: branch, mirrored PLAN, worktree-local authorization."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DETERMINISTIC_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(DETERMINISTIC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

import checkout_policy
import execution_evidence
from bounded_run import run_captured
from git_env import git_env

ADD_WORKTREE_TIMEOUT = 120
REMOVE_WORKTREE_TIMEOUT = 60
BASE_REF_TIMEOUT = 15
STATUS_TIMEOUT = 30
WRITE_PROBE_TIMEOUT = 1500
WORKTREE_SCRIPT = DETERMINISTIC_SCRIPTS / "worktree.py"


class TicketWorktreeError(RuntimeError):
    pass


def _git(repo: Path, args: list[str], timeout: float) -> tuple[int, str, str]:
    command = ["git", "-C", str(repo), *args]
    result = run_captured(command, timeout, env=git_env())
    return result.returncode, result.stdout.decode("utf-8", "replace"), result.stderr.decode("utf-8", "replace")


def ticket_slug(epic_slug: str, ticket_id: str) -> str:
    return f"{epic_slug}/{ticket_id}"


def worktree_path(repo: Path, epic_slug: str, ticket_id: str) -> Path:
    return repo.parent / f"{repo.name}.worktrees" / epic_slug / ticket_id


def add_worktree(repo: Path, path: Path, branch: str, base_ref: str) -> None:
    returncode, _, stderr = _git(repo, ["worktree", "add", str(path), "-b", branch, base_ref], ADD_WORKTREE_TIMEOUT)
    if returncode != 0:
        raise TicketWorktreeError(f"git worktree add failed for {path}: {stderr.strip() or f'exit {returncode}'}")


def remove_worktree(repo: Path, path: Path, *, force: bool = False) -> None:
    args = ["worktree", "remove", *(["--force"] if force else []), str(path)]
    returncode, _, stderr = _git(repo, args, REMOVE_WORKTREE_TIMEOUT)
    if returncode != 0:
        raise TicketWorktreeError(f"git worktree remove failed for {path}: {stderr.strip() or f'exit {returncode}'}")


def scaffolding_only_changes(worktree_root: Path) -> bool:
    slug = worktree_root.parent.name
    returncode, stdout, stderr = _git(
        worktree_root, ["status", "--porcelain=v1", "-z", "--untracked-files=all"], STATUS_TIMEOUT
    )
    if returncode != 0:
        raise TicketWorktreeError(f"git status failed for {worktree_root}: {stderr.strip() or f'exit {returncode}'}")
    allowed_plan = f"features/{slug}/PLAN.md"
    allowed_prefix = f"features/{slug}/receipts/"
    tokens = stdout.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        if len(token) < 4:
            raise TicketWorktreeError(f"unexpected git status entry: {token!r}")
        paths.append(token[3:])
        if token[0] in "RC":
            if index >= len(tokens) or not tokens[index]:
                raise TicketWorktreeError("git status rename entry is missing its source path")
            paths.append(tokens[index])
            index += 1
    return all(path == allowed_plan or path.startswith(allowed_prefix) for path in paths)


def delete_branch(repo: Path, branch: str, *, force: bool = False) -> None:
    ref = f"refs/heads/{branch}"
    returncode, _, _ = _git(repo, ["rev-parse", "--verify", "--quiet", ref], BASE_REF_TIMEOUT)
    if returncode != 0:
        return
    if not force:
        merged, _, _ = _git(repo, ["merge-base", "--is-ancestor", ref, _default_base_ref(repo)], BASE_REF_TIMEOUT)
        if merged != 0:
            raise TicketWorktreeError(f"branch {branch} holds commits not on the base ref")
    returncode, _, stderr = _git(repo, ["branch", "-D", branch], REMOVE_WORKTREE_TIMEOUT)
    if returncode != 0:
        raise TicketWorktreeError(f"git branch delete failed for {branch}: {stderr.strip() or f'exit {returncode}'}")


def _default_base_ref(repo: Path) -> str:
    returncode, stdout, _ = _git(repo, ["symbolic-ref", "refs/remotes/origin/HEAD"], BASE_REF_TIMEOUT)
    ref = stdout.strip()
    if returncode != 0 or not ref:
        raise TicketWorktreeError("cannot resolve origin/HEAD to a base ref for the ticket worktree")
    return ref


def run_write_probe(worktree_root: Path) -> dict[str, str]:
    command = [
        sys.executable,
        str(WORKTREE_SCRIPT),
        "--repo",
        str(worktree_root),
        "--intent",
        "write",
        "--checkout-choice",
        "auto",
    ]
    try:
        captured = run_captured(command, WRITE_PROBE_TIMEOUT, grace=2, env=git_env())
    except OSError as error:
        raise TicketWorktreeError(f"worktree write probe could not run: {type(error).__name__}") from error
    values: dict[str, str] = {}
    for line in captured.stdout.decode("utf-8", "replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values.setdefault(key, value)
    if values.get("result") != "valid":
        errors: list[str] = []
        index = 1
        while f"error_{index}" in values:
            errors.append(values[f"error_{index}"])
            index += 1
        detail = "; ".join(errors) if errors else f"result={values.get('result', 'unknown')}"
        raise TicketWorktreeError(f"worktree write probe failed: {detail}")
    return values


def mirror_plan(worktree_root: Path, epic_plan_text: str, research_json: bytes | None) -> Path:
    slug = worktree_root.parent.name
    plan_file = worktree_root / "features" / slug / "PLAN.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_bytes(epic_plan_text.encode("utf-8"))
    receipts_dir = plan_file.parent / "receipts"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    if research_json is not None:
        research_file = receipts_dir / "research.json"
        research_file.write_bytes(research_json)
        research_file.chmod(0o600)
    return plan_file


def mint_worktree_authorization(worktree_root: Path, mirrored_plan: Path, *, epic_fingerprint: str) -> None:
    minted_plan_id = execution_evidence.plan_id(mirrored_plan)
    value: dict[str, object] = {
        "allowed": ["approved-build"],
        "approval_digest": execution_evidence.text_digest(f"ticket-worktree-authorization:{epic_fingerprint}"),
        "approved_at": execution_evidence.utc_text(execution_evidence.utc_now()),
        "effect": "build the claimed ticket within its mirrored epic scope",
        "mode": "standard",
        "plan_fingerprint": execution_evidence.require_digest(epic_fingerprint, "epic fingerprint"),
        "plan_id": minted_plan_id,
        "schema_version": 2,
        "stop_before": execution_evidence.STOP_BEFORE,
        "target": minted_plan_id,
    }
    execution_evidence.safe_receipt_json(
        worktree_root, execution_evidence.receipt_path(mirrored_plan, "authorization.json"), value
    )


def materialize(
    repo: Path, epic_plan: Path, epic_plan_text: str, ticket_id: str, epic_slug: str, *, epic_fingerprint: str
) -> dict[str, str]:
    primary = checkout_policy.primary_checkout(repo)
    path = worktree_path(primary, epic_slug, ticket_id)
    branch_name = f"ticket/{ticket_slug(epic_slug, ticket_id)}"
    base_ref = _default_base_ref(primary)
    add_worktree(primary, path, branch_name, base_ref)
    run_write_probe(path)
    research_path = execution_evidence.receipt_path(epic_plan, "research.json")
    research_json = research_path.read_bytes() if research_path.is_file() and not research_path.is_symlink() else None
    mirrored_plan = mirror_plan(path, epic_plan_text, research_json)
    mint_worktree_authorization(path, mirrored_plan, epic_fingerprint=epic_fingerprint)
    return {"worktree": str(path), "branch": branch_name}
