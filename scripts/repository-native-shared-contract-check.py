#!/usr/bin/env python3
"""Prove the no-version shared wiring: one repository fetches the newest Hard Eng main into its own copy and
commits the bootstrap, guard shim, and rules; every fresh clone, worktree, and machine then fetches or reuses
that copy at session start and stays guarded until it does."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

AGENTS_ROOT = Path(__file__).resolve().parents[1]
DENY = '"permissionDecision":"deny"'
IDENTITY = ["-c", "user.name=proof", "-c", "user.email=proof@example.invalid"]
TOOLS = ("bash", "sh", "git", "python3", "dirname", "grep", "sed", "tr", "tail", "cat", "mkdir", "rm", "chmod")
SHARED_FILES = (
    "AGENTS.override.md",
    ".github/instructions/hard-eng.instructions.md",
    ".hard-eng/bootstrap.sh",
    ".hard-eng/hook.sh",
    ".codex/hooks.json",
    ".claude/settings.json",
    ".github/hooks/hard-eng.json",
    ".codex/config.toml",
)
GLOBAL_PAYLOAD_FILES = (
    "AGENTS.md",
    "scripts/hooks/agent-hook.sh",
    "agents/he-learn/claude.md",
    "agents/he-learn/codex.toml",
    "agents/he-learn/copilot.agent.md",
    "output-styles/plain-english.md",
    "skills/plain-english/SKILL.md",
    "bin/hard-eng",
)
OLD_PYTHON3 = '#!/bin/sh\ncase "$1" in\n  -c) exit 1 ;;\nesac\necho "Python 3.11.9"\n'


def load_contract():
    spec = importlib.util.spec_from_file_location(
        "contract", AGENTS_ROOT / "scripts/repository-native-contract-check.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = load_contract()
write = contract.write
link = contract.link


def run(command: list[str], *, cwd: Path, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, check=False
    )
    if check and result.returncode != 0:
        raise AssertionError(f"{command} failed ({result.returncode}):\n{result.stdout}\n{result.stderr}")
    return result


def git(cwd: Path, env: dict[str, str], *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *IDENTITY, *arguments], cwd=cwd, env=env, check=check)


def base_env(home: Path, url: str) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env["HOME"] = str(home)
    env["HARD_ENG_SOURCE_URL"] = url
    env["GIT_CONFIG_GLOBAL"] = "/dev/null"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def tools_path(root: Path, *, exclude: tuple[str, ...] = ()) -> Path:
    tools = root / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    for name in TOOLS:
        if name in exclude:
            continue
        target = shutil.which(name)
        if target is not None:
            (tools / name).symlink_to(target)
    return tools


def make_source(root: Path, env: dict[str, str]) -> str:
    excludes = [".git", "node_modules", ".venv-mutation", "mutants", ".a", "features", "__pycache__"]
    run(["rsync", "-a", *(f"--exclude={name}" for name in excludes), f"{AGENTS_ROOT}/", f"{root}/"], cwd=root, env=env)
    git(root, env, "init", "-q", "-b", "main")
    git(root, env, "add", "-A")
    git(root, env, "commit", "-q", "-m", "one")
    return git(root, env, "rev-parse", "HEAD").stdout.strip()


def make_consumer(path: Path, env: dict[str, str], marker: dict, extra: dict[str, str] | None = None) -> None:
    path.mkdir(parents=True)
    git(path, env, "init", "-q", "-b", "main")
    (path / "AGENTS.md").write_text("# Repository Rules\n\n- Keep it simple.\n", encoding="utf-8")
    (path / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (path / "hard-eng.gates.json").write_text(json.dumps(marker, indent=2) + "\n", encoding="utf-8")
    for relative, content in (extra or {}).items():
        write(path / relative, content)
    git(path, env, "add", "-A")
    git(path, env, "commit", "-q", "-m", "init")


def launcher(source: Path, repo: Path, env: dict[str, str], *arguments: str, check: bool = True):
    command = [sys.executable, str(source / "bin/hard-eng"), *arguments, "--repo", str(repo), "--home", env["HOME"]]
    return run(command, cwd=repo, env=env, check=check)


def state(source: Path, repo: Path, env: dict[str, str], *arguments: str) -> dict:
    return json.loads(launcher(source, repo, env, *arguments, "--json").stdout)


def hook(repo: Path, env: dict[str, str], agent: str, event: str, *, cwd: Path | None = None) -> str:
    return run(["bash", str(repo / ".hard-eng/hook.sh"), agent, event], cwd=cwd or repo, env=env).stdout


def bootstrap(repo: Path, env: dict[str, str], mode: str, *, check: bool = True):
    return run(["bash", str(repo / ".hard-eng/bootstrap.sh"), mode], cwd=repo, env=env, check=check)


def current_commit(repo: Path) -> str:
    link = repo / ".agents/hard-eng/current"
    assert link.is_symlink(), link
    target = os.readlink(link)
    assert target.startswith("checkouts/"), target
    return target.split("/", 1)[1]


def git_status(repo: Path, env: dict[str, str]) -> set[str]:
    output = git(repo, env, "status", "--short", "--untracked-files=all").stdout
    return {line[3:] for line in output.splitlines() if line.strip()}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hook_settings(command: str) -> str:
    value = {
        "hooks": {"PreToolUse": [{"hooks": [{"command": command, "type": "command"}]}]},
        "outputStyle": "Plain English",
    }
    return json.dumps(value, indent=2) + "\n"


def build_healthy_global(home: Path) -> None:
    root = home / ".agents"
    for relative in GLOBAL_PAYLOAD_FILES:
        source = AGENTS_ROOT / relative
        write(root / relative, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
    for source in sorted((AGENTS_ROOT / "runtime/repository_native").glob("*.py")):
        write(
            root / "runtime/repository_native" / source.name, source.read_bytes(), stat.S_IMODE(source.stat().st_mode)
        )
    link(home / ".local/bin/hard-eng", root / "bin/hard-eng")
    write(home / ".claude/CLAUDE.md", f"@{(root / 'AGENTS.md').resolve()}\n")
    link(home / ".claude/skills", root / "skills")
    link(home / ".claude/output-styles", root / "output-styles")
    link(home / ".claude/agents/he-learn.md", root / "agents/he-learn/claude.md")
    write(
        home / ".claude/settings.json", hook_settings(f"bash {root / 'scripts/hooks/agent-hook.sh'} claude pretooluse")
    )
    write(home / ".claude.json", json.dumps({"mcpServers": {"codebase-memory": {}}}))


def assert_share_and_clone(root: Path, env: dict[str, str], source: Path, first: str) -> Path:
    shared_marker = {"schema_version": 1, "hard_eng": {"schema_version": 1, "wiring": "shared"}}
    origin = root / "origin"
    make_consumer(origin, env, shared_marker)
    home = root / "home"
    shared_env = base_env(home, env["HARD_ENG_SOURCE_URL"])
    shared = state(source, origin, shared_env, "update", "--agent", "codex")
    assert shared["mode"] == "shared" and shared["identity"] == first and shared["wiring"] == "verified", shared
    assert current_commit(origin) == first
    for relative in SHARED_FILES:
        assert (origin / relative).is_file(), relative
    assert read_json(origin / "hard-eng.gates.json")["hard_eng"] == shared_marker["hard_eng"]
    assert git_status(origin, env) == set(SHARED_FILES), git_status(origin, env)
    git(origin, env, "add", "-A")
    git(origin, env, "commit", "-q", "-m", "share hard eng")
    print("share: PASS")

    clone = root / "clone"
    git(root, env, "clone", "-q", str(origin), str(clone))
    clone_home = root / "clone-home"
    dead = base_env(clone_home, "file://" + str(root / "missing"))
    live = base_env(clone_home, env["HARD_ENG_SOURCE_URL"])
    denied = hook(clone, dead, "claude", "pretooluse")
    assert DENY in denied and "bash .hard-eng/bootstrap.sh claude" in denied and "could not reach" in denied, denied
    assert hook(clone, dead, "claude", "posttooluse") == "" and hook(clone, dead, "claude", "stop") == ""
    assert not (clone / ".agents/hard-eng/current").exists()
    command = read_json(clone / ".claude/settings.json")["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    subdirectory = clone / "nested/deeper"
    subdirectory.mkdir(parents=True)
    nested = run(["bash", "-c", command], cwd=subdirectory, env=dead).stdout
    assert DENY in nested, nested
    inherited = {**dead, "GIT_DIR": str(source / ".git"), "GIT_WORK_TREE": str(source)}
    from_inherited = run(["bash", "-c", command], cwd=subdirectory, env=inherited).stdout
    assert DENY in from_inherited, from_inherited
    assert git_status(clone, env) == set(), git_status(clone, env)
    print("fresh-clone-denied: PASS")

    started = bootstrap(clone, live, "claude")
    assert "Hard Eng is now at " + first[:12] in started.stderr, started.stderr
    output = json.loads(started.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart" and output["reloadSkills"] is True
    assert current_commit(clone) == first
    assert hook(clone, live, "claude", "pretooluse") == ""
    status = state(source, clone, live, "status", "--agent", "claude")
    assert status["mode"] == "shared" and status["identity"] == first and status["wiring"] == "verified", status
    assert git_status(clone, env) == set(), "clone dirty"
    print("first-fetch: PASS")

    same = bootstrap(clone, live, "download")
    assert "Hard Eng is now at" not in same.stderr, same.stderr
    (source / "AGENTS.md").open("a", encoding="utf-8").write("\n- Newer rule.\n")
    git(source, env, "commit", "-qam", "two")
    second = git(source, env, "rev-parse", "HEAD").stdout.strip()
    refreshed = bootstrap(clone, live, "codex")
    assert "Hard Eng is now at " + second[:12] in refreshed.stderr, refreshed.stderr
    assert current_commit(clone) == second
    assert not (clone / ".agents/hard-eng/checkouts" / first).exists()
    assert "Newer rule" in (clone / ".agents/hard-eng/current/AGENTS.md").read_text()
    print("refresh: PASS")

    kept = bootstrap(clone, dead, "download")
    assert kept.returncode == 0 and "keeping Hard Eng " + second[:12] in kept.stderr, kept.stderr
    assert current_commit(clone) == second
    assert hook(clone, dead, "claude", "pretooluse") == ""
    print("offline-keep: PASS")

    guard = clone / ".agents/hard-eng/global-guard"
    guard.write_text("codex\n", encoding="utf-8")
    assert hook(clone, dead, "codex", "pretooluse") == ""
    assert hook(clone, dead, "claude", "pretooluse") == ""
    guard.unlink()
    print("global-guard-toggle: PASS")

    legacy = clone / ".agents/hard-eng"
    (legacy / "releases/v0.1.0-alpha.gabc").mkdir(parents=True)
    (legacy / "last-check.json").write_text("{}", encoding="utf-8")
    (legacy / "current").unlink()
    (legacy / "current").symlink_to("releases/v0.1.0-alpha.gabc")
    healed = bootstrap(clone, live, "download")
    assert "Hard Eng is now at " + second[:12] in healed.stderr, healed.stderr
    assert not (legacy / "releases").exists() and not (legacy / "last-check.json").exists()
    assert current_commit(clone) == second
    print("legacy-cache: PASS")
    return origin


def assert_worktree_self_heal(
    root: Path, env: dict[str, str], origin: Path, source: Path, live: dict[str, str]
) -> None:
    root.mkdir(parents=True)
    healed = root / "healed-worktree"
    git(origin, env, "worktree", "add", "-q", "--detach", str(healed))
    assert not (healed / ".agents").exists()
    assert hook(healed, live, "claude", "posttooluse") == "" and hook(healed, live, "claude", "stop") == ""
    assert not (healed / ".agents").exists(), "posttooluse/stop passthrough must not trigger a fetch"
    allowed = hook(healed, live, "claude", "pretooluse")
    assert allowed == "", allowed
    newest = git(source, env, "rev-parse", "HEAD").stdout.strip()
    assert current_commit(healed) == newest
    assert hook(healed, live, "claude", "pretooluse") == ""
    print("worktree-self-heal: PASS")


def assert_python_version_gate(root: Path, env: dict[str, str], origin: Path, url: str) -> None:
    root.mkdir(parents=True)
    clone = root / "clone"
    git(root, env, "clone", "-q", str(origin), str(clone))
    old_python = root / "old-python-bin"
    write(old_python / "python3", OLD_PYTHON3, 0o755)
    gate_env = base_env(root / "home", url)
    gate_env["PATH"] = os.pathsep.join((str(old_python), str(tools_path(root))))
    failed = bootstrap(clone, gate_env, "claude", check=False)
    assert failed.returncode == 1 and failed.stdout == "", (failed.returncode, failed.stdout)
    assert "hard-eng bootstrap: python3 3.12 or newer is required" in failed.stderr, failed.stderr
    assert not (clone / ".agents/hard-eng/current").exists()
    assert git_status(clone, env) == set(), git_status(clone, env)
    print("python-version-gate: PASS")


def assert_git_missing_gate(root: Path, env: dict[str, str], origin: Path, url: str) -> None:
    root.mkdir(parents=True)
    clone = root / "clone"
    git(root, env, "clone", "-q", str(origin), str(clone))
    gate_env = base_env(root / "home", url)
    gate_env["PATH"] = str(tools_path(root, exclude=("git",)))
    failed = bootstrap(clone, gate_env, "claude", check=False)
    assert failed.returncode == 1 and failed.stdout == "", (failed.returncode, failed.stdout)
    assert "hard-eng bootstrap: git is required" in failed.stderr, failed.stderr
    assert not (clone / ".agents/hard-eng/current").exists()
    print("git-missing-gate: PASS")


def assert_merge_update_uninstall(root: Path, env: dict[str, str], source: Path, url: str) -> None:
    root.mkdir(parents=True)
    marker = {"schema_version": 1, "hard_eng": {"schema_version": 1, "wiring": "shared"}}
    origin = root / "origin"
    foreign_claude = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo foreign"}]}]},
    }
    foreign_codex = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo codex-foreign"}]}]}}
    foreign_config = "editor = 'vim'\n"
    extra = {
        ".claude/settings.json": json.dumps(foreign_claude) + "\n",
        ".codex/hooks.json": json.dumps(foreign_codex) + "\n",
        ".codex/config.toml": foreign_config,
    }
    make_consumer(origin, env, marker, extra)
    home = root / "home"
    origin_env = base_env(home, url)
    shared = state(source, origin, origin_env, "update", "--agent", "claude")
    assert shared["mode"] == "shared", shared
    claude = read_json(origin / ".claude/settings.json")
    assert claude["permissions"] == foreign_claude["permissions"]
    assert len(claude["hooks"]["PreToolUse"]) == 2 and len(claude["hooks"]["SessionStart"]) == 1
    codex = read_json(origin / ".codex/hooks.json")
    assert codex["hooks"]["PreToolUse"][0] == foreign_codex["hooks"]["PreToolUse"][0]
    assert len(codex["hooks"]["PreToolUse"]) == 2
    config = (origin / ".codex/config.toml").read_text(encoding="utf-8")
    assert config.startswith("editor = 'vim'") and "project_doc_max_bytes = 65536" in config, config
    assert git_status(origin, env) == set(SHARED_FILES), git_status(origin, env)
    git(origin, env, "add", "-A")
    git(origin, env, "commit", "-q", "-m", "share")
    print("merge: PASS")

    foreign_owner = root / "foreign-owner"
    make_consumer(foreign_owner, env, marker, {"AGENTS.override.md": "# Someone else's override\n"})
    foreign_env = base_env(root / "foreign-home", url)
    refused = launcher(source, foreign_owner, foreign_env, "update", "--agent", "claude", check=False)
    assert refused.returncode == 1 and "has another owner: AGENTS.override.md" in refused.stderr, refused.stderr
    assert git_status(foreign_owner, env) == set()
    assert not (foreign_owner / ".agents").exists()

    small = root / "small-config"
    make_consumer(small, env, marker, {".codex/config.toml": "project_doc_max_bytes = 100\n"})
    small_env = base_env(root / "small-home", url)
    failed_small = launcher(source, small, small_env, "update", "--agent", "claude", check=False)
    assert failed_small.returncode == 1 and "project_doc_max_bytes = 100" in failed_small.stderr, failed_small.stderr
    assert git_status(small, env) == set()
    print("merge-refusals: PASS")

    (source / "AGENTS.md").open("a", encoding="utf-8").write("\n- Even newer.\n")
    git(source, env, "commit", "-qam", "three")
    newest = git(source, env, "rev-parse", "HEAD").stdout.strip()
    updated = state(source, origin, origin_env, "update", "--agent", "claude")
    assert updated["mode"] == "shared" and updated["identity"] == newest, updated
    assert current_commit(origin) == newest
    git(origin, env, "add", "-A")
    git(origin, env, "commit", "-q", "-m", "update")
    print("update: PASS")

    uninstalled = launcher(source, origin, origin_env, "uninstall")
    assert "removed the Hard Eng wiring" in uninstalled.stdout, uninstalled.stdout
    assert read_json(origin / ".claude/settings.json") == foreign_claude
    assert read_json(origin / ".codex/hooks.json") == foreign_codex
    assert (origin / ".codex/config.toml").read_text(encoding="utf-8") == foreign_config
    assert "hard_eng" not in read_json(origin / "hard-eng.gates.json")
    assert not (origin / ".hard-eng").exists() and not (origin / ".agents").exists()
    assert git_status(origin, env) == {*SHARED_FILES, "hard-eng.gates.json"}, git_status(origin, env)
    again = launcher(source, origin, origin_env, "uninstall")
    assert "Hard Eng is not installed in this repository" in again.stdout, again.stdout
    print("uninstall: PASS")


def assert_global_machine(root: Path, env: dict[str, str], origin: Path, source: Path, url: str) -> None:
    root.mkdir(parents=True)
    home = root / "home"
    build_healthy_global(home)
    clone = root / "clone"
    git(root, env, "clone", "-q", str(origin), str(clone))
    clone_env = base_env(home, url)
    prepared = state(source, clone, clone_env, "prepare", "--agent", "claude")
    assert prepared["mode"] == "shared" and "the global Hard Eng guard checks tool calls" in prepared["wiring"], (
        prepared
    )
    assert (clone / ".agents/hard-eng/global-guard").read_text(encoding="utf-8") == "claude\n"
    assert current_commit(clone) is not None
    assert hook(clone, clone_env, "claude", "pretooluse") == ""
    print("global-machine: PASS")


def assert_old_marker_and_pass_through(root: Path, env: dict[str, str], source: Path, url: str) -> None:
    root.mkdir(parents=True)
    old = root / "old-marker"
    old_marker = {
        "schema_version": 1,
        "hard_eng": {"schema_version": 1, "wiring": "shared", "channel": "prerelease", "pin": {"tag": "v0.1.0"}},
    }
    make_consumer(old, env, old_marker)
    old_env = base_env(root / "old-home", url)
    rejected = launcher(source, old, old_env, "prepare", "--agent", "codex", check=False)
    assert rejected.returncode == 1 and "unsupported keys: channel, pin" in rejected.stderr, rejected.stderr
    print("old-marker: PASS")

    unmarked = root / "unmarked"
    make_consumer(unmarked, env, {"schema_version": 1})
    unmarked_env = base_env(root / "unmarked-home", url)
    plain = launcher(source, unmarked, unmarked_env, "prepare", "--agent", "codex", check=False)
    assert plain.returncode == 1 and "hard-eng install --repo" in plain.stderr, plain.stderr
    status = state(source, unmarked, unmarked_env, "status", "--agent", "codex")
    assert status["mode"] == "unprotected", status
    print("unprotected: PASS")


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="hard-eng-shared-"))
    try:
        source = work / "source"
        source.mkdir()
        env = base_env(work / "rsync-home", "file://" + str(source))
        first = make_source(source, env)
        url = "file://" + str(source)

        origin = assert_share_and_clone(work / "share", env, source, first)
        live = base_env(work / "worktree-home", url)
        assert_worktree_self_heal(work / "worktree-heal", env, origin, source, live)
        assert_python_version_gate(work / "python-gate", env, origin, url)
        assert_git_missing_gate(work / "git-gate", env, origin, url)
        assert_merge_update_uninstall(work / "merge", env, source, url)
        assert_global_machine(work / "global", env, origin, source, url)
        assert_old_marker_and_pass_through(work / "markers", env, source, url)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(
        "repository-native-shared-contract: PASS share fresh-clone-denied first-fetch refresh offline-keep "
        "global-guard-toggle legacy-cache worktree-self-heal python-version-gate git-missing-gate merge "
        "merge-refusals update uninstall global-machine old-marker unprotected"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
