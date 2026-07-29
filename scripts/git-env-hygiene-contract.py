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
import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKER = "git-env-hygiene: exempt"
SHELL_SANITIZER = "unset $(git rev-parse --local-env-vars)"
SUBPROCESS_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
SHELL_GIT_COMMAND = re.compile(r"(?:^|[;&|(]|\$\()\s*git\s+[-a-z]")
JAVASCRIPT_GIT_CALL = re.compile(
    r"\b(?:spawn|spawnSync|execFile|execFileSync)\s*\(\s*(['\"])git\1\s*,"
)
PROCESS_WIDE_ENTRYPOINTS = ("scripts/check-skill-contracts.py",)


def fail(message: str) -> None:
    raise SystemExit(f"git-env-hygiene: FAIL: {message}")


def managed_skills(root: Path) -> frozenset[str]:
    lock_path = root / ".skill-lock.json"
    if not lock_path.is_file():
        return frozenset()
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
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


def _javascript_call(source: str, start: int) -> str:
    opening = source.find("(", start)
    if opening < 0:
        return ""
    depth = 0
    quote = ""
    escaped = False
    for index in range(opening, len(source)):
        character = source[index]
        if quote:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == quote:
                quote = ""
            continue
        if character in {"'", '"', "`"}:
            quote = character
        elif character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return source[opening : index + 1]
    return source[opening:]


def javascript_violations(source: str, label: str) -> list[str]:
    found: list[str] = []
    for match in JAVASCRIPT_GIT_CALL.finditer(source):
        call = _javascript_call(source, match.start())
        line = source.count("\n", 0, match.start()) + 1
        if "rev-parse" in call and "--local-env-vars" in call:
            continue
        if re.search(r"\benv\s*:\s*(?:gitEnv|sanitizedGitEnv)\b", call):
            continue
        found.append(
            f"{label}:{line}: Git child process without env: gitEnv/sanitizedGitEnv"
        )
    return found


def scan(root: Path) -> list[str]:
    skip = tuple(f"skills/{name}/" for name in managed_skills(root))
    found: list[str] = []
    candidates = (
        *root.glob("scripts/**/*"),
        *root.glob("tool/**/*"),
        *root.glob(".githooks/**/*"),
        *root.glob(".husky/**/*"),
        *root.glob("skills/**/*"),
    )
    for path in sorted(candidates):
        if not path.is_file() or path.suffix not in {
            ".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".tsx"
        }:
            continue
        label = path.relative_to(root).as_posix()
        if label.startswith(skip):
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        if MARKER in source:
            if not exemption_reason(source):
                found.append(f"{label}: exemption marker without a reason")
            continue
        if path.suffix == ".py":
            checker = python_violations
        elif path.suffix == ".sh":
            checker = shell_violations
        else:
            checker = javascript_violations
        found.extend(checker(source, label))
    for label in PROCESS_WIDE_ENTRYPOINTS:
        path = root / label
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if "scrub_environ()" not in source:
            found.append(f"{label}: process-wide Git environment scrub missing")
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
    ("bare.mjs", "spawnSync('git', ['init', fixture], { encoding: 'utf8' })", True),
    (
        "passed.mjs",
        "spawnSync('git', ['init', fixture], { env: gitEnv, encoding: 'utf8' })",
        False,
    ),
    (
        "probe.mjs",
        "spawnSync('git', ['rev-parse', '--local-env-vars'], { encoding: 'utf8' })",
        False,
    ),
)


def selftest() -> None:
    for name, source, expected in SELFTEST:
        if name.endswith(".py"):
            checker = python_violations
        elif name.endswith(".sh"):
            checker = shell_violations
        else:
            checker = javascript_violations
        if bool(checker(source, name)) != expected:
            fail(f"detector self-test broke on {name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        fail(f"scan root is not a directory: {root}")
    selftest()
    violations = scan(root)
    if violations:
        fail("\n".join(violations))
    print("git-env-hygiene: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
