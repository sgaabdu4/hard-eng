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


def is_release(pull: Pull, base: str) -> bool:
    """A release pull request merges the base branch itself into another branch."""
    return pull.head_ref == base and pull.base_ref != base


def base_matches(pull: Pull, base: str) -> bool:
    return pull.base_ref == base or is_release(pull, base)


def merge_method(root: Path, repository: str, pull: Pull, base: str) -> str:
    """rebase; a merge commit for a release; or the method a rebase-forbidding repository allows."""
    from shipping import ShippingError, merge_settings

    if is_release(pull, base):
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
