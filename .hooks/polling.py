"""Claude Code PreToolUse hook: refuse a merge that skips ship, and deny foreground polling (HE-NO-FOREGROUND-POLL)."""

import json
import sys
from collections.abc import Callable

REASON = (
    "HE-NO-FOREGROUND-POLL: this command waits in the foreground with sleep. "
    "Start the long job once with run_in_background: true; "
    "the harness tells you when it exits. Read its output file after that notice."
)


UNQUOTE = str.maketrans("", "", "'\"\\")
NONWORD = str.maketrans({c: " " for c in "!\"#$%&'()*+,-.:;<=>?@[\\]^`{|}~"})


WATCHED_MARKS = ("$", "`", "{", "<(")
WATCHED_WORDS = frozenset(
    ("merge", "merges", "mergebranch", "mergepullrequest", "enqueuepullrequest")
    + ("enablepullrequestautomerge", "alias")
)
SPLIT = str.maketrans({c: " " for c in "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"})
API_WRITES = ("--method", "--input", "--field", "--raw-field")


def writes_api(words: list[str]) -> bool:
    """Whether a `gh api` call has a method flag, a field or `--input`: anything but a plain read."""
    return "api" in words and any(
        word.startswith(API_WRITES)
        or (word.startswith(("-f", "-x")) and not word.startswith("--"))
        for word in words
    )


def watched_gh(command: str) -> bool:
    """Whether the command, with its quotes removed, has a word that is `gh` or a path to it, in any letter case, and a word, mark or api write the merge guard must read."""
    bare = command.replace("\\\n", "").translate(UNQUOTE).lower()
    return (
        "gh" in bare
        and (
            any(mark in bare for mark in WATCHED_MARKS)
            or not WATCHED_WORDS.isdisjoint(bare.translate(SPLIT).split())
            or writes_api(bare.split())
        )
        and any(
            word.rsplit("/", 1)[-1] == "gh" for word in bare.translate(NONWORD).split()
        )
    )


def deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def decision(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if payload.get("tool_name") != "Bash" or not isinstance(command, str):
        return None
    if watched_gh(command):
        from merge_guard import merge_problem

        if problem := merge_problem(command, str(payload.get("cwd") or ".")):
            return deny(f"Merge refused: {problem}")
    if payload.get("agent_id") or (
        isinstance(tool_input, dict) and tool_input.get("run_in_background") is True
    ):
        return None
    if "sleep" not in command and "select(" not in command:
        return None
    from wait_text import polls

    return deny(REASON) if polls(command) else None


def respond(decide: Callable[[object], dict[str, object] | None]) -> int:
    try:
        output = decide(json.load(sys.stdin))
    except ValueError:
        return 0
    if output is not None:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(respond(decision))
