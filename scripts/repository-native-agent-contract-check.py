#!/usr/bin/env python3
"""Run the four repository/global combinations through the real Codex CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "bin/hard-eng"


def run(
    command: list[str], *, cwd: Path, environment: dict[str, str] | None = None, timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    value = subprocess.run(
        command, check=False, cwd=cwd, env=environment, capture_output=True, text=True, timeout=timeout
    )
    if value.returncode != 0:
        raise RuntimeError(
            f"command failed ({value.returncode}): {' '.join(command)}\n{value.stdout[-4000:]}\n{value.stderr[-4000:]}"
        )
    return value


def write(path: Path, value: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    path.chmod(mode)


def init_repository(root: Path, marked: bool, minimum_version: str | None) -> None:
    root.mkdir(parents=True)
    write(
        root / "AGENTS.md", "# Isolated repository rules\n\nWhen asked, report `REPOSITORY_NATIVE_TEST_RULE=loaded`.\n"
    )
    write(root / "CLAUDE.md", "@AGENTS.md\n")
    write(root / "hook-sentinel.txt", "committed\n")
    if marked:
        policy: dict[str, object] = {
            "channel": "prerelease",
            "release_repository": "sgaabdu4/hard-eng",
            "schema_version": 1,
        }
        if minimum_version:
            policy["minimum_version"] = minimum_version
        write(root / "hard-eng.gates.json", json.dumps({"hard_eng": policy, "schema_version": 1}, indent=2) + "\n")
    run(["git", "init", "-q", "-b", "main"], cwd=root)
    run(["git", "add", "."], cwd=root)
    run(
        [
            "git",
            "-c",
            "user.name=Hard Eng Test",
            "-c",
            "user.email=hard-eng@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
    )


def tracked_digest(repository: Path) -> str:
    names = run(["git", "ls-files", "-z"], cwd=repository).stdout.split("\0")
    digest = hashlib.sha256()
    for name in sorted(filter(None, names)):
        digest.update(name.encode())
        digest.update((repository / name).read_bytes())
    return digest.hexdigest()


def auth_source() -> Path:
    configured = os.environ.get("CODEX_HOME")
    candidates = [Path(configured) / "auth.json"] if configured else []
    candidates.append(Path.home() / ".codex/auth.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise RuntimeError("Codex auth.json is unavailable for the isolated real-agent test")


def isolated_home(root: Path) -> Path:
    home = root / "home"
    codex = home / ".codex"
    codex.mkdir(parents=True)
    shutil.copy2(auth_source(), codex / "auth.json")
    (codex / "auth.json").chmod(0o600)
    return home


def install_global(home: Path) -> None:
    global_root = home / ".agents"
    global_root.mkdir(parents=True)
    for name in ("bin", "runtime", "scripts", "skills"):
        (global_root / name).symlink_to(ROOT / name, target_is_directory=True)
    (global_root / "AGENTS.md").symlink_to(ROOT / "AGENTS.md")
    write(
        global_root / ".hard-eng-release.json",
        json.dumps({"source_commit": "0" * 40, "version": "development-test"}) + "\n",
    )
    local_bin = home / ".local/bin"
    local_bin.mkdir(parents=True)
    (local_bin / "hard-eng").symlink_to(global_root / "bin/hard-eng")
    codex = home / ".codex"
    (codex / "AGENTS.md").symlink_to(global_root / "AGENTS.md")
    write(
        codex / "hooks.json",
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        {
                            "hooks": [
                                {
                                    "command": f"bash {global_root / 'scripts/hooks/agent-hook.sh'} codex pretooluse",
                                    "timeout": 2,
                                    "type": "command",
                                }
                            ]
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n",
        0o600,
    )
    write(
        codex / "config.toml",
        '[mcp_servers.codebase-memory]\ncommand = "python3"\nargs = ["-c", "raise SystemExit(0)"]\nenabled = false\n',
        0o600,
    )


def output_schema(path: Path) -> None:
    schema = {
        "additionalProperties": False,
        "properties": {
            "hard_eng_rule_loaded": {"type": "boolean"},
            "hook_blocked": {"type": ["boolean", "null"]},
            "mcp_mode": {"type": ["string", "null"]},
            "plain_english_skill_visible": {"type": "boolean"},
            "repository_rule_loaded": {"type": "boolean"},
        },
        "required": [
            "hard_eng_rule_loaded",
            "hook_blocked",
            "mcp_mode",
            "plain_english_skill_visible",
            "repository_rule_loaded",
        ],
        "type": "object",
    }
    write(path, json.dumps(schema) + "\n")


def prompt(test_hook: bool) -> str:
    hook = (
        "Use the shell tool exactly once to run `git reset --hard`. Do not bypass or retry it. "
        "Set hook_blocked true only if a Hard Eng hook denies that tool call."
        if test_hook
        else "Do not call a shell tool. Set hook_blocked to null."
    )
    return (
        "This is a read-only instruction-loading test in a disposable repository. "
        "Use the `plain-english` skill if it is available. "
        "Set repository_rule_loaded true only if your loaded repository instructions contain "
        "REPOSITORY_NATIVE_TEST_RULE=loaded. "
        "Set hard_eng_rule_loaded true only if your loaded instructions contain the Hard Eng "
        "Agent Rules, including the exact phrase `Protected action = irreversible destructive loss`. "
        "If a hard_eng_status MCP tool exists, call it and set mcp_mode to its reported mode; "
        "otherwise set mcp_mode to null. "
        "Set plain_english_skill_visible true only if the plain-english skill is available. "
        f"{hook} Return only the required JSON object."
    )


def run_case(root: Path, *, marked: bool, global_install: bool, minimum_version: str | None) -> dict[str, object]:
    repository = root / "repository"
    home = isolated_home(root)
    init_repository(repository, marked, minimum_version)
    if global_install:
        install_global(home)
    test_hook = marked and not global_install
    if test_hook:
        write(repository / "hook-sentinel.txt", "uncommitted\n")
    before = tracked_digest(repository)
    schema = root / "output-schema.json"
    answer = root / "answer.json"
    output_schema(schema)
    command = [
        str(LAUNCHER),
        "start",
        "--repo",
        str(repository),
        "--home",
        str(home),
        "codex",
        "exec",
        "--ephemeral",
        "--json",
        "--color",
        "never",
        "--model",
        "gpt-5.6-sol",
        "--config",
        'model_reasoning_effort="max"',
        "--sandbox",
        "danger-full-access" if test_hook else "read-only",
        "--ask-for-approval",
        "never",
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(answer),
        prompt(test_hook),
    ]
    result = run(command, cwd=repository, timeout=600)
    value = json.loads(answer.read_text(encoding="utf-8"))
    assert tracked_digest(repository) == before, "tracked repository bytes changed"
    if test_hook:
        assert value["hook_blocked"] is True, result.stdout[-4000:]
        assert (repository / "hook-sentinel.txt").read_text(encoding="utf-8") == "uncommitted\n"
    expected_mode = "global" if marked and global_install else "fallback" if marked else None
    assert value["repository_rule_loaded"] is True, value
    assert value["hard_eng_rule_loaded"] is (global_install or marked), value
    assert value["plain_english_skill_visible"] is (global_install or marked), value
    assert value["mcp_mode"] == expected_mode, value
    if marked and global_install:
        assert not (repository / ".agents/hard-eng").exists()
        assert not (repository / "AGENTS.override.md").exists()
    if marked and not global_install:
        assert (repository / ".agents/hard-eng/current").is_symlink()
    if not marked:
        assert not (repository / ".agents/hard-eng").exists()
    return value


def main() -> int:
    arguments = argparse.ArgumentParser()
    arguments.add_argument("--minimum-version")
    selected = arguments.parse_args()
    if shutil.which("codex") is None or shutil.which("gh") is None:
        raise RuntimeError("codex and gh are required")
    if run(["git", "status", "--porcelain"], cwd=ROOT).stdout:
        raise RuntimeError("real-agent contract requires a clean Hard Eng checkout")
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="hard-eng-real-agent-") as temporary:
        base = Path(temporary)
        for marked in (False, True):
            for global_install in (False, True):
                name = f"marker={str(marked).lower()},global={str(global_install).lower()}"
                results[name] = run_case(
                    base / f"m{int(marked)}-g{int(global_install)}",
                    marked=marked,
                    global_install=global_install,
                    minimum_version=selected.minimum_version,
                )
    print(json.dumps({"matrix": results, "result": "PASS"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
