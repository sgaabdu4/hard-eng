"""The commit author and message check for Claude attribution, which settings can turn off."""

import re
import subprocess
from pathlib import Path

from gate_config import ALL_ZERO_OBJECT_ID

CLAUDE_EMAIL = re.compile(r"noreply@anthropic\.com", re.IGNORECASE)


def validate_attribution(root: Path, base: str | None = None) -> None:
    import plans
    from agent_hooks import attribution_off, reject_attribution

    if (
        not attribution_off(root, "commit")
        or subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
            cwd=root,
            stdout=subprocess.DEVNULL,
            check=False,
        ).returncode
    ):
        return
    point = base or plans.default_branch_point(root) or "HEAD"
    span = "HEAD" if ALL_ZERO_OBJECT_ID.fullmatch(point) else f"{point}..HEAD"
    try:
        log = plans._git_output(root, "log", "--format=%x1e%h%x1f%ae%x1f%ce%n%B", span)
    except subprocess.CalledProcessError as error:
        raise ValueError(
            "Cannot verify commit attribution; fetch or supply a valid Git --base"
        ) from error
    for entry in filter(None, log.split("\x1e")):
        header, _, text = entry.partition("\n")
        revision, *emails = header.split("\x1f")
        if any(CLAUDE_EMAIL.fullmatch(email) for email in emails):
            raise ValueError(f"Commit {revision} has a Claude author or committer")
        reject_attribution(root, "commit", text, f"Commit {revision}")


CLAUDE_EMAIL = re.compile(r"noreply@anthropic\.com", re.IGNORECASE)
