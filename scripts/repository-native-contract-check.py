#!/usr/bin/env python3
"""Isolated contracts for repository-native Hard Eng startup."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "bin/hard-eng"
COMMIT = "a" * 40
TAG = f"v0.1.0-alpha.g{COMMIT}"


def run(
    command: list[str], *, cwd: Path, environment: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    value = subprocess.run(command, check=False, cwd=cwd, env=environment, capture_output=True, text=True, timeout=90)
    if check and value.returncode != 0:
        raise AssertionError(
            f"command failed ({value.returncode}): {' '.join(command)}\n{value.stdout}\n{value.stderr}"
        )
    return value


def write(path: Path, value: str | bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_bytes(value)
    path.chmod(mode)


def init_repository(root: Path, *, marked: bool, policy: bool = True) -> None:
    root.mkdir(parents=True)
    write(root / "AGENTS.md", "# Repository rules\n\nREPOSITORY_RULE_MARKER = loaded\n")
    write(root / "CLAUDE.md", "@AGENTS.md\n")
    if marked:
        marker: dict[str, object] = {"schema_version": 1}
        if policy:
            marker["hard_eng"] = {
                "channel": "prerelease",
                "release_repository": "sgaabdu4/hard-eng",
                "schema_version": 1,
            }
        write(root / "hard-eng.gates.json", json.dumps(marker) + "\n")
    run(["git", "init", "-q", "-b", "main"], cwd=root)
    run(["git", "add", "AGENTS.md", "CLAUDE.md", *(["hard-eng.gates.json"] if marked else [])], cwd=root)
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


def payload(root: Path) -> None:
    write(root / "AGENTS.md", "# Hard Eng rules\n\nHARD_ENG_RULE_MARKER = loaded\n")
    write(root / "skills/plain-english/SKILL.md", "---\nname: plain-english\n---\nUse plain English.\n")
    write(root / "scripts/hooks/agent-hook.sh", "#!/bin/bash\nexit 0\n", 0o755)
    for relative in (
        "agents/he-learn/claude.md",
        "agents/he-learn/codex.toml",
        "agents/he-learn/copilot.agent.md",
        "output-styles/plain-english.md",
    ):
        source = ROOT / relative
        write(root / relative, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
    for source in sorted((ROOT / "runtime/repository_native").glob("*.py")):
        relative = source.relative_to(ROOT)
        write(root / relative, source.read_bytes(), stat.S_IMODE(source.stat().st_mode))
    write(root / "bin/hard-eng", (ROOT / "bin/hard-eng").read_bytes(), 0o755)


def release_assets(root: Path, commit: str = COMMIT) -> tuple[Path, dict[str, object]]:
    tag = f"v0.1.0-alpha.g{commit}"
    source = root / "payload"
    payload(source)
    archive = root / f"hard-eng-{tag}.tar.gz"
    prefix = f"hard-eng-{tag}"
    with tarfile.open(archive, "w:gz", format=tarfile.PAX_FORMAT) as bundle:
        directory = tarfile.TarInfo(prefix)
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o755
        bundle.addfile(directory)
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source).as_posix()
            info = bundle.gettarinfo(str(path), arcname=f"{prefix}/{relative}")
            if info.isfile():
                with path.open("rb") as handle:
                    bundle.addfile(info, handle)
            else:
                bundle.addfile(info)
    archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest = {
        "archive": {"name": archive.name, "sha256": archive_digest, "size": archive.stat().st_size},
        "compatibility": {
            "agents": ["claude", "codex", "copilot"],
            "node": ">=26.0.0",
            "platforms": ["darwin-arm64", "darwin-x64", "linux-arm64", "linux-x64"],
            "python": ">=3.12.0",
        },
        "launcher_schema": 1,
        "minimum_supported_version": f"v0.1.0-alpha.g{'0' * 40}",
        "product": "hard-eng",
        "schema_version": 3,
        "source_commit": commit,
        "version": tag,
    }
    manifest_path = root / f"hard-eng-{tag}.manifest.json"
    write(manifest_path, json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    release = {
        "assets": [
            {"digest": f"sha256:{archive_digest}", "name": archive.name, "size": archive.stat().st_size},
            {
                "digest": f"sha256:{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}",
                "name": manifest_path.name,
                "size": manifest_path.stat().st_size,
            },
        ],
        "draft": False,
        "immutable": True,
        "prerelease": True,
        "tag_name": tag,
        "target_commitish": commit,
    }
    return root, release


def fake_gh(bin_root: Path, assets: Path, releases: list[dict[str, object]]) -> Path:
    executable = bin_root / "gh"
    script = f"""#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
releases = json.loads({json.dumps(json.dumps(releases))})
args = sys.argv[1:]
if args[:1] == ["api"]:
    endpoint = next((item for item in args[1:] if item.startswith("repos/")), "")
    if "/compare/" in endpoint:
        pair = endpoint.rsplit("/", 1)[-1]
        base, head = pair.split("...", 1)
        order = {{item["target_commitish"]: index for index, item in enumerate(reversed(releases))}}
        status = "identical" if base == head else "ahead" if order[head] > order[base] else "behind"
        print(json.dumps({{"status": status}}))
    elif "/releases/tags/" in endpoint:
        tag = endpoint.rsplit("/", 1)[-1]
        print(json.dumps(next(item for item in releases if item["tag_name"] == tag)))
    elif endpoint.endswith("/releases"):
        print(json.dumps(releases))
    else:
        raise SystemExit("unknown fake API endpoint: " + endpoint)
elif args[:2] == ["release", "download"]:
    tag = args[2]
    release = next(item for item in releases if item["tag_name"] == tag)
    destination = Path(args[args.index("--dir") + 1])
    destination.mkdir(parents=True, exist_ok=True)
    source = Path(os.environ["HARD_ENG_TEST_ASSETS"])
    for name in (release["assets"][0]["name"], release["assets"][1]["name"]):
        shutil.copy2(next(source.rglob(name)), destination / name)
elif args[:2] == ["release", "verify"]:
    print(json.dumps([{{"verified": True}}]))
else:
    raise SystemExit("unknown fake gh command: " + " ".join(args))
"""
    write(executable, script, 0o755)
    return executable


def environment(fake_bin: Path, assets: Path) -> dict[str, str]:
    value = dict(os.environ)
    value["PATH"] = os.pathsep.join((str(fake_bin), value.get("PATH", "")))
    value["HARD_ENG_TEST_ASSETS"] = str(assets)
    value["PYTHONDONTWRITEBYTECODE"] = "1"
    return value


def launcher(
    repository: Path, home: Path, environment_value: dict[str, str], *, agent: str = "codex", check: bool = True
) -> subprocess.CompletedProcess[str]:
    return run(
        [str(LAUNCHER), "start", "--repo", str(repository), "--home", str(home), "--dry-run", agent],
        cwd=repository,
        environment=environment_value,
        check=check,
    )


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if ".git" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        if path.is_symlink():
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()


def tracked_digest(repository: Path) -> str:
    names = run(["git", "ls-files", "-z"], cwd=repository).stdout.split("\0")
    digest = hashlib.sha256()
    for name in sorted(filter(None, names)):
        digest.update(name.encode())
        digest.update((repository / name).read_bytes())
    return digest.hexdigest()


def install_global(home: Path, source: Path, agent: str = "codex") -> None:
    global_root = home / ".agents"
    shutil.copytree(source, global_root)
    write(global_root / ".hard-eng-release.json", json.dumps({"source_commit": COMMIT, "version": TAG}) + "\n")
    (home / ".local/bin").mkdir(parents=True)
    (home / ".local/bin/hard-eng").symlink_to(global_root / "bin/hard-eng")
    if agent == "codex":
        (home / ".codex").mkdir(parents=True)
        (home / ".codex/AGENTS.md").symlink_to(global_root / "AGENTS.md")
        (home / ".codex/agents").mkdir()
        (home / ".codex/agents/he-learn.toml").symlink_to(global_root / "agents/he-learn/codex.toml")
        write(
            home / ".codex/hooks.json",
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
                }
            ),
        )
        write(home / ".codex/config.toml", "[mcp_servers.codebase-memory]\ncommand = 'memory'\n")
    elif agent == "claude":
        (home / ".claude").mkdir(parents=True)
        write(home / ".claude/CLAUDE.md", f"@{(global_root / 'AGENTS.md').resolve()}\n")
        (home / ".claude/skills").symlink_to(global_root / "skills", target_is_directory=True)
        (home / ".claude/output-styles").symlink_to(global_root / "output-styles", target_is_directory=True)
        (home / ".claude/agents").mkdir()
        (home / ".claude/agents/he-learn.md").symlink_to(global_root / "agents/he-learn/claude.md")
        write(
            home / ".claude/settings.json",
            json.dumps(
                {
                    "outputStyle": "plain-english",
                    "hooks": {
                        "PreToolUse": [
                            {
                                "hooks": [
                                    {
                                        "command": f"bash {global_root / 'scripts/hooks/agent-hook.sh'} claude pretooluse",
                                        "type": "command",
                                    }
                                ]
                            }
                        ]
                    },
                }
            ),
        )
        write(home / ".claude.json", json.dumps({"mcpServers": {"codebase-memory": {}}}))
    elif agent == "copilot":
        (home / ".copilot/agents").mkdir(parents=True)
        (home / ".copilot/agents/he-learn.agent.md").symlink_to(global_root / "agents/he-learn/copilot.agent.md")
        write(
            home / ".zshenv",
            "# >>> hard-eng managed Copilot instructions >>>\n"
            'export COPILOT_CUSTOM_INSTRUCTIONS_DIRS="$HOME/.agents"\n'
            "# <<< hard-eng managed Copilot instructions <<<\n",
        )
        write(
            home / ".copilot/hooks/hard-eng.json",
            json.dumps(
                {
                    "hooks": {
                        "preToolUse": [
                            {
                                "bash": f"bash {global_root / 'scripts/hooks/agent-hook.sh'} copilot pretooluse",
                                "type": "command",
                            }
                        ]
                    },
                    "version": 1,
                }
            ),
        )
        write(home / ".copilot/mcp-config.json", json.dumps({"mcpServers": {"codebase-memory": {}}}))
        write(home / ".copilot/settings.json", json.dumps({"includeCoAuthoredBy": False}))


def assert_matrix(root: Path, env: dict[str, str], release_root: Path) -> None:
    results: dict[tuple[bool, bool], dict[str, object]] = {}
    for marked in (False, True):
        for global_install in (False, True):
            case = root / f"matrix-m{int(marked)}-g{int(global_install)}"
            repository = case / "repository"
            home = case / "home"
            home.mkdir(parents=True)
            init_repository(repository, marked=marked)
            if global_install:
                install_global(home, release_root)
            before = tracked_digest(repository)
            home_before = tree_digest(home)
            result = launcher(repository, home, env)
            value = json.loads(result.stdout)
            results[(marked, global_install)] = value
            assert tracked_digest(repository) == before
            expected = "global" if marked and global_install else "fallback" if marked else "pass-through"
            assert value["mode"] == expected, (marked, global_install, value)
            if not marked:
                assert tree_digest(home) == home_before
                assert not (repository / ".agents/hard-eng").exists()
                assert not (repository / "AGENTS.override.md").exists()
            elif global_install:
                assert not (repository / ".agents/hard-eng").exists()
                assert not (repository / "AGENTS.override.md").exists()
            else:
                assert (repository / ".agents/hard-eng/current").is_symlink()
                assert (repository / "AGENTS.override.md").is_file()
                assert (repository / ".agents/skills/plain-english").is_symlink()
                assert (repository / ".codex/agents/he-learn.toml").is_symlink()
                assert (repository / ".claude/agents/he-learn.md").is_symlink()
                assert (repository / ".github/agents/he-learn.agent.md").is_symlink()
                assert (repository / ".claude/output-styles/plain-english.md").is_symlink()
                assert (repository / ".codex/hooks.json").is_file()
                assert not (repository / ".copilot").exists()
                assert value["version"] == TAG
    assert set(results) == {(False, False), (False, True), (True, False), (True, True)}


def assert_provider_adapters(root: Path, env: dict[str, str], release_root: Path) -> None:
    for agent in ("claude", "copilot"):
        for global_install in (False, True):
            case = root / f"{agent}-g{int(global_install)}"
            repository = case / "repository"
            home = case / "home"
            home.mkdir(parents=True)
            init_repository(repository, marked=True)
            if global_install:
                install_global(home, release_root, agent)
            value = json.loads(launcher(repository, home, env, agent=agent).stdout)
            assert value["mode"] == ("global" if global_install else "fallback")
            command = value["command"]
            assert ("--mcp-config" if agent == "claude" else "--additional-mcp-config") in command
            if global_install:
                assert not (repository / ".agents/hard-eng").exists()
                continue
            if agent == "claude":
                assert (repository / ".claude/settings.local.json").is_file()
                assert (repository / "CLAUDE.local.md").read_text(encoding="utf-8") == "@AGENTS.override.md\n"
            else:
                assert (repository / ".github/hooks/hard-eng.json").is_file()
                assert (repository / ".agents/hard-eng/copilot-instructions/AGENTS.md").is_file()


def assert_failure_and_cache(root: Path, env: dict[str, str]) -> None:
    partial = root / "partial"
    repository = partial / "repository"
    home = partial / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    (home / ".agents").mkdir()
    write(home / ".agents/AGENTS.md", "partial\n")
    write(home / ".agents/scripts/hooks/agent-hook.sh", "#!/bin/bash\n", 0o755)
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "partial or broken global" in failed.stderr
    assert not (repository / ".agents/hard-eng/current").exists()

    generic = root / "generic-agent-skills"
    repository = generic / "repository"
    home = generic / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    write(home / ".agents/skills/example/SKILL.md", "# Example\n")
    prepared = json.loads(launcher(repository, home, env).stdout)
    assert prepared["mode"] == "fallback"

    conflict = root / "generated-file-conflict"
    repository = conflict / "repository"
    home = conflict / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    write(repository / "AGENTS.override.md", "user-owned\n")
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "another owner" in failed.stderr
    assert (repository / "AGENTS.override.md").read_text(encoding="utf-8") == "user-owned\n"
    assert not (repository / ".agents/hard-eng/current").exists()

    missing_policy = root / "missing-policy"
    repository = missing_policy / "repository"
    home = missing_policy / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True, policy=False)
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "no hard_eng release policy" in failed.stderr

    redirected = root / "redirected-release"
    repository = redirected / "repository"
    home = redirected / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    marker = json.loads((repository / "hard-eng.gates.json").read_text(encoding="utf-8"))
    marker["hard_eng"]["release_repository"] = "attacker/hard-eng"
    write(repository / "hard-eng.gates.json", json.dumps(marker) + "\n")
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "must be sgaabdu4/hard-eng" in failed.stderr
    assert not (repository / ".agents/hard-eng").exists()

    redirected_parent = root / "redirected-parent"
    repository = redirected_parent / "repository"
    home = redirected_parent / "home"
    outside = redirected_parent / "outside"
    home.mkdir(parents=True)
    outside.mkdir()
    init_repository(repository, marked=True)
    (repository / ".agents").symlink_to(outside, target_is_directory=True)
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "fallback parent is unsafe" in failed.stderr
    assert not tuple(outside.iterdir())

    cached = root / "cached"
    repository = cached / "repository"
    home = cached / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    first = json.loads(launcher(repository, home, env).stdout)
    assert first["last_check"] == "online-verified"
    status = json.loads(
        run(
            [str(LAUNCHER), "status", "--repo", str(repository), "--home", str(home), "--json"],
            cwd=repository,
            environment=env,
        ).stdout
    )
    assert status["mode"] == "fallback" and status["last_check"] == "online-verified"
    write(repository / ".agents/hard-eng/user-note.txt", "retain\n")
    offline_bin = root / "offline-bin"
    offline_bin.mkdir()
    for command in ("node", "python3"):
        target = shutil.which(command)
        assert target is not None
        (offline_bin / command).symlink_to(target)
    write(offline_bin / "gh", "#!/bin/sh\nprintf '%s\\n' 'network is unreachable' >&2\nexit 1\n", 0o755)
    offline = dict(env)
    offline["PATH"] = os.pathsep.join((str(offline_bin), "/usr/bin", "/bin"))
    second = json.loads(launcher(repository, home, offline).stdout)
    assert second["last_check"] == "offline-cache"
    before = tracked_digest(repository)
    exclude = Path(
        run(["git", "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"], cwd=repository).stdout.strip()
    )
    with exclude.open("a", encoding="utf-8") as output:
        output.write("# user update after Hard Eng setup\n")
    run([str(LAUNCHER), "uninstall", "--repo", str(repository)], cwd=repository, environment=env)
    assert tracked_digest(repository) == before
    assert not (repository / ".agents/hard-eng/current").exists()
    assert (repository / ".agents/hard-eng/releases" / TAG).is_dir()
    assert (repository / ".agents/hard-eng/user-note.txt").read_text(encoding="utf-8") == "retain\n"
    assert not (repository / "AGENTS.override.md").exists()
    exclude_after = exclude.read_text(encoding="utf-8")
    assert "# user update after Hard Eng setup" in exclude_after
    assert "hard-eng repository fallback" not in exclude_after

    tampered = root / "tampered-cache"
    repository = tampered / "repository"
    home = tampered / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    launcher(repository, home, env)
    current = (repository / ".agents/hard-eng/current").resolve(strict=True)
    write(current / "AGENTS.md", "tampered\n")
    failed = launcher(repository, home, offline, check=False)
    assert failed.returncode == 1 and "no allowed verified cache" in failed.stderr


def assert_concurrent_start(root: Path, env: dict[str, str]) -> None:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    command = [str(LAUNCHER), "start", "--repo", str(repository), "--home", str(home), "--dry-run", "codex"]
    processes = [
        subprocess.Popen(command, cwd=repository, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=90) + (process.returncode,) for process in processes]
    assert all(result[2] == 0 for result in results), results
    assert all(json.loads(result[0])["version"] == TAG for result in results)


def assert_quoted_path(root: Path, env: dict[str, str]) -> None:
    repository = root / 'repository-"quoted"'
    home = root / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    value = json.loads(launcher(repository, home, env).stdout)
    command = value["command"]
    overrides = [command[index + 1] for index, argument in enumerate(command[:-1]) if argument == "-c"]
    parsed = tomllib.loads("\n".join(overrides))
    assert parsed["mcp_servers"]["hard_eng"]["args"][-1] == str(repository.resolve())
    copilot_bridge = repository / ".agents/hard-eng/copilot-instructions/AGENTS.md"
    assert "Read and follow `./AGENTS.md` first." in copilot_bridge.read_text(encoding="utf-8")
    assert (repository / ".agents/hard-eng/current").is_symlink()


def assert_update(root: Path) -> None:
    assets_root = root / "assets"
    first_assets, first = release_assets(assets_root / "first", "a" * 40)
    _, second = release_assets(assets_root / "second", "b" * 40)
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_gh(fake_bin, assets_root, [first])
    env = environment(fake_bin, assets_root)
    repository = root / "repository"
    home = root / "home"
    home.mkdir()
    init_repository(repository, marked=True)
    first_tag = first.get("tag_name")
    second_tag = second.get("tag_name")
    assert isinstance(first_tag, str) and isinstance(second_tag, str)
    initial = json.loads(launcher(repository, home, env).stdout)
    assert initial["version"] == first_tag
    altered = json.loads(json.dumps(second))
    altered["assets"][0]["digest"] = f"sha256:{'0' * 64}"
    fake_gh(fake_bin, assets_root, [altered, first])
    retained = json.loads(launcher(repository, home, env).stdout)
    assert retained["version"] == first_tag
    assert retained["newest_allowed_version"] == second_tag
    assert retained["last_check"].startswith("update-failed-using-verified-cache:")
    fake_gh(fake_bin, assets_root, [second, first])
    updated = json.loads(launcher(repository, home, env).stdout)
    assert updated["version"] == second_tag
    releases = repository / ".agents/hard-eng/releases"
    assert (releases / first_tag).is_dir()
    assert (releases / second_tag).is_dir()
    assert (repository / ".agents/hard-eng/current").resolve() == (releases / second_tag).resolve()
    assert first_assets.is_dir()


def assert_unsafe_archive(root: Path) -> None:
    assets, release = release_assets(root / "assets")
    release_asset_values = release.get("assets")
    assert isinstance(release_asset_values, list) and len(release_asset_values) == 2
    archive_asset, manifest_asset = release_asset_values
    assert isinstance(archive_asset, dict) and isinstance(manifest_asset, dict)
    archive_name = archive_asset.get("name")
    manifest_name = manifest_asset.get("name")
    assert isinstance(archive_name, str) and isinstance(manifest_name, str)
    archive = assets / archive_name
    prefix = f"hard-eng-{TAG}"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo(f"{prefix}/../../escaped")
        info.size = 4
        bundle.addfile(info, io.BytesIO(b"bad\n"))
    manifest_path = assets / manifest_name
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_archive = manifest.get("archive")
    assert isinstance(manifest_archive, dict)
    manifest_archive["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest_archive["size"] = archive.stat().st_size
    write(manifest_path, json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    archive_asset["digest"] = f"sha256:{hashlib.sha256(archive.read_bytes()).hexdigest()}"
    archive_asset["size"] = archive.stat().st_size
    manifest_asset["digest"] = f"sha256:{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}"
    manifest_asset["size"] = manifest_path.stat().st_size
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_gh(fake_bin, assets, [release])
    env = environment(fake_bin, assets)
    repository = root / "repository"
    home = root / "home"
    home.mkdir()
    init_repository(repository, marked=True)
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "unsafe release archive path" in failed.stderr
    assert not (root / "escaped").exists()


def assert_mcp(root: Path) -> None:
    repository = root / "mcp-repository"
    init_repository(repository, marked=False)
    messages = (
        "\n".join(
            (
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "hard_eng_status", "arguments": {}},
                    }
                ),
            )
        )
        + "\n"
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "runtime/repository_native/mcp_server.py"), "--repo", str(repository)],
        check=False,
        input=messages,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    responses = [json.loads(line) for line in result.stdout.splitlines()]
    assert responses[0]["result"]["serverInfo"]["name"] == "hard-eng"
    assert responses[1]["result"]["tools"][0]["name"] == "hard_eng_status"
    assert responses[2]["result"]["structuredContent"]["mode"] == "unprotected"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-repository-native-") as temporary:
        root = Path(temporary)
        assets, release = release_assets(root / "release")
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_gh(fake_bin, assets, [release])
        env = environment(fake_bin, assets)
        assert_matrix(root, env, assets / "payload")
        assert_provider_adapters(root / "providers", env, assets / "payload")
        assert_failure_and_cache(root, env)
        assert_concurrent_start(root / "concurrent", env)
        assert_quoted_path(root / "quoted", env)
        assert_update(root / "update")
        assert_unsafe_archive(root / "unsafe")
        assert_mcp(root)
    print(
        "repository-native-contract: PASS matrix=4 providers=claude+codex+copilot safeguards=PASS generic-skills=PASS "
        "offline-cache=PASS tamper=PASS concurrency=PASS quoted-path=PASS update=PASS "
        "unsafe-archive=PASS uninstall=PASS mcp=PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
