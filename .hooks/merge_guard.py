"""Refuse a merge that skips ship: a command with the words `gh` and `merge` passes only as one plain `gh pr merge` with a passed ship record."""

import json
import re
import shlex
import subprocess
from pathlib import Path

METHOD_FLAGS = {
    "--rebase": "rebase",
    "-r": "rebase",
    "--squash": "squash",
    "-s": "squash",
    "--merge": "merge",
    "-m": "merge",
}
VALUE_FLAGS = frozenset(
    ("--match-head-commit", "-R", "--repo", "-b", "--body", "-F", "--body-file")
    + ("-t", "--subject", "-A", "--author-email")
)
PULL_NUMBER = re.compile(r"(?:^|/pull/)(\d+)/?$")
WORD = re.compile(r"[A-Za-z0-9_]+")
MERGE_WORDS = frozenset(("merge", "mergePullRequest", "enablePullRequestAutoMerge"))
REFUSED_FLAGS = frozenset(("--admin", "--auto", "--disable-auto"))
STEP = "Merge with `python3 .hooks/hard-eng.py ship --pr <PR URL> --stage merge`."


def record_for(cwd: Path, number: int) -> dict[str, object] | None:
    done = subprocess.run(
        ["git", "rev-parse", "--git-path", "hard-eng/ship"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode:
        return None
    try:
        record = json.loads((cwd / done.stdout.strip() / f"{number}.json").read_text())
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def pr_flags(arguments: list[str]) -> tuple[str | None, set[str], str | None]:
    selector, methods, head = None, set[str](), None
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word == "--match-head-commit" and index + 1 < len(arguments):
            head = arguments[index + 1]
            index += 1
        elif word.startswith("--match-head-commit="):
            head = word.partition("=")[2]
        elif word in VALUE_FLAGS:
            index += 1
        elif word in METHOD_FLAGS:
            methods.add(METHOD_FLAGS[word])
        elif not word.startswith("-") and selector is None:
            selector = word
        index += 1
    return selector, methods, head


def pr_merge_problem(arguments: list[str], cwd: Path) -> str | None:
    selector, methods, head = pr_flags(arguments)
    found = PULL_NUMBER.search(selector or "")
    if found is None:
        return f"gh pr merge must name the pull request by number or URL. {STEP}"
    record = record_for(cwd, int(found[1]))
    if record is None or record.get("result") != "passed":
        return f"no passed `ship` record for PR {found[1]}. {STEP}"
    if head != record.get("head"):
        return f"gh pr merge needs `--match-head-commit {record.get('head')}`, the head that `ship` passed. {STEP}"
    if methods != {record.get("method")}:
        return f"the passed `ship` record names the method {record.get('method')}; use only that flag. {STEP}"
    return None


def holds_merge(command: str) -> bool:
    """Whether the command has the word `gh` and a merge word, each as its own word and never a part of one."""
    words = set(WORD.findall(command))
    return "gh" in words and bool(words & MERGE_WORDS)


def merge_problem(command: str, cwd: Path) -> str | None:
    """The reason a command that holds `gh` and `merge` is refused, or None when it is one plain `gh pr merge` with a passed record."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = list[str]()
    plain = tokens[:3] == ["gh", "pr", "merge"] and not re.search(
        r"[;&|<>`$(){}\n]", command
    )
    if not plain:
        return f"a command that holds `gh` and `merge` must be exactly one plain `gh pr merge`. {STEP}"
    if REFUSED_FLAGS & set(tokens):
        return f"`gh pr merge` with --admin or --auto skips ship. {STEP}"
    return pr_merge_problem(tokens[3:], cwd)
