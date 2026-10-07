"""Publish the prepared Hard Eng update as its own pull request, merged once its checks pass."""

import json
import re
import subprocess
from pathlib import Path

from gate_config import JsonValue
from shipping import ShippingError, gh, load_policy
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
SKIPPED = {"SKIPPED", "NEUTRAL", "STALE"}
BODY = (
    "Prepared by Hard Eng. It merges by rebase once its checks pass, when update-pr is run "
    "again; a failing check is fixed on this branch before other shipping."
)
GENERATED = re.compile(r"Update Hard Eng to [0-9a-f]+")


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
            "url,title,statusCheckRollup,headRefOid",
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


def check_state(pull: dict[str, JsonValue], required: list[str] | None = None) -> str:
    rollup = pull.get("statusCheckRollup")
    entries: list[dict[str, JsonValue]] = []
    for item in rollup if isinstance(rollup, list) else []:
        if isinstance(item, dict):
            entries.append(item)
    if required:
        named = [e for e in entries if (e.get("name") or e.get("context")) in required]
        pending = len({e.get("name") or e.get("context") for e in named}) < len(
            set(required)
        )
        entries = named
    else:
        pending = not entries
    for entry in entries:
        outcome = entry.get("conclusion") or entry.get("state")
        if outcome in FAILED or (required and outcome in SKIPPED):
            return "failing"
        if entry.get("status", "COMPLETED") != "COMPLETED" or outcome in {
            None,
            "",
            "PENDING",
            "EXPECTED",
        }:
            pending = True
    if not pending and not any(
        (e.get("conclusion") or e.get("state")) == "SUCCESS" for e in entries
    ):
        return "pending"
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
            "opens the PR and merges it once its checks pass; no approval is needed."
        )
    if check_state(pull) == "failing":
        return f"The Hard Eng update PR {pull.get('url')} is failing: fix it first. {fix_steps(root)}"
    return (
        f"The Hard Eng update PR {pull.get('url')} merges once its checks pass: wait for them, run "
        f"`{UPDATE_COMMAND}` to merge it, then rebase this branch on origin/{base}."
    )


def git_lines(root: Path, *args: str) -> list[str] | None:
    done = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    return done.stdout.splitlines() if done.returncode == 0 else None


def replaceable_remote(root: Path, base: str) -> str | None:
    """The remote update tip to lease against, or None after refusing to overwrite someone's fix."""
    tracking = f"+refs/heads/{UPDATE_BRANCH}:refs/remotes/origin/{UPDATE_BRANCH}"
    subprocess.run(
        ["git", "fetch", "--quiet", "origin", tracking], cwd=root, check=False
    )
    remote = f"refs/remotes/origin/{UPDATE_BRANCH}"
    tip = git_lines(root, "rev-parse", "--verify", "--quiet", remote)
    if not tip:
        return ""
    if (
        git_lines(root, "merge-base", "--is-ancestor", tip[0], UPDATE_BRANCH)
        is not None
    ):
        return tip[0]
    subjects = git_lines(
        root,
        "log",
        "--format=%s",
        "--cherry-pick",
        "--right-only",
        "--no-merges",
        f"origin/{base}...{remote}",
    )
    if subjects is not None and all(GENERATED.fullmatch(s) for s in subjects):
        return tip[0]
    print(
        f"origin/{UPDATE_BRANCH} holds commits that are not generated update commits, so it was "
        f"not replaced. Update the branch from the remote first: `git fetch origin {UPDATE_BRANCH}`, "
        f"put those commits on {UPDATE_BRANCH}, then run `{UPDATE_COMMAND}` again."
    )
    return None


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
    lease = replaceable_remote(root, base)
    if lease is None:
        return 1
    expected = f"--force-with-lease=refs/heads/{UPDATE_BRANCH}:{lease}"
    subprocess.run(
        ["git", "push", expected, "origin", UPDATE_BRANCH],
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
    head = (git_lines(root, "rev-parse", f"refs/heads/{UPDATE_BRANCH}") or [""])[0]
    pull = open_pull(root)
    policy = load_policy(root, required=False)
    state = (
        check_state(pull, policy["checks"] if policy else None) if pull else "pending"
    )
    if pull is not None and pull.get("headRefOid") != head:
        state = "pending"
    if state == "passing":
        gh(
            root,
            "pr",
            "merge",
            url,
            "--auto",
            "--rebase",
            "--match-head-commit",
            head,
        )
        print(
            f"Hard Eng update PR {url}: checks passing. Merge requested for {head[:12]}."
        )
        return 0
    print(f"Hard Eng update PR {url}: checks {state}.")
    if state == "failing":
        print(fix_steps(root))
        return 1
    print(
        f"Not merged yet. Run `{UPDATE_COMMAND}` again once the checks pass to merge it."
    )
    return 0
