#!/usr/bin/env python3
"""Static coverage for direct repository-owned Git process launches.

Git exports its per-invocation repository variables (`git rev-parse
--local-env-vars`) to hooks. A hook-launched child that inherits them resolves
`-C`, discovery, pathspecs, and the index against the hook's repository instead
of the requested checkout, so cross-repository and worktree work silently
targets the wrong tree.

The scanner covers direct and imported Python subprocess calls, common asyncio
and alternate process APIs, direct JavaScript child-process calls, and shell
Git commands. It does not claim to prove opaque wrappers or runtime-built
commands. Runtime owners still pass `env=git_env()` per call or call
`scrub_environ()` at process entry. Shell owners run the canonical unset line.
Managed vendor skills are lock-verified separately and are not scanned here.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
MARKER = "git-env-hygiene: exempt"
SHELL_SANITIZER = "unset $(git rev-parse --local-env-vars)"
SUBPROCESS_CALLS = frozenset({"run", "Popen", "call", "check_call", "check_output"})
ASYNC_PROCESS_CALLS = frozenset({"create_subprocess_exec", "create_subprocess_shell"})
ALTERNATE_PROCESS_CALLS = frozenset({"run_process", "open_process"})
SHELL_GIT_COMMAND = re.compile(r"(?:^|[;&|(]|\$\()\s*git\s+[-a-z]")
JAVASCRIPT_GIT_ARGV_CALL = re.compile(r"\b(?:spawn|spawnSync|execFile|execFileSync)\s*\(\s*(['\"])git\1\s*,")
JAVASCRIPT_GIT_SHELL_CALL = re.compile(r"\b(?:exec|execSync)\s*\(\s*(['\"])\s*git(?:\s|$)")
PROCESS_WIDE_ENTRYPOINTS = ("scripts/check-skill-contracts.py",)


def fail(message: str) -> NoReturn:
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


def _call_name(node: ast.expr) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (*_call_name(node.value), node.attr)
    return ()


def _literal_git_head(node: ast.expr, commands: dict[str, ast.expr]) -> bool:
    if isinstance(node, ast.Name) and node.id in commands:
        return _literal_git_head(commands[node.id], commands)
    if isinstance(node, (ast.List, ast.Tuple)):
        node = node.elts[0] if node.elts else ast.Constant(value=None)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return bool(re.match(r"^\s*git(?:\s|$)", node.value))
    return False


def _scrubs_process(tree: ast.AST) -> bool:
    if not isinstance(tree, ast.Module):
        return False
    return any(
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and _call_name(statement.value.func)[-1:] == ("scrub_environ",)
        for statement in tree.body
    )


def _sanitized_env(node: ast.expr) -> bool:
    if isinstance(node, ast.Call):
        return _call_name(node.func)[-1:] in {("git_env",), ("git_environment",)}
    if isinstance(node, ast.Name):
        return node.id in {"git_env", "sanitized_git_env", "sanitizedGitEnv"}
    return False


def python_violations(source: str, label: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"{label}: unparsable ({error})"]

    if _scrubs_process(tree):
        return []
    module_aliases: dict[str, str] = {
        "subprocess": "subprocess",
        "asyncio": "asyncio",
        "anyio": "anyio",
        "trio": "trio",
    }
    direct_calls: dict[str, str] = {}
    commands: dict[str, ast.expr] = {}
    runner_aliases: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for entry in node.names:
                if entry.name in {"subprocess", "asyncio", "anyio", "trio"}:
                    module_aliases[entry.asname or entry.name] = entry.name
        elif isinstance(node, ast.ImportFrom) and node.module in {"subprocess", "asyncio", "anyio", "trio"}:
            for entry in node.names:
                direct_calls[entry.asname or entry.name] = f"{node.module}.{entry.name}"
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Name) or value is None:
                    continue
                if isinstance(value, (ast.List, ast.Tuple, ast.Constant)):
                    commands[target.id] = value
                name = _call_name(value)
                if len(name) == 2 and name[0] in module_aliases:
                    runner_aliases[target.id] = (module_aliases[name[0]], name[1])

    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node.func)
        owner = ""
        operation = ""
        if len(name) == 2 and name[0] in module_aliases:
            owner, operation = module_aliases[name[0]], name[1]
        elif len(name) == 1 and name[0] in direct_calls:
            owner, operation = direct_calls[name[0]].split(".", 1)
        elif len(name) == 1 and name[0] in runner_aliases:
            owner, operation = runner_aliases[name[0]]
        supported = (
            owner == "subprocess"
            and operation in SUBPROCESS_CALLS
            or owner == "asyncio"
            and operation in ASYNC_PROCESS_CALLS
            or owner in {"anyio", "trio"}
            and operation in ALTERNATE_PROCESS_CALLS
        )
        if not supported or not node.args:
            continue
        if not _literal_git_head(node.args[0], commands):
            continue
        if any(keyword.arg == "env" and _sanitized_env(keyword.value) for keyword in node.keywords):
            continue
        found.append(f"{label}:{node.lineno}: direct Git process without a sanitized env")
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
    matches = sorted(
        (*JAVASCRIPT_GIT_ARGV_CALL.finditer(source), *JAVASCRIPT_GIT_SHELL_CALL.finditer(source)),
        key=lambda item: item.start(),
    )
    for match in matches:
        call = _javascript_call(source, match.start())
        line = source.count("\n", 0, match.start()) + 1
        if "rev-parse" in call and "--local-env-vars" in call:
            continue
        if re.search(r"\benv\s*:\s*(?:gitEnv|sanitizedGitEnv)\b", call):
            continue
        found.append(f"{label}:{line}: Git child process without env: gitEnv/sanitizedGitEnv")
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
        if not path.is_file() or path.suffix not in {".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".tsx"}:
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
    ("unsafe-env.py", 'subprocess.run(["git", "status"], env=os.environ)', True),
    ("unknown-env.py", 'subprocess.run(["git", "status"], env=bad_mapping)', True),
    ("scrubbed.py", 'scrub_environ()\nsubprocess.run(["git", "status"])', False),
    ("definition.py", 'def scrub_environ():\n    pass\nsubprocess.run(["git", "s"])', True),
    ("nested-scrub.py", 'def later():\n    scrub_environ()\nsubprocess.run(["git", "s"])', True),
    ("module-alias.py", 'import subprocess as sp\nsp.run(["git", "status"])', True),
    ("direct-import.py", 'from subprocess import run as execute\nexecute(["git", "status"])', True),
    ("runner-alias.py", 'runner = subprocess.run\nrunner(["git", "status"])', True),
    ("argv-name.py", 'command = ["git", "status"]\nsubprocess.run(command)', True),
    ("asyncio.py", 'asyncio.create_subprocess_exec("git", "status")', True),
    ("anyio.py", 'anyio.run_process(["git", "status"])', True),
    ("opaque-wrapper.py", 'repository_command("git", "status")', False),
    ("other.py", 'subprocess.run(["node", "x"])', False),
    ("bare.sh", 'git -C "$repo" init', True),
    ("substitution.sh", "top=$(git rev-parse --show-toplevel)", True),
    ("sanitized.sh", f'{SHELL_SANITIZER}\ngit -C "$repo" init', False),
    ("comment.sh", '# git -C "$repo" init', False),
    ("bare.mjs", "spawnSync('git', ['init', fixture], { encoding: 'utf8' })", True),
    ("qualified.mjs", "child_process.spawn('git', ['status'])", True),
    ("exec.mjs", "child_process.exec('git status')", True),
    ("passed.mjs", "spawnSync('git', ['init', fixture], { env: gitEnv, encoding: 'utf8' })", False),
    ("probe.mjs", "spawnSync('git', ['rev-parse', '--local-env-vars'], { encoding: 'utf8' })", False),
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
