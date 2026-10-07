"""Publish the prepared Hard Eng update as its own auto-merging pull request."""

import json
import subprocess
from pathlib import Path

from gate_config import JsonValue
from shipping import ShippingError, gh
from update_runner import (
    UPDATE_BRANCH,
    UPDATE_COMMAND,
    branch_worktree,
    fetch_base,
    installed_revision,
    last_result,
    locked_update,
    revision_at,
    update_base,
)

FAILED = {
    "FAILURE",
    "TIMED_OUT",
    "CANCELLED",
    "ACTION_REQUIRED",
    "STARTUP_FAILURE",
    "ERROR",
}
BODY = (
    "Prepared by Hard Eng. It merges by rebase on its own once the required checks pass; "
    "a failing check is fixed on this branch before other shipping."
)


def open_pull(root: Path) -> dict[str, JsonValue] | None:
    rows = json.loads(
        gh(
            root,
            "pr",
            "list",
            "--head",
            UPDATE_BRANCH,
            "--state",
            "open",
            "--json",
            "url,title,statusCheckRollup",
            "--limit",
            "1",
        )
    )
    if not isinstance(rows, list):
        raise ShippingError("update PR query must return a list")
    if not rows:
        return None
    if not isinstance(rows[0], dict):
        raise ShippingError("update PR must be an object")
    return rows[0]


def check_state(pull: dict[str, JsonValue]) -> str:
    rollup = pull.get("statusCheckRollup")
    entries: list[JsonValue] = rollup if isinstance(rollup, list) else []
    pending = not entries
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        outcome = entry.get("conclusion") or entry.get("state")
        if outcome in FAILED:
            return "failing"
        if entry.get("status", "COMPLETED") != "COMPLETED" or outcome in {
            None,
            "",
            "PENDING",
            "EXPECTED",
        }:
            pending = True
    return "pending" if pending else "passing"


def fix_steps(root: Path) -> str:
    existing = branch_worktree(root)
    if existing is not None:
        where = f"in {existing}"
    else:
        path = root.parent / f"{root.name}-hard-eng-update"
        where = f"in its own worktree (`git worktree add {path} {UPDATE_BRANCH}`)"
    return (
        f"Fix its checks on branch {UPDATE_BRANCH} {where}, commit there, then run "
        f"`{UPDATE_COMMAND}` from that worktree to push the fix."
    )


def next_step(root: Path) -> str:
    """What to do about a stale install before shipping, from the remote base and the update PR."""
    try:
        base = update_base(root)
        landed = revision_at(root, fetch_base(root, base))
        if landed is not None and landed != installed_revision(root):
            return (
                f"The update is already on {base}: run `git fetch origin {base}` and rebase this "
                f"branch on origin/{base}, then continue."
            )
        pull = open_pull(root)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        return f"The update PR could not be read ({error}); run `{UPDATE_COMMAND}`."
    if pull is None:
        return (
            f"No Hard Eng update PR is open: run `{UPDATE_COMMAND}`. It pushes {UPDATE_BRANCH}, "
            "opens the PR and turns on auto-merge; no approval is needed."
        )
    if check_state(pull) == "failing":
        return f"The Hard Eng update PR {pull.get('url')} is failing: fix it first. {fix_steps(root)}"
    return (
        f"The Hard Eng update PR {pull.get('url')} merges by itself once its checks pass: wait for "
        f"it, then rebase this branch on origin/{base}."
    )


def publish(root: Path) -> int:
    base = update_base(root)
    landed = revision_at(root, fetch_base(root, base))
    revision = revision_at(root, f"refs/heads/{UPDATE_BRANCH}")
    if revision is None:
        print(locked_update(root))
        revision = revision_at(root, f"refs/heads/{UPDATE_BRANCH}")
    if revision is None or revision == landed:
        print(
            f"Nothing to publish: Hard Eng is current on {base}. Last update result: {last_result(root)}"
        )
        return 0
    tracking = f"+refs/heads/{UPDATE_BRANCH}:refs/remotes/origin/{UPDATE_BRANCH}"
    subprocess.run(
        ["git", "fetch", "--quiet", "origin", tracking], cwd=root, check=False
    )
    subprocess.run(
        ["git", "push", "--force-with-lease", "origin", UPDATE_BRANCH],
        cwd=root,
        check=True,
    )
    title = f"Update Hard Eng to {revision[:12]}"
    pull = open_pull(root)
    if pull is None:
        created = gh(
            root,
            "pr",
            "create",
            "--base",
            base,
            "--head",
            UPDATE_BRANCH,
            "--title",
            title,
            "--body",
            BODY,
        )
        url = created.strip().splitlines()[-1]
    else:
        url = str(pull["url"])
        if pull.get("title") != title:
            gh(root, "pr", "edit", url, "--title", title)
    gh(root, "pr", "merge", url, "--auto", "--rebase")
    pull = open_pull(root)
    state = check_state(pull) if pull else "pending"
    print(
        f"Hard Eng update PR {url}: checks {state}. Auto-merge is on; it merges by rebase once required checks pass."
    )
    if state == "failing":
        print(fix_steps(root))
        return 1
    return 0
