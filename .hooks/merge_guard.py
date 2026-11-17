"""Refuse a merge that skips ship: `gh pr merge` needs a passed ship record for its head, and `gh api` merge calls are always refused."""

import json
import re
import shlex
import subprocess
from pathlib import Path

OPERATORS = frozenset(("&&", "||", ";", "|", "&", "(", ")"))
WRAPPERS = frozenset(("env", "command", "sudo", "exec", "time", "nohup", "builtin"))
SHELLS = frozenset(("sh", "bash", "zsh", "dash"))
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
SHELL_COMMAND_FLAG = re.compile(r"-[a-z]*c[a-z]*")
VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
PULL_NUMBER = re.compile(r"(?:^|/pull/)(\d+)/?$")
API_MERGE = re.compile(
    r"pulls/[^\s/]*/merge\b|mergePullRequest|enablePullRequestAutoMerge"
)
OPAQUE_QUERY = re.compile(r"=@|^query=\$|\$\(|^--input")
GH_VALUE_FLAGS = frozenset(("-R", "--repo", "--hostname"))
INTERPRETERS = ("python", "node", "ruby", "perl", "php", "deno", "bun")
PR_MERGE_TEXT = re.compile(r"\bpr\W+merge\b")
STEP = "Merge with `python3 .hooks/hard-eng.py ship --pr <PR URL> --stage merge`."


def segments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(
        command.replace("\n", " ; "), posix=True, punctuation_chars=True
    )
    vars(lexer).update(whitespace_split=True)
    try:
        tokens = list(lexer)
    except ValueError:
        tokens = command.split()
    found: list[list[str]] = [[]]
    for token in tokens:
        if token in OPERATORS:
            found.append([])
        else:
            found[-1].append(token)
    return [words for words in found if words]


def program(words: list[str]) -> tuple[str, list[str]]:
    """The command a segment runs and its arguments, without variables and wrappers in front."""
    rest = list(words)
    while rest and (rest[0] in WRAPPERS or VARIABLE.match(rest[0])):
        rest.pop(0)
    return (Path(rest[0]).name, rest[1:]) if rest else ("", [])


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


def subcommand(arguments: list[str]) -> tuple[list[str], list[str]]:
    """The first two words of a gh command after its leading flags, and everything else."""
    words: list[str] = []
    rest: list[str] = []
    index = 0
    while index < len(arguments):
        word = arguments[index]
        if word.startswith("-"):
            take = 2 if word in GH_VALUE_FLAGS else 1
            rest += arguments[index : index + take]
            index += take
        elif len(words) < 2:
            words.append(word)
            index += 1
        else:
            rest += arguments[index:]
            break
    return words, rest


def gh_problem(arguments: list[str], cwd: Path) -> str | None:
    words, rest = subcommand(arguments)
    if words[:2] == ["pr", "merge"]:
        return pr_merge_problem(rest, cwd)
    if words[:1] == ["api"] and (
        any(API_MERGE.search(a) for a in arguments)
        or ("graphql" in arguments and any(OPAQUE_QUERY.search(a) for a in arguments))
    ):
        return f"a merge through `gh api` skips ship, and a query read from a file or a variable cannot be checked. {STEP}"
    if words[:1] == ["alias"] and any("merge" in a for a in arguments):
        return f"a `gh alias` that holds a merge skips ship. {STEP}"
    return None


def command_problem(words: list[str], cwd: Path, depth: int) -> str | None:
    name, arguments = program(words)
    if name == "gh":
        return gh_problem(arguments, cwd)
    if name in ("xargs", "eval") and depth < 3:
        return merge_problem(" ".join(arguments), cwd, depth + 1)
    if name.startswith(INTERPRETERS) and any(
        PR_MERGE_TEXT.search(a) for a in arguments
    ):
        return f"a script that runs `gh pr merge` skips ship. {STEP}"
    if name in SHELLS and depth < 3:
        for position, word in enumerate(arguments[:-1]):
            if SHELL_COMMAND_FLAG.fullmatch(word):
                return merge_problem(arguments[position + 1], cwd, depth + 1)
    return None


def merge_problem(command: str, cwd: Path, depth: int = 0) -> str | None:
    """The reason a command that merges a pull request is refused, or None."""
    for words in segments(command):
        if problem := command_problem(words, cwd, depth):
            return problem
    return None
