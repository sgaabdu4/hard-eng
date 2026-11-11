"""The rules for the text of a pull request body."""

from __future__ import annotations

import json
import re
from pathlib import Path

UNDO_LINE = re.compile(r"^[ \t]*Undo:[ \t]*\S", re.MULTILINE)
MERMAID_BLOCK = re.compile(r"^[ \t]*```[ \t]*mermaid\b", re.MULTILINE)
NOT_CHECKED_LINE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?Not checked:(.*)$", re.MULTILINE)
EMPTY_ANSWER = re.compile(r"(?:none|nothing|n/a)?[ \t]*[-—–]*", re.IGNORECASE)


def body_problem(body: str) -> str | None:
    """Name what a PR body lacks: an undo line, two diagrams or a Not checked line."""
    if not UNDO_LINE.search(body):
        return "PR body needs a line that starts `Undo:` and lists the undo steps"
    if len(MERMAID_BLOCK.findall(body)) < 2:
        return (
            "PR body needs a `Before and after` part with two or more Mermaid diagrams: "
            "one of the old flow and one of the new flow for each main change, "
            "or two or more of the new flows when no old flow exists"
        )
    for found in NOT_CHECKED_LINE.findall(body):
        if not EMPTY_ANSWER.fullmatch(found.strip().rstrip(".")):
            return None
    return (
        "PR body needs a line that starts `Not checked:`, with the answer on that line: "
        "`Not checked: <what no check covered>`, "
        "or `Not checked: None — <reason>`"
    )


def event_problem(event_path: str, root: Path = Path()) -> str | None:
    """Name what the text of the PR in a GitHub event file lacks; None when it passes."""
    from shipping import ShippingError, load_policy
    from update_runner import UPDATE_BRANCH

    pull = json.loads(Path(event_path).read_text())["pull_request"]
    if pull["head"]["ref"] == UPDATE_BRANCH:
        return None
    try:
        policy = load_policy(root, required=False)
    except ShippingError:
        policy = None
    if policy is not None and pull["base"]["ref"] != policy["base"]:
        return None
    problem = body_problem(pull["body"] or "")
    if problem:
        return f"{problem}. Edit the PR text; this check runs again on each edit."
    return None
