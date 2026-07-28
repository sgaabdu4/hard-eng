#!/usr/bin/env python3
"""Contract: every repository-owned Git invocation drops inherited hook variables.

Git exports its per-invocation repository variables (`git rev-parse
--local-env-vars`) to hooks. A hook-launched child that inherits them resolves
`-C`, discovery, pathspecs, and the index against the hook's repository instead
of the requested checkout, so cross-repository and worktree work silently
targets the wrong tree.

Python owners pass `env=git_env()` per call, or sanitize their own process with
`scrub_environ()`. Shell owners run `unset $(git rev-parse --local-env-vars)`.
An owner that must keep the inherited environment carries an exemption marker
with a reason.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKER = "git-env-hygiene: exempt"
SHELL_SANITIZER = "unset $(git rev-parse --local-env-vars)"
SUBPROCESS_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
SHELL_GIT_COMMAND = re.compile(r"(?:^|[;&|(]|\$\()\s*git\s+[-a-z]")


def fail(message: str) -> None:
    raise SystemExit(f"git-env-hygiene: FAIL: {message}")


def managed_skills() -> frozenset[str]:
    lock = json.loads((ROOT / ".skill-lock.json").read_text(encoding="utf-8"))
    return frozenset(lock.get("skills", {}))


def exemption_reason(source: str) -> str:
    for line in source.splitlines():
        if MARKER in line:
            return line.split(MARKER, 1)[1].strip(" #:-")
    return ""


def python_violations(source: str, label: str) -> list[str]:
    if re.search(r"(?<!def )scrub_environ\(", source):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"{label}: unparsable ({error})"]

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in SUBPROCESS_CALLS:
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "subprocess":
            continue
        if not node.args or not isinstance(node.args[0], (ast.List, ast.Tuple)):
            continue
        head = node.args[0].elts[0] if node.args[0].elts else None
        if not isinstance(head, ast.Constant) or head.value != "git":
            continue
        if any(keyword.arg == "env" for keyword in node.keywords):
            continue
        found.append(f"{label}:{node.lineno}: git subprocess without env=git_env()")
    return found


def shell_violations(source: str, label: str) -> list[str]:
    invocations = [
        index + 1
        for index, line in enumerate(source.splitlines())
        if SHELL_GIT_COMMAND.search(line) and not line.lstrip().startswith("#")
    ]
    if not invocations or SHELL_SANITIZER in source:
        return []
    return [f"{label}:{invocations[0]}: git invocation without `{SHELL_SANITIZER}`"]


def scan() -> list[str]:
    skip = tuple(f"skills/{name}/" for name in managed_skills())
    found: list[str] = []
    for path in sorted((*ROOT.glob("scripts/**/*"), *ROOT.glob("skills/**/*"))):
        if not path.is_file() or path.suffix not in {".py", ".sh"}:
            continue
        label = path.relative_to(ROOT).as_posix()
        if label.startswith(skip):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if MARKER in source:
            if not exemption_reason(source):
                found.append(f"{label}: exemption marker without a reason")
            continue
        checker = python_violations if path.suffix == ".py" else shell_violations
        found.extend(checker(source, label))
    return found


SELFTEST = (
    ("bare.py", 'subprocess.run(["git", "status"])', True),
    ("passed.py", 'subprocess.run(["git", "status"], env=git_env())', False),
    ("scrubbed.py", 'scrub_environ()\nsubprocess.run(["git", "status"])', False),
    ("definition.py", 'def scrub_environ():\n    pass\nsubprocess.run(["git", "s"])', True),
    ("other.py", 'subprocess.run(["node", "x"])', False),
    ("bare.sh", 'git -C "$repo" init', True),
    ("substitution.sh", 'top=$(git rev-parse --show-toplevel)', True),
    ("sanitized.sh", f'{SHELL_SANITIZER}\ngit -C "$repo" init', False),
    ("comment.sh", '# git -C "$repo" init', False),
)


def selftest() -> None:
    for name, source, expected in SELFTEST:
        checker = python_violations if name.endswith(".py") else shell_violations
        if bool(checker(source, name)) != expected:
            fail(f"detector self-test broke on {name}")


def main() -> int:
    selftest()
    violations = scan()
    if violations:
        fail("\n".join(violations))
    print("git-env-hygiene: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
