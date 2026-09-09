"""Format the dirty-paths note for the project gate's mutated-tree error."""

from __future__ import annotations

from pathlib import Path

from bounded_run import run_captured
from git_env import git_env
from source_tree_coordination import remaining


def _dirty_paths_note(repo: Path, deadline: float | None) -> str:
    """List dirty paths for the mutated-tree error; "" if unavailable.

    Mirrors `tree_fingerprint`'s own path set (tracked/untracked plus
    `.worktreeinclude`-required ignored paths) since plain porcelain status
    hides the latter, which is where a required ignored file would go quiet.
    """
    try:
        status = run_captured(
            ["git", "-C", str(repo), "status", "--porcelain"],
            remaining(deadline, "while listing dirty paths") if deadline else 20,
            env=git_env(),
        )
        if status.returncode != 0:
            return ""
        paths = [line[3:].strip() for line in status.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
        include = repo / ".worktreeinclude"
        if include.is_file():
            for entry in include.read_text(encoding="utf-8").splitlines():
                entry = entry.strip()
                if not entry or entry.startswith("#"):
                    continue
                ignored = run_captured(
                    ["git", "-C", str(repo), "ls-files", "--others", "--ignored", "--exclude-standard", "--", entry],
                    remaining(deadline, "while listing dirty paths") if deadline else 20,
                    env=git_env(),
                )
                if ignored.returncode == 0:
                    paths.extend(
                        path for path in ignored.stdout.decode("utf-8", "replace").splitlines() if path.strip()
                    )
    except Exception:
        return ""
    paths = sorted(dict.fromkeys(paths))
    if not paths:
        return ""
    shown = ", ".join(paths[:10])
    if len(paths) > 10:
        shown += f", +{len(paths) - 10} more"
    return (
        f"; dirty_paths=[{shown}] may be concurrent uncommitted work from another agent"
        " — do not restore, overwrite, or delete them"
    )
