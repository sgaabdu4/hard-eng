"""The passed ship record that the merge hook reads, and the merge method that the record names."""

import json
import subprocess
import time
from pathlib import Path
from typing import Protocol

METHODS = (("squashMergeAllowed", "squash"), ("mergeCommitAllowed", "merge"))
SETTING_NAMES = ("rebaseMergeAllowed", *(name for name, _ in METHODS))


class Pull(Protocol):
    @property
    def head_sha(self) -> str: ...
    @property
    def head_ref(self) -> str: ...
    @property
    def base_ref(self) -> str: ...
    @property
    def rebaseable(self) -> bool | None: ...
    @property
    def default_branch(self) -> str | None: ...


def is_release(pull: Pull, base: str) -> bool:
    """A release pull request merges the base branch itself into another branch."""
    return pull.head_ref == base and pull.base_ref != base


def _contains(root: Path, ancestor: str, commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, commit],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def _remote_tip(root: Path, branch: str) -> str | None:
    done = subprocess.run(
        [
            "git",
            "rev-parse",
            "--verify",
            "-q",
            f"refs/remotes/origin/{branch}^{{commit}}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return done.stdout.strip() if done.returncode == 0 else None


def is_join(root: Path, pull: Pull, default: str) -> bool:
    """The head holds the default branch's tip, which the base lacks; local refs, so fetch first."""
    tip, base_tip = _remote_tip(root, default), _remote_tip(root, pull.base_ref)
    return (
        tip is not None
        and base_tip is not None
        and _contains(root, tip, pull.head_sha)
        and not _contains(root, tip, base_tip)
    )


def route(root: Path, pull: Pull, base: str) -> str | None:
    """release, hotfix or join when the pull request moves work between the base and the default branch; else None."""
    default = pull.default_branch
    if is_release(pull, base) and default in (None, pull.base_ref):
        return "release"
    if default is None or default == base:
        return None
    if pull.base_ref == default and pull.head_ref.startswith("hotfix/"):
        return "hotfix"
    if pull.base_ref == base and is_join(root, pull, default):
        return "join"
    return None


def base_matches(root: Path, pull: Pull, base: str) -> bool:
    return pull.base_ref == base or route(root, pull, base) is not None


def merge_method(root: Path, repository: str, pull: Pull, base: str) -> str:
    """rebase; a merge commit for a release, hotfix or join; or the method a rebase-forbidding repository allows."""
    from shipping import ShippingError, merge_settings

    if route(root, pull, base) is not None:
        return "merge"
    if pull.rebaseable is not False:
        return "rebase"
    try:
        allowed = merge_settings(root, repository, SETTING_NAMES)
    except ShippingError:
        return "rebase"
    if allowed.get("rebaseMergeAllowed") is False:
        for key, method in METHODS:
            if allowed.get(key) is True:
                return method
    return "rebase"


def record_ship(root: Path, number: int, head: str, method: str) -> None:
    """Write the record `ship ready` leaves for the merge hook: head, time, result and method."""
    path = subprocess.run(
        ["git", "rev-parse", "--git-path", "hard-eng/ship"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    folder = root / path
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{number}.json").write_text(
        json.dumps(
            {
                "head": head,
                "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "result": "passed",
                "method": method,
            }
        )
    )


def ship_method(
    root: Path, repository: str, pull: Pull, base: str, stage: str, number: int
) -> str:
    """The merge method for this pull request; the `ready` stage also records it for the merge hook."""
    method = merge_method(root, repository, pull, base)
    if stage == "ready":
        record_ship(root, number, pull.head_sha, method)
    return method
