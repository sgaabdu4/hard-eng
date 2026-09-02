#!/usr/bin/env python3
"""Prove shared wiring: one repository pins a release and commits the bootstrap, shim, hooks, and rules;
every fresh clone then downloads exactly that release at session start and stays guarded until it does."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "scripts/repository-native-contract-check.py"
SHARED_FILES = (
    "AGENTS.override.md",
    ".github/instructions/hard-eng.instructions.md",
    ".hard-eng/bootstrap.sh",
    ".hard-eng/hook.sh",
    ".codex/hooks.json",
    ".claude/settings.json",
    ".github/hooks/hard-eng.json",
)
PRIVATE_FILES = (
    "CLAUDE.local.md",
    ".agents/hard-eng/current",
    ".agents/hard-eng/last-check.json",
    ".agents/hard-eng/wiring.json",
    ".claude/skills/plain-english",
    ".claude/output-styles/plain-english.md",
)
DENY = '"permissionDecision":"deny"'


def load_contract():
    spec = importlib.util.spec_from_file_location("repository_native_contract", CONTRACT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


contract = load_contract()
TAG = contract.TAG
ASSET_NAMES = (f"hard-eng-{TAG}.tar.gz", f"hard-eng-{TAG}.manifest.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def downloads(assets: Path, name: str = "downloads", *, tamper: bool = False) -> str:
    """Lay the release assets out the way GitHub serves them: <base>/<tag>/<asset>."""
    root = assets.parent / name
    target = root / TAG
    if not target.exists():
        target.mkdir(parents=True)
        for asset in ASSET_NAMES:
            shutil.copy2(assets / asset, target / asset)
        if tamper:
            with (target / ASSET_NAMES[0]).open("ab") as handle:
                handle.write(b"tampered")
    return root.as_uri()


def git_status(repository: Path) -> set[str]:
    output = contract.run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout
    return {line[3:] for line in output.splitlines() if line.strip()}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hook_commands(value: dict, event: str) -> list[str]:
    commands: list[str] = []
    for entry in value.get("hooks", {}).get(event, []):
        inner = entry.get("hooks") if isinstance(entry.get("hooks"), list) else [entry]
        for hook in inner:
            commands.extend(str(hook[key]) for key in ("command", "bash") if key in hook)
    return commands


def cli(repository: Path, home: Path, env: dict[str, str], *arguments: str, check: bool = True):
    command = [str(contract.LAUNCHER), *arguments, "--repo", str(repository), "--home", str(home)]
    return contract.run(command, cwd=repository, environment=env, check=check)


def state(repository: Path, home: Path, env: dict[str, str], *arguments: str) -> dict:
    return json.loads(cli(repository, home, env, *arguments, "--json").stdout)


def shim(clone: Path, env: dict[str, str], agent: str, event: str, *, cwd: Path | None = None) -> str:
    result = contract.run(["bash", str(clone / ".hard-eng/hook.sh"), agent, event], cwd=cwd or clone, environment=env)
    return result.stdout


def bootstrap(clone: Path, env: dict[str, str], mode: str, *, check: bool = True):
    return contract.run(["bash", ".hard-eng/bootstrap.sh", mode], cwd=clone, environment=env, check=check)


def clone_env(env: dict[str, str], home: Path, base_url: str) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    value = dict(env)
    value["HOME"] = str(home)
    value["HARD_ENG_RELEASE_BASE_URL"] = base_url
    return value


def assert_share(root: Path, env: dict[str, str], assets: Path) -> Path:
    repository = root / "origin"
    contract.init_repository(repository, marked=True)
    home = root / "home"
    home.mkdir()
    shared = state(repository, home, env, "prepare", "--shared", "--agent", "claude")
    assert shared["mode"] == "shared" and shared["version"] == TAG, shared
    assert shared["last_check"] == "pinned-verified" and shared["wiring"] == "verified", shared
    policy = read_json(repository / "hard-eng.gates.json")["hard_eng"]
    assert policy["channel"] == "prerelease" and policy["wiring"] == "shared", policy
    assert policy["pin"] == {
        "tag": TAG,
        "archive_sha256": sha256(assets / ASSET_NAMES[0]),
        "manifest_sha256": sha256(assets / ASSET_NAMES[1]),
    }, policy["pin"]
    for relative in SHARED_FILES:
        assert (repository / relative).is_file(), relative
    for relative in (".hard-eng/bootstrap.sh", ".hard-eng/hook.sh"):
        script = repository / relative
        assert os.access(script, os.X_OK), relative
        text = script.read_text(encoding="utf-8")
        assert text.startswith("#!/usr/bin/env bash\n# Generated by Hard Eng"), relative
    override = (repository / "AGENTS.override.md").read_text(encoding="utf-8")
    assert contract.REPOSITORY_MARKER in override and contract.HARD_ENG_MARKER in override
    assert "--repo --shared" in override
    instructions = (repository / ".github/instructions/hard-eng.instructions.md").read_text(encoding="utf-8")
    assert instructions.startswith('---\napplyTo: "**"\n---\n') and contract.HARD_ENG_MARKER in instructions
    claude = read_json(repository / ".claude/settings.json")
    assert claude["outputStyle"] == "Plain English"
    assert claude["hooks"]["SessionStart"][0]["matcher"] == "startup|resume|clear"
    assert claude["hooks"]["SessionStart"][0]["hooks"][0]["timeout"] == 300
    assert hook_commands(claude, "SessionStart") == [
        'bash "$(git rev-parse --show-toplevel)/.hard-eng/bootstrap.sh" claude'
    ]
    assert hook_commands(claude, "PreToolUse") == [
        'bash "$(git rev-parse --show-toplevel)/.hard-eng/hook.sh" claude pretooluse'
    ]
    codex = read_json(repository / ".codex/hooks.json")
    assert codex["hooks"]["SessionStart"][0]["matcher"] == "startup|resume"
    assert hook_commands(codex, "SessionStart") == [
        'bash "$(git rev-parse --show-toplevel)/.hard-eng/bootstrap.sh" codex'
    ]
    assert hook_commands(codex, "PreToolUse") == [
        'bash "$(git rev-parse --show-toplevel)/.hard-eng/hook.sh" codex pretooluse'
    ]
    copilot = read_json(repository / ".github/hooks/hard-eng.json")
    assert copilot["version"] == 1 and copilot["hooks"]["sessionStart"][0]["timeoutSec"] == 300
    assert hook_commands(copilot, "sessionStart") == [
        'bash "$(git rev-parse --show-toplevel)/.hard-eng/bootstrap.sh" copilot'
    ]
    assert hook_commands(copilot, "preToolUse") == [
        'bash "$(git rev-parse --show-toplevel)/.hard-eng/hook.sh" copilot pretooluse'
    ]
    for relative in PRIVATE_FILES:
        assert (repository / relative).exists() or (repository / relative).is_symlink(), relative
    assert not (repository / ".claude/settings.local.json").exists()
    exclude = contract.git_exclude(repository).read_text(encoding="utf-8")
    assert "/CLAUDE.local.md\n" in exclude and "/.agents/hard-eng/\n" in exclude
    assert "/.claude/skills/plain-english\n" in exclude
    assert "/AGENTS.override.md" not in exclude and "/.claude/settings.json" not in exclude
    assert git_status(repository) == {*SHARED_FILES, "hard-eng.gates.json"}, git_status(repository)
    digest = contract.tree_digest(repository)
    again = state(repository, home, env, "prepare", "--agent", "codex")
    assert again["mode"] == "shared" and again["last_check"] == "pinned-verified", again
    repeated = state(repository, home, env, "prepare", "--shared", "--agent", "copilot")
    assert repeated["mode"] == "shared", repeated
    assert contract.tree_digest(repository) == digest, "repeated prepare changed the repository"
    verified = state(repository, home, env, "status", "--agent", "claude")
    assert verified["mode"] == "shared" and verified["wiring"] == "verified", verified
    contract.commit_all(repository, [*SHARED_FILES, "hard-eng.gates.json"])
    assert git_status(repository) == set()
    return repository


def assert_clone(root: Path, env: dict[str, str], repository: Path, base_url: str) -> None:
    clone = root / "clone"
    contract.run(["git", "clone", "-q", str(repository), str(clone)], cwd=root)
    home = root / "clone-home"
    env = clone_env(env, home, base_url)
    denied = shim(clone, env, "claude", "pretooluse")
    assert denied.startswith('{"hookSpecificOutput":{"hookEventName":"PreToolUse",') and DENY in denied, denied
    assert "not downloaded" in denied and "bash .hard-eng/bootstrap.sh claude" in denied, denied
    assert shim(clone, env, "claude", "posttooluse") == "" and shim(clone, env, "claude", "stop") == ""
    copilot_denied = shim(clone, env, "copilot", "pretooluse")
    assert copilot_denied.startswith('{"permissionDecision":"deny"'), copilot_denied
    subdirectory = clone / "nested/deeper"
    subdirectory.mkdir(parents=True)
    command = hook_commands(read_json(clone / ".claude/settings.json"), "PreToolUse")[0]
    from_subdirectory = contract.run(["bash", "-c", command], cwd=subdirectory, environment=env).stdout
    assert DENY in from_subdirectory, from_subdirectory
    assert git_status(clone) == set()
    first = bootstrap(clone, env, "claude")
    assert "downloaded and verified Hard Eng" in first.stderr, first.stderr
    output = json.loads(first.stdout)["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart" and output["reloadSkills"] is True
    assert contract.HARD_ENG_MARKER in output["additionalContext"]
    release = clone / ".agents/hard-eng/releases" / TAG
    assert (release / ".hard-eng-release.json").is_file() and (release / "bin/hard-eng").is_file()
    assert os.readlink(clone / ".agents/hard-eng/current") == f"releases/{TAG}"
    last_check = read_json(clone / ".agents/hard-eng/last-check.json")
    assert last_check["pin"] == read_json(clone / "hard-eng.gates.json")["hard_eng"]["pin"]
    assert last_check["last_result"] == "pinned-verified" and last_check["active_version"] == TAG
    for relative in PRIVATE_FILES:
        assert (clone / relative).exists() or (clone / relative).is_symlink(), relative
    assert git_status(clone) == set(), git_status(clone)
    second = bootstrap(clone, env, "claude")
    assert second.stdout == "" and "downloaded" not in second.stderr, (second.stdout, second.stderr)
    assert shim(clone, env, "claude", "pretooluse") == ""
    assert bootstrap(clone, env, "codex").stdout == ""
    verified = state(clone, home, env, "status", "--agent", "claude")
    assert verified["mode"] == "shared" and verified["wiring"] == "verified", verified
    assert verified["last_check"] == "pinned-verified" and verified["version"] == TAG, verified
    prepared = state(clone, home, env, "prepare", "--agent", "copilot")
    assert prepared["mode"] == "shared" and prepared["last_check"] == "pinned-verified", prepared
    with (release / "AGENTS.md").open("ab") as handle:
        handle.write(b"\ntampered\n")
    repaired = bootstrap(clone, env, "download")
    assert "downloaded and verified Hard Eng" in repaired.stderr, repaired.stderr
    assert b"tampered" not in (release / "AGENTS.md").read_bytes()
    shutil.rmtree(clone / ".agents/hard-eng")
    via_launcher = state(clone, home, env, "prepare", "--agent", "claude")
    assert via_launcher["mode"] == "shared" and (clone / ".agents/hard-eng/current").is_symlink(), via_launcher
    assert git_status(clone) == set(), git_status(clone)


def assert_download_failure(root: Path, env: dict[str, str], repository: Path, tampered_url: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, base_url, message in (
        ("offline", (root / "nowhere").as_uri(), "could not download"),
        ("tampered", tampered_url, "does not match the digest pinned"),
    ):
        clone = root / name
        contract.run(["git", "clone", "-q", str(repository), str(clone)], cwd=root)
        home = root / f"{name}-home"
        failed_env = clone_env(env, home, base_url)
        before = contract.tree_digest(clone)
        failed = bootstrap(clone, failed_env, "claude", check=False)
        assert failed.returncode == 1 and message in failed.stderr, (failed.returncode, failed.stderr)
        assert failed.stdout == ""
        assert not (clone / ".agents/hard-eng/current").exists()
        assert contract.tree_digest(clone) == before, "a failed bootstrap changed the clone"
        launcher = cli(clone, home, failed_env, "prepare", "--agent", "claude", check=False)
        assert launcher.returncode == 1 and "could not be downloaded" in launcher.stderr, launcher.stderr
        assert DENY in shim(clone, failed_env, "claude", "pretooluse")
        assert git_status(clone) == set(), git_status(clone)


def assert_merge(root: Path, env: dict[str, str]) -> None:
    repository = root / "origin"
    contract.init_repository(repository, marked=True)
    foreign_claude = {
        "permissions": {"allow": ["Bash(ls:*)"]},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo foreign"}]}]},
    }
    foreign_codex = {"hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo codex-foreign"}]}]}}
    contract.write(repository / ".claude/settings.json", json.dumps(foreign_claude, indent=2) + "\n")
    contract.write(repository / ".codex/hooks.json", json.dumps(foreign_codex) + "\n")
    contract.commit_all(repository, [".claude/settings.json", ".codex/hooks.json"])
    home = root / "home"
    home.mkdir()
    shared = state(repository, home, env, "prepare", "--shared", "--agent", "claude")
    assert shared["mode"] == "shared", shared
    claude = read_json(repository / ".claude/settings.json")
    assert claude["permissions"] == foreign_claude["permissions"]
    assert claude["hooks"]["PreToolUse"][0] == foreign_claude["hooks"]["PreToolUse"][0]
    assert len(claude["hooks"]["PreToolUse"]) == 2 and len(claude["hooks"]["SessionStart"]) == 1
    codex = read_json(repository / ".codex/hooks.json")
    assert codex["hooks"]["PreToolUse"][0] == foreign_codex["hooks"]["PreToolUse"][0]
    assert len(codex["hooks"]["PreToolUse"]) == 2
    assert git_status(repository) == {*SHARED_FILES, "hard-eng.gates.json"}, git_status(repository)
    foreign = root / "foreign"
    contract.init_repository(foreign, marked=True)
    contract.write(foreign / "AGENTS.override.md", "# Someone else's override\n")
    contract.commit_all(foreign, ["AGENTS.override.md"])
    before = contract.tree_digest(foreign)
    failed = cli(foreign, home, env, "prepare", "--shared", "--agent", "claude", check=False)
    assert failed.returncode == 1 and "has another owner: AGENTS.override.md" in failed.stderr, failed.stderr
    assert contract.tree_digest(foreign) == before, "a refused share changed the repository"
    assert git_status(foreign) == set()


def assert_global_machine(root: Path, env: dict[str, str], repository: Path, assets: Path, base_url: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    home = root / "home"
    contract.install_global(home, assets / "payload", agents=("claude",))
    agents_bin = root / "agents-bin"
    contract.fake_agents(agents_bin, ("claude",))
    machine_env = clone_env(env, home, base_url)
    machine_env["PATH"] = os.pathsep.join((str(agents_bin), machine_env["PATH"]))
    clone = root / "clone"
    contract.run(["git", "clone", "-q", str(repository), str(clone)], cwd=root)
    prepared = state(clone, home, machine_env, "prepare", "--agent", "claude")
    assert prepared["mode"] == "shared" and "global Hard Eng guard" in prepared["last_check"], prepared
    assert (clone / ".agents/hard-eng/current").is_symlink()
    assert (clone / ".agents/hard-eng/global-guard").read_text(encoding="utf-8") == "claude\n"
    assert shim(clone, machine_env, "claude", "pretooluse") == ""
    assert git_status(clone) == set(), git_status(clone)
    verified = state(clone, home, machine_env, "status", "--agent", "claude")
    assert verified["wiring"] == "verified; the global Hard Eng guard checks tool calls", verified
    codex = state(clone, home, machine_env, "prepare", "--agent", "codex")
    assert codex["mode"] == "shared" and "global Hard Eng is broken" in codex["last_check"], codex
    assert (clone / ".agents/hard-eng/global-guard").read_text(encoding="utf-8") == "claude\n"
    shutil.rmtree(home / ".agents")
    (home / ".local/bin/hard-eng").unlink()
    again = state(clone, home, machine_env, "prepare", "--agent", "claude")
    assert again["mode"] == "shared" and "global" not in again["last_check"], again
    assert not (clone / ".agents/hard-eng/global-guard").exists()


def assert_update_and_uninstall(root: Path, assets: Path, release: dict[str, object]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _, newer = contract.release_assets(assets / "newer", "b" * 40)
    newer_tag = str(newer["tag_name"])
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    contract.fake_gh(fake_bin, [release])
    env = contract.environment(fake_bin, assets)
    repository = root / "origin"
    contract.init_repository(repository, marked=True)
    foreign = {
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo foreign"}]}]}
    }
    contract.write(repository / ".claude/settings.json", json.dumps(foreign) + "\n")
    contract.commit_all(repository, [".claude/settings.json"])
    home = root / "home"
    home.mkdir()
    assert state(repository, home, env, "prepare", "--shared", "--agent", "claude")["version"] == TAG
    contract.commit_all(repository, [*SHARED_FILES, "hard-eng.gates.json"])
    contract.fake_gh(fake_bin, [newer, release])
    unchanged = state(repository, home, env, "prepare", "--agent", "claude")
    assert unchanged["version"] == TAG and git_status(repository) == set(), unchanged
    updated = state(repository, home, env, "update", "--shared", "--agent", "claude")
    assert updated["mode"] == "shared" and updated["version"] == newer_tag, updated
    assert read_json(repository / "hard-eng.gates.json")["hard_eng"]["pin"]["tag"] == newer_tag
    assert git_status(repository) == {"hard-eng.gates.json"}, git_status(repository)
    assert os.readlink(repository / ".agents/hard-eng/current") == f"releases/{newer_tag}"
    contract.commit_all(repository, ["hard-eng.gates.json"])
    clone = root / "clone"
    contract.run(["git", "clone", "-q", str(repository), str(clone)], cwd=root)
    assert cli(clone, home, env, "uninstall", "--shared").stdout.startswith("removed the shared Hard Eng wiring")
    assert git_status(clone) == {*SHARED_FILES, "hard-eng.gates.json"}, git_status(clone)
    assert read_json(clone / ".claude/settings.json") == foreign
    assert "pin" not in read_json(clone / "hard-eng.gates.json")["hard_eng"]
    refused = cli(repository, home, env, "uninstall", check=False)
    assert refused.returncode == 1 and "uninstall --shared" in refused.stderr, refused.stderr
    assert cli(repository, home, env, "uninstall", "--shared").stdout.startswith("removed the shared Hard Eng wiring")
    for relative in SHARED_FILES:
        assert (repository / relative).exists() == (relative == ".claude/settings.json"), relative
    assert read_json(repository / ".claude/settings.json") == foreign
    assert not (repository / ".hard-eng").exists() and not (repository / ".agents").exists()
    assert not (repository / "CLAUDE.local.md").exists() and not (repository / ".claude/skills").exists()
    policy = read_json(repository / "hard-eng.gates.json")["hard_eng"]
    assert "pin" not in policy and "wiring" not in policy and policy["channel"] == "prerelease"
    assert "# >>> hard-eng repository fallback >>>" not in contract.git_exclude(repository).read_text(encoding="utf-8")
    assert cli(repository, home, env, "uninstall", "--shared").stdout.startswith(
        "Hard Eng shared wiring is not installed"
    )
    assert git_status(repository) == {*SHARED_FILES, "hard-eng.gates.json"}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-shared-") as temporary:
        root = Path(temporary)
        assets, release = contract.release_assets(root / "release")
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        contract.fake_gh(fake_bin, [release])
        contract.fake_agents(fake_bin, ("codex",))
        env = contract.environment(fake_bin, assets)
        base_url = downloads(assets)
        tampered_url = downloads(assets, "tampered", tamper=True)
        repository = assert_share(root / "share", env, assets)
        assert_clone(root / "share", env, repository, base_url)
        assert_download_failure(root / "failure", env, repository, tampered_url)
        assert_merge(root / "merge", env)
        assert_global_machine(root / "global", env, repository, assets, base_url)
        assert_update_and_uninstall(root / "update", assets, release)
    print("repository-native-shared-contract: PASS share clone failure merge global update uninstall")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
