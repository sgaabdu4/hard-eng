#!/usr/bin/env python3
from __future__ import annotations

import atexit
import hashlib
import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "bin/hard-eng"
COMMIT = "a" * 40
TAG = f"v0.1.0-alpha.g{COMMIT}"
AGENTS = ("codex", "claude", "copilot")
AGENT_HOMES = {"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR", "copilot": "COPILOT_HOME"}
TOOLS = ("bash", "git", "node", "npm", "npx", "perl", "python3", "sh")
GIT_CONFIG = Path(tempfile.mkdtemp(prefix="hard-eng-gitconfig-")) / "gitconfig"
GIT_CONFIG.write_text("[core]\n\texcludesFile = /dev/null\n\thooksPath = /dev/null\n")
atexit.register(shutil.rmtree, GIT_CONFIG.parent, True)
os.environ["GIT_CONFIG_GLOBAL"] = str(GIT_CONFIG)
os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
HARD_ENG_MARKER = "HARD_ENG_RULE_MARKER = loaded"
REPOSITORY_MARKER = "REPOSITORY_RULE_MARKER = loaded"
IDENTITY = ("-c", "user.name=Hard Eng Test", "-c", "user.email=hard-eng@example.invalid")
OWNER_BLOCK = (
    "# >>> hard-eng repository owners >>>\n/AGENTS.md\n/CLAUDE.md\n/hard-eng.gates.json\n"
    "# <<< hard-eng repository owners <<<\n"
)
POLICY = {"channel": "prerelease", "release_repository": "sgaabdu4/hard-eng", "schema_version": 1}


def run(
    command: list[str], *, cwd: Path, environment: dict[str, str] | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    value = subprocess.run(command, check=False, cwd=cwd, env=environment, capture_output=True, text=True, timeout=120)
    if check and value.returncode != 0:
        raise AssertionError(
            f"command failed ({value.returncode}): {' '.join(command)}\n{value.stdout}\n{value.stderr}"
        )
    return value


def write(path: Path, value: str | bytes, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value.encode() if isinstance(value, str) else value)
    path.chmod(mode)


def commit_all(root: Path, paths: list[str]) -> None:
    run(["git", "add", *paths], cwd=root)
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


def init_repository(root: Path, *, marked: bool, policy: bool = True) -> None:
    root.mkdir(parents=True)
    write(root / "AGENTS.md", f"# Repository rules\n\n{REPOSITORY_MARKER}\n")
    write(root / "CLAUDE.md", "@AGENTS.md\n")
    if marked:
        marker: dict[str, object] = {"schema_version": 1}
        if policy:
            marker["hard_eng"] = POLICY
        write(root / "hard-eng.gates.json", json.dumps(marker) + "\n")
    run(["git", "init", "-q", "-b", "main"], cwd=root)
    commit_all(root, ["AGENTS.md", "CLAUDE.md", *(["hard-eng.gates.json"] if marked else [])])


def payload(root: Path) -> None:
    write(root / "AGENTS.md", f"# Hard Eng rules\n\n{HARD_ENG_MARKER}\n")
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


def asset(path: Path) -> dict[str, object]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"digest": f"sha256:{digest}", "name": path.name, "size": path.stat().st_size}


def release_assets(root: Path, commit: str = COMMIT) -> tuple[Path, dict[str, object]]:
    tag = f"v0.1.0-alpha.g{commit}"
    source = root / "payload"
    if not source.exists():
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
        "assets": [asset(archive), asset(manifest_path)],
        "draft": False,
        "immutable": True,
        "prerelease": True,
        "tag_name": tag,
        "target_commitish": commit,
    }
    return root, release


def fake_gh(bin_root: Path, releases: list[dict[str, object]]) -> Path:
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
    if os.environ.get("HARD_ENG_TEST_TAMPER") == "1":
        with (destination / release["assets"][0]["name"]).open("ab") as handle:
            handle.write(b"tampered")
elif args[:2] == ["release", "verify"]:
    if os.environ.get("HARD_ENG_TEST_FAIL_VERIFY") == "1":
        raise SystemExit(1)
    print(json.dumps([{{"verified": True}}]))
else:
    raise SystemExit("unknown fake gh command: " + " ".join(args))
"""
    write(executable, script, 0o755)
    return executable


def fake_agents(bin_root: Path, agents: tuple[str, ...]) -> None:
    for agent in agents:
        write(bin_root / agent, "#!/bin/sh\nexit 0\n", 0o755)


def tools_path(root: Path) -> Path:
    tools = root / "tools"
    if not tools.exists():
        tools.mkdir()
        for name in TOOLS:
            target = shutil.which(name)
            if target is not None:
                (tools / name).symlink_to(target)
    return tools


def environment(fake_bin: Path, assets: Path, *, extra_path: tuple[Path, ...] = ()) -> dict[str, str]:
    value = {
        name: item
        for name, item in os.environ.items()
        if name not in {"CODEX_HOME", "CLAUDE_CONFIG_DIR", "COPILOT_HOME", "XDG_CONFIG_HOME"}
    }
    value["PATH"] = os.pathsep.join(
        (str(fake_bin), *(str(path) for path in extra_path), str(tools_path(assets.parent)), "/usr/bin", "/bin")
    )
    value["HARD_ENG_TEST_ASSETS"] = str(assets)
    value["PYTHONDONTWRITEBYTECODE"] = "1"
    return value


def launcher(
    repository: Path,
    home: Path,
    environment_value: dict[str, str],
    *,
    agent: str = "codex",
    command: str = "prepare",
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    arguments = [str(LAUNCHER), command, "--repo", str(repository), "--home", str(home)]
    if command != "uninstall":
        arguments.extend(["--agent", agent, "--json"])
    return run(arguments, cwd=repository, environment=environment_value, check=check)


def prepared(repository: Path, home: Path, environment_value: dict[str, str], *, agent: str = "codex") -> dict:
    return json.loads(launcher(repository, home, environment_value, agent=agent).stdout)


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


def git_exclude(repository: Path) -> Path:
    return Path(
        run(["git", "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"], cwd=repository).stdout.strip()
    )


def tracked_digest(repository: Path) -> str:
    names = run(["git", "ls-files", "-z"], cwd=repository).stdout.split("\0")
    digest = hashlib.sha256()
    for name in sorted(filter(None, names)):
        digest.update(name.encode())
        digest.update((repository / name).read_bytes())
    return digest.hexdigest()


def hook_settings(command: str, nested_key: str, nested: bool, *, style: bool = False) -> str:
    hook: dict[str, object] = {nested_key: command, "type": "command"}
    style_value = {"outputStyle": "Plain English"} if style else {}
    value = (
        {"hooks": {"PreToolUse": [{"hooks": [hook]}]}, **style_value}
        if nested
        else {"hooks": {"preToolUse": [hook]}, "version": 1}
    )
    return json.dumps(value, indent=2) + "\n"


def link(path: Path, target: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_symlink():
        path.symlink_to(target, target_is_directory=target.is_dir())


def install_global(home: Path, source: Path, agents: tuple[str, ...] = ("codex",)) -> None:
    global_root = home / ".agents"
    shutil.copytree(source, global_root)
    write(global_root / ".hard-eng-release.json", json.dumps({"source_commit": COMMIT, "version": TAG}) + "\n")
    wire_global(home, global_root, agents)


def wire_global(home: Path, global_root: Path, agents: tuple[str, ...]) -> None:
    link(home / ".local/bin/hard-eng", global_root / "bin/hard-eng")
    hook = f"bash {global_root / 'scripts/hooks/agent-hook.sh'}"
    if "codex" in agents:
        link(home / ".codex/AGENTS.md", global_root / "AGENTS.md")
        link(home / ".codex/agents/he-learn.toml", global_root / "agents/he-learn/codex.toml")
        write(home / ".codex/hooks.json", hook_settings(f"{hook} codex pretooluse", "command", True))
        write(home / ".codex/config.toml", "[mcp_servers.codebase-memory]\ncommand = 'memory'\n")
    if "claude" in agents:
        write(home / ".claude/CLAUDE.md", f"@{(global_root / 'AGENTS.md').resolve()}\n")
        link(home / ".claude/skills", global_root / "skills")
        link(home / ".claude/output-styles", global_root / "output-styles")
        link(home / ".claude/agents/he-learn.md", global_root / "agents/he-learn/claude.md")
        write(home / ".claude/settings.json", hook_settings(f"{hook} claude pretooluse", "command", True, style=True))
        write(home / ".claude.json", json.dumps({"mcpServers": {"codebase-memory": {}}}))
    if "copilot" in agents:
        link(home / ".copilot/copilot-instructions.md", global_root / "AGENTS.md")
        link(home / ".copilot/agents/he-learn.agent.md", global_root / "agents/he-learn/copilot.agent.md")
        write(home / ".copilot/hooks/hard-eng.json", hook_settings(f"{hook} copilot pretooluse", "bash", False))
        write(home / ".copilot/mcp-config.json", json.dumps({"mcpServers": {"codebase-memory": {}}}))
        write(home / ".copilot/settings.json", json.dumps({"includeCoAuthoredBy": False}))


def assert_fallback_files(repository: Path, expected_status: str = "") -> None:
    assert (repository / ".agents/hard-eng/current").is_symlink()
    override = (repository / "AGENTS.override.md").read_text(encoding="utf-8")
    assert REPOSITORY_MARKER in override and HARD_ENG_MARKER in override
    assert override.index(REPOSITORY_MARKER) < override.index(HARD_ENG_MARKER)
    assert (repository / "CLAUDE.local.md").read_text(encoding="utf-8") == "@.agents/hard-eng/current/AGENTS.md\n"
    instructions = (repository / ".github/instructions/hard-eng.instructions.md").read_text(encoding="utf-8")
    assert instructions.startswith('---\napplyTo: "**"\n---\n') and HARD_ENG_MARKER in instructions
    claude_settings = json.loads((repository / ".claude/settings.local.json").read_text(encoding="utf-8"))
    assert claude_settings["outputStyle"] == "Plain English"
    assert "agent-hook.sh" in claude_settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    codex_hooks = json.loads((repository / ".codex/hooks.json").read_text(encoding="utf-8"))
    hook_path = shlex.split(codex_hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"])[1]
    assert Path(hook_path).samefile(repository / ".agents/hard-eng/current/scripts/hooks/agent-hook.sh")
    copilot_hooks = json.loads((repository / ".github/hooks/hard-eng.json").read_text(encoding="utf-8"))
    assert copilot_hooks["version"] == 1 and "copilot pretooluse" in copilot_hooks["hooks"]["preToolUse"][0]["bash"]
    for relative in (
        ".agents/skills/plain-english",
        ".claude/skills/plain-english",
        ".codex/agents/he-learn.toml",
        ".claude/agents/he-learn.md",
        ".github/agents/he-learn.agent.md",
        ".claude/output-styles/plain-english.md",
    ):
        assert (repository / relative).is_symlink(), relative
    assert not (repository / ".agents/hard-eng/mcp.json").exists()
    assert not (repository / ".copilot").exists()
    assert run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout == expected_status


def assert_matrix(root: Path, env: dict[str, str], release_root: Path) -> None:
    for marked in (False, True):
        for global_install in (False, True):
            case = root / f"matrix-m{int(marked)}-g{int(global_install)}"
            repository = case / 'repository "quoted"'
            home = case / "home"
            home.mkdir(parents=True)
            init_repository(repository, marked=marked)
            if global_install:
                install_global(home, release_root)
            before = tracked_digest(repository)
            home_before = tree_digest(home)
            value = prepared(repository, home, env)
            assert tracked_digest(repository) == before
            expected = "global" if marked and global_install else "fallback" if marked else "pass-through"
            assert value["mode"] == expected, (marked, global_install, value)
            if expected == "fallback":
                assert value["version"] == TAG and value["wiring"] == "verified"
                assert_fallback_files(repository)
            else:
                assert not (repository / ".agents").exists() and not (repository / "AGENTS.override.md").exists()
            if not marked:
                assert tree_digest(home) == home_before
            status = json.loads(launcher(repository, home, env, command="status").stdout)
            assert status["mode"] == expected and status["wiring"] == "verified"


def assert_agents(root: Path, env: dict[str, str], fake_bin: Path, release_root: Path) -> None:
    for agent in ("claude", "copilot"):
        case = root / f"{agent}-global"
        repository = case / "repository"
        home = case / "home"
        home.mkdir(parents=True)
        init_repository(repository, marked=True)
        install_global(home, release_root, ("codex",))
        assert prepared(repository, home, env, agent=agent)["mode"] == "global"
        fake_agents(fake_bin, (agent,))
        rejected = launcher(repository, home, env, agent=agent, check=False)
        assert rejected.returncode == 1 and "partial or broken global" in rejected.stderr
        assert "not wired to Hard Eng" in rejected.stderr
        (fake_bin / agent).unlink()
        shutil.rmtree(home)
        home.mkdir()
        install_global(home, release_root, ("codex", agent))
        fake_agents(fake_bin, (agent,))
        assert prepared(repository, home, env, agent=agent)["mode"] == "global"
        if agent == "claude":
            settings_path = home / ".claude/settings.json"
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            settings["outputStyle"] = "plain-english"
            write(settings_path, json.dumps(settings))
            invalid = launcher(repository, home, env, agent=agent, check=False)
            assert invalid.returncode == 1 and "plain-English output style is missing" in invalid.stderr
        (fake_bin / agent).unlink()
    alternate = root / "alternate-homes"
    repository = alternate / "repository"
    home = alternate / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    install_global(home, release_root, AGENTS)
    fake_agents(fake_bin, AGENTS)
    relocated = dict(env)
    for agent, variable in AGENT_HOMES.items():
        destination = home / f"custom-{agent}"
        (home / f".{agent}").rename(destination)
        relocated[variable] = str(destination)
    (home / ".claude.json").rename(home / "custom-claude/.claude.json")
    for agent in AGENTS:
        broken = launcher(repository, home, env, agent=agent, check=False)
        assert broken.returncode == 1 and "partial or broken global" in broken.stderr, agent
        assert prepared(repository, home, relocated, agent=agent)["mode"] == "global", agent
    for agent in AGENTS:
        (fake_bin / agent).unlink()


def assert_private_owner_admission(root: Path, env: dict[str, str]) -> None:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    write(repository / "README.md", "fixture\n")
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    commit_all(repository, ["README.md"])
    write(repository / "AGENTS.md", "# Repository rules\n")
    write(repository / "CLAUDE.md", "@AGENTS.md\n")
    write(repository / "hard-eng.gates.json", json.dumps({"schema_version": 1, "hard_eng": POLICY}) + "\n")
    write(repository / ".gitignore", "/AGENTS.md\n/CLAUDE.md\n/hard-eng.gates.json\n")
    rejected = launcher(repository, home, env, check=False)
    assert rejected.returncode == 1 and "tracked or privately ignored" in rejected.stderr
    (repository / ".gitignore").unlink()
    exclude = git_exclude(repository)
    write(exclude, exclude.read_text(encoding="utf-8") + OWNER_BLOCK)
    before = tracked_digest(repository)
    assert prepared(repository, home, env)["mode"] == "fallback"
    assert tracked_digest(repository) == before
    assert run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout == ""


def assert_rejections(root: Path, env: dict[str, str]) -> None:
    cases = {
        "partial-global": ("partial or broken global", None),
        "generated-file-conflict": ("another owner", "user-owned\n"),
        "missing-policy": ("no hard_eng release policy", None),
        "redirected-release": ("must be sgaabdu4/hard-eng", None),
        "tracked-override": ("tracked repository state", None),
        "oversize-rules": ("Codex reads at most", None),
    }
    for name, (message, override) in cases.items():
        case = root / name
        repository = case / "repository"
        home = case / "home"
        home.mkdir(parents=True)
        init_repository(repository, marked=True, policy=name != "missing-policy")
        if name == "partial-global":
            write(home / ".agents/AGENTS.md", "partial\n")
            write(home / ".agents/scripts/hooks/agent-hook.sh", "#!/bin/bash\n", 0o755)
        elif override is not None:
            write(repository / "AGENTS.override.md", override)
        elif name == "redirected-release":
            marker = json.loads((repository / "hard-eng.gates.json").read_text(encoding="utf-8"))
            marker["hard_eng"]["release_repository"] = "attacker/hard-eng"
            write(repository / "hard-eng.gates.json", json.dumps(marker) + "\n")
        elif name == "tracked-override":
            write(repository / "AGENTS.override.md", "tracked\n")
            commit_all(repository, ["AGENTS.override.md"])
        elif name == "oversize-rules":
            write(repository / "AGENTS.md", "# Big\n" + ("x" * 80 + "\n") * 420)
            commit_all(repository, ["AGENTS.md"])
        failed = launcher(repository, home, env, check=False)
        assert failed.returncode == 1 and message in failed.stderr, (name, failed.stderr)
        assert not (repository / ".agents/hard-eng/current").exists(), name
        if override is not None:
            assert (repository / "AGENTS.override.md").read_text(encoding="utf-8") == override
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
    generic = root / "generic-agent-skills"
    repository = generic / "repository"
    home = generic / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    write(home / ".agents/skills/example/SKILL.md", "# Example\n")
    assert prepared(repository, home, env)["mode"] == "fallback"


def assert_cache_and_uninstall(root: Path, env: dict[str, str]) -> None:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    first = prepared(repository, home, env)
    assert first["last_check"] == "online-verified"
    write(repository / ".agents/hard-eng/user-note.txt", "retain\n")
    write(root / "offline-bin/gh", "#!/bin/sh\nprintf '%s\\n' 'network is unreachable' >&2\nexit 1\n", 0o755)
    offline = {**env, "PATH": os.pathsep.join((str(root / "offline-bin"), env["PATH"]))}
    second = prepared(repository, home, offline)
    assert second["last_check"] == "offline-cache"
    before = tracked_digest(repository)
    exclude = git_exclude(repository)
    write(exclude, exclude.read_text(encoding="utf-8") + "# user update after Hard Eng setup\n")
    launcher(repository, home, env, command="uninstall")
    assert tracked_digest(repository) == before
    assert sorted(path.name for path in (repository / ".agents/hard-eng").iterdir()) == ["user-note.txt"]
    for relative in ("AGENTS.override.md", "CLAUDE.local.md", ".github/instructions", ".claude/settings.local.json"):
        assert not (repository / relative).exists(), relative
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


def assert_heal_and_takeover(root: Path, env: dict[str, str], release_root: Path) -> None:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    assert prepared(repository, home, env)["mode"] == "fallback"
    write(repository / "AGENTS.md", f"# Repository rules\n\n{REPOSITORY_MARKER}\nSECOND_RULE = loaded\n")
    commit_all(repository, ["AGENTS.md"])
    settings_path = repository / ".claude/settings.local.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    settings["hooks"]["PreToolUse"].append({"hooks": [{"command": "echo user-hook", "type": "command"}]})
    settings["permissions"] = {"allow": ["Bash(ls:*)"]}
    write(settings_path, json.dumps(settings, indent=4))
    status = json.loads(launcher(repository, home, env, command="status").stdout)
    assert status["wiring"] == "stale: AGENTS.override.md is out of date", status
    healed = prepared(repository, home, env)
    assert healed["mode"] == "fallback"
    assert "SECOND_RULE = loaded" in (repository / "AGENTS.override.md").read_text(encoding="utf-8")
    assert json.loads(launcher(repository, home, env, command="status").stdout)["wiring"] == "verified"
    kept = json.loads(settings_path.read_text(encoding="utf-8"))
    assert kept["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert any("user-hook" in json.dumps(entry) for entry in kept["hooks"]["PreToolUse"])
    override = repository / "AGENTS.override.md"
    generated = override.read_text(encoding="utf-8")
    write(override, generated + "\nhand edit\n")
    edited = launcher(repository, home, env, check=False)
    assert edited.returncode == 1 and "edited by hand" in edited.stderr
    write(override, generated)
    assert prepared(repository, home, env)["mode"] == "fallback"
    (repository / ".claude/skills/plain-english").unlink()
    status = json.loads(launcher(repository, home, env, command="status").stdout)
    assert status["wiring"] == "stale: .claude/skills/plain-english link is missing", status
    assert prepared(repository, home, env)["wiring"] == "verified"
    assert (repository / ".claude/skills/plain-english").is_symlink()
    install_global(home, release_root)
    before = tracked_digest(repository)
    taken = prepared(repository, home, env)
    assert taken["mode"] == "global" and "stale repository fallback removed" in taken["last_check"], taken
    assert tracked_digest(repository) == before
    for relative in ("AGENTS.override.md", "CLAUDE.local.md", ".github/instructions", ".agents/hard-eng/current"):
        assert not (repository / relative).exists(), relative
    kept = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "outputStyle" not in kept and kept["permissions"] == {"allow": ["Bash(ls:*)"]}
    assert all("agent-hook.sh" not in json.dumps(entry) for entry in kept["hooks"]["PreToolUse"])
    assert not (repository / ".codex/hooks.json").exists()
    assert run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout.split() == [
        "??",
        ".claude/settings.local.json",
    ], run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout
    assert json.loads(launcher(repository, home, env, command="status").stdout)["wiring"] == "verified"


def assert_concurrent_prepare(root: Path, env: dict[str, str]) -> None:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True)
    command = [str(LAUNCHER), "prepare", "--repo", str(repository), "--home", str(home), "--json"]
    processes = [
        subprocess.Popen(command, cwd=repository, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for _ in range(2)
    ]
    results = [process.communicate(timeout=90) + (process.returncode,) for process in processes]
    assert all(result[2] == 0 for result in results), results
    assert all(json.loads(result[0])["version"] == TAG for result in results)


def assert_update(root: Path) -> None:
    assets_root = root / "assets"
    first_assets, first = release_assets(assets_root / "first", "a" * 40)
    _, second = release_assets(assets_root / "second", "b" * 40)
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_gh(fake_bin, [first])
    env = environment(fake_bin, assets_root)
    repository = root / "repository"
    home = root / "home"
    home.mkdir()
    init_repository(repository, marked=True)
    first_tag = str(first["tag_name"])
    second_tag = str(second["tag_name"])
    assert prepared(repository, home, env)["version"] == first_tag
    altered = json.loads(json.dumps(second))
    altered["assets"][0]["digest"] = f"sha256:{'0' * 64}"
    fake_gh(fake_bin, [altered, first])
    retained = prepared(repository, home, env)
    assert retained["version"] == first_tag
    assert retained["newest_allowed_version"] == second_tag
    assert retained["last_check"].startswith("update-failed-using-verified-cache:")
    fake_gh(fake_bin, [second, first])
    updated = prepared(repository, home, env)
    assert updated["version"] == second_tag and updated["wiring"] == "verified"
    releases = repository / ".agents/hard-eng/releases"
    assert (releases / first_tag).is_dir() and (releases / second_tag).is_dir()
    assert (repository / ".agents/hard-eng/current").resolve() == (releases / second_tag).resolve()
    assert first_assets.is_dir()


def assert_unsafe_archive(root: Path) -> None:
    assets, release = release_assets(root / "assets")
    archive_asset, manifest_asset = release["assets"]  # type: ignore[misc]
    archive = assets / str(archive_asset["name"])
    prefix = f"hard-eng-{TAG}"
    with tarfile.open(archive, "w:gz") as bundle:
        info = tarfile.TarInfo(f"{prefix}/../../escaped")
        info.size = 4
        bundle.addfile(info, io.BytesIO(b"bad\n"))
    manifest_path = assets / str(manifest_asset["name"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["archive"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    manifest["archive"]["size"] = archive.stat().st_size
    write(manifest_path, json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
    archive_asset["digest"] = f"sha256:{hashlib.sha256(archive.read_bytes()).hexdigest()}"
    archive_asset["size"] = archive.stat().st_size
    manifest_asset["digest"] = f"sha256:{hashlib.sha256(manifest_path.read_bytes()).hexdigest()}"
    manifest_asset["size"] = manifest_path.stat().st_size
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_gh(fake_bin, [release])
    env = environment(fake_bin, assets)
    repository = root / "repository"
    home = root / "home"
    home.mkdir()
    init_repository(repository, marked=True)
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "unsafe release archive path" in failed.stderr
    assert not (root / "escaped").exists()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-repository-native-") as temporary:
        root = Path(temporary)
        assets, release = release_assets(root / "release")
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_gh(fake_bin, [release])
        fake_agents(fake_bin, ("codex",))
        env = environment(fake_bin, assets)
        assert_matrix(root, env, assets / "payload")
        assert_agents(root / "agents", env, fake_bin, assets / "payload")
        assert_private_owner_admission(root / "private-owners", env)
        assert_rejections(root / "rejections", env)
        assert_cache_and_uninstall(root / "cache", env)
        assert_heal_and_takeover(root / "heal", env, assets / "payload")
        assert_concurrent_prepare(root / "concurrent", env)
        assert_update(root / "update")
        assert_unsafe_archive(root / "unsafe")
    print(
        "repository-native-contract: PASS matrix=4 agents=3 homes rejections owners cache heal takeover update unsafe"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
