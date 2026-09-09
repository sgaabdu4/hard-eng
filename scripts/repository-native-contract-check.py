#!/usr/bin/env python3
from __future__ import annotations

import atexit
import fcntl
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "bin/hard-eng"
AGENTS = ("codex", "claude", "copilot")
TOOLS = ("bash", "git", "node", "npm", "npx", "perl", "python3", "sh", "rsync")
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
SHARED_POLICY = {"schema_version": 1, "wiring": "shared"}
SOURCE_EXCLUDES = (".git", "node_modules", ".venv-mutation", "mutants", ".a", "features", "__pycache__")


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
            marker["hard_eng"] = dict(SHARED_POLICY)
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


def environment(fake_bin: Path, workspace: Path, *, extra_path: tuple[Path, ...] = ()) -> dict[str, str]:
    value = {
        name: item
        for name, item in os.environ.items()
        if name not in {"CODEX_HOME", "CLAUDE_CONFIG_DIR", "COPILOT_HOME", "XDG_CONFIG_HOME"}
    }
    value["PATH"] = os.pathsep.join(
        (str(fake_bin), *(str(path) for path in extra_path), str(tools_path(workspace)), "/usr/bin", "/bin")
    )
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


def install_global(home: Path, source: Path, agents: tuple[str, ...] = ("codex",)) -> str:
    global_root = home / ".agents"
    shutil.copytree(source, global_root)
    run(["git", "init", "-q", "-b", "main"], cwd=global_root)
    commit_all(global_root, ["-A"])
    wire_global(home, global_root, agents)
    return run(["git", "rev-parse", "HEAD"], cwd=global_root).stdout.strip()


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


def build_source(root: Path) -> tuple[Path, str]:
    source = root / "source"
    source.mkdir()
    excludes = tuple(f"--exclude={name}" for name in SOURCE_EXCLUDES)
    run(["rsync", "-a", *excludes, f"{ROOT}/", f"{source}/"], cwd=root)
    run(["git", "init", "-q", "-b", "main"], cwd=source)
    commit_all(source, ["-A"])
    return source, run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()


def assert_shared_wiring(repository: Path, source: Path, commit: str) -> None:
    current = repository / ".agents/hard-eng/current"
    assert current.is_symlink() and current.resolve().name == commit
    source_agents = (source / "AGENTS.md").read_bytes()
    override = (repository / "AGENTS.override.md").read_bytes()
    assert override.endswith(source_agents) and REPOSITORY_MARKER.encode() in override
    assert override.index(REPOSITORY_MARKER.encode()) < len(override) - len(source_agents)
    assert (repository / "CLAUDE.local.md").read_bytes() == b"@.agents/hard-eng/current/AGENTS.md\n"
    instructions = (repository / ".github/instructions/hard-eng.instructions.md").read_bytes()
    assert instructions.startswith(b'---\napplyTo: "**"\n---\n') and instructions.endswith(source_agents)
    for relative in (".hard-eng/bootstrap.sh", ".hard-eng/hook.sh"):
        target = repository / relative
        assert target.is_file() and os.access(target, os.X_OK), relative
    codex_hooks = json.loads((repository / ".codex/hooks.json").read_text(encoding="utf-8"))
    session = codex_hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    assert "bootstrap.sh" in session and "codex" in session
    pretool = codex_hooks["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "hook.sh" in pretool and "pretooluse" in pretool
    claude_settings = json.loads((repository / ".claude/settings.json").read_text(encoding="utf-8"))
    assert claude_settings["outputStyle"] == "Plain English"
    assert "hook.sh" in claude_settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    copilot_hooks = json.loads((repository / ".github/hooks/hard-eng.json").read_text(encoding="utf-8"))
    assert copilot_hooks["version"] == 1
    assert "bootstrap.sh" in copilot_hooks["hooks"]["sessionStart"][0]["bash"]
    assert "hook.sh" in copilot_hooks["hooks"]["preToolUse"][0]["bash"]
    codex_config = (repository / ".codex/config.toml").read_text(encoding="utf-8")
    assert "project_doc_max_bytes = 65536" in codex_config
    for relative in (
        ".agents/skills/plain-english",
        ".claude/skills/plain-english",
        ".codex/agents/he-learn.toml",
        ".claude/agents/he-learn.md",
        ".github/agents/he-learn.agent.md",
        ".claude/output-styles/plain-english.md",
    ):
        assert (repository / relative).is_symlink(), relative


def assert_matrix(root: Path, env: dict[str, str], global_payload: Path, source: Path, commit: str) -> None:
    cases = (
        ("unmarked", None, False),
        ("unmarked-global", None, True),
        ("marked-no-global", False, False),
        ("marked-global", False, True),
        ("shared-no-global", True, False),
        ("shared-global", True, True),
    )
    for name, marker, global_install in cases:
        case = root / name
        repository = case / 'repository "quoted"'
        home = case / "home"
        home.mkdir(parents=True)
        init_repository(repository, marked=marker is not None, policy=bool(marker))
        global_commit = install_global(home, global_payload) if global_install else None
        before = tracked_digest(repository)
        if marker is False and not global_install:
            failed = launcher(repository, home, env, check=False)
            assert failed.returncode == 1 and "hard-eng install --repo" in failed.stderr, failed.stderr
            status = json.loads(launcher(repository, home, env, command="status").stdout)
            assert status["mode"] == "unprotected", status
            continue
        value = prepared(repository, home, env)
        assert tracked_digest(repository) == before
        expected = "pass-through" if marker is None else "global" if marker is False else "shared"
        assert value["mode"] == expected, (name, value)
        if expected == "shared":
            note = "; the global Hard Eng guard checks tool calls" if global_install else ""
            assert value["identity"] == commit and value["wiring"] == "verified" + note, value
            assert_shared_wiring(repository, source, commit)
        elif expected == "global":
            assert value["identity"] == global_commit and not (repository / ".agents").exists()
        status = json.loads(launcher(repository, home, env, command="status").stdout)
        assert status["mode"] == expected, status


def assert_agents(root: Path, env: dict[str, str], fake_bin: Path, global_payload: Path) -> None:
    for agent in AGENTS:
        case = root / agent
        repository = case / "repository"
        home = case / "home"
        home.mkdir(parents=True)
        init_repository(repository, marked=True, policy=False)
        commit = install_global(home, global_payload, (agent,))
        fake_agents(fake_bin, (agent,))
        try:
            value = prepared(repository, home, env, agent=agent)
            assert value["mode"] == "global" and value["identity"] == commit, (agent, value)
        finally:
            (fake_bin / agent).unlink()
    fake_agents(fake_bin, ("codex",))


def assert_private_owner_admission(root: Path, env: dict[str, str], commit: str) -> None:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    write(repository / "README.md", "fixture\n")
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    commit_all(repository, ["README.md"])
    write(repository / "AGENTS.md", "# Repository rules\n")
    write(repository / "CLAUDE.md", "@AGENTS.md\n")
    write(repository / "hard-eng.gates.json", json.dumps({"schema_version": 1, "hard_eng": dict(SHARED_POLICY)}) + "\n")
    write(repository / ".gitignore", "/AGENTS.md\n/CLAUDE.md\n/hard-eng.gates.json\n")
    rejected = launcher(repository, home, env, check=False)
    assert rejected.returncode == 1 and "tracked or privately ignored" in rejected.stderr, rejected.stderr
    (repository / ".gitignore").unlink()
    exclude = git_exclude(repository)
    write(exclude, exclude.read_text(encoding="utf-8") + OWNER_BLOCK)
    before = tracked_digest(repository)
    value = prepared(repository, home, env)
    assert value["mode"] == "shared" and value["identity"] == commit, value
    assert tracked_digest(repository) == before
    owners = ("AGENTS.md", "CLAUDE.md", "hard-eng.gates.json")
    status = run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout
    assert not any(name in line for line in status.splitlines() for name in owners), status


def assert_rejections(root: Path, env: dict[str, str]) -> None:
    refused = (
        ("channel", "prerelease"),
        ("pin", {"tag": "v1"}),
        ("release_repository", "attacker/hard-eng"),
        ("minimum_version", "0.1.0"),
    )
    for key, value in refused:
        case = root / f"key-{key}"
        repository = case / "repository"
        home = case / "home"
        home.mkdir(parents=True)
        init_repository(repository, marked=True, policy=True)
        marker = json.loads((repository / "hard-eng.gates.json").read_text(encoding="utf-8"))
        marker["hard_eng"][key] = value
        write(repository / "hard-eng.gates.json", json.dumps(marker) + "\n")
        failed = launcher(repository, home, env, check=False)
        assert failed.returncode == 1 and f"unsupported keys: {key}" in failed.stderr, (key, failed.stderr)
        assert not (repository / ".agents/hard-eng/current").exists(), key
    untracked = root / "untracked-marker"
    repository = untracked / "repository"
    home = untracked / "home"
    home.mkdir(parents=True)
    write(repository / "AGENTS.md", f"# Repository rules\n\n{REPOSITORY_MARKER}\n")
    write(repository / "CLAUDE.md", "@AGENTS.md\n")
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    commit_all(repository, ["AGENTS.md", "CLAUDE.md"])
    write(repository / "hard-eng.gates.json", json.dumps({"schema_version": 1, "hard_eng": dict(SHARED_POLICY)}) + "\n")
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "tracked or privately ignored" in failed.stderr, failed.stderr
    symlinked = root / "symlinked-marker"
    repository = symlinked / "repository"
    home = symlinked / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=False)
    outside = symlinked / "outside.json"
    write(outside, json.dumps({"schema_version": 1, "hard_eng": dict(SHARED_POLICY)}) + "\n")
    (repository / "hard-eng.gates.json").symlink_to(outside)
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and "must be a regular file" in failed.stderr, failed.stderr
    bad_claude = root / "bad-claude"
    repository = bad_claude / "repository"
    home = bad_claude / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True, policy=True)
    write(repository / "CLAUDE.md", "not just the import\n")
    commit_all(repository, ["CLAUDE.md"])
    failed = launcher(repository, home, env, agent="claude", check=False)
    assert failed.returncode == 1 and "must contain only @AGENTS.md" in failed.stderr, failed.stderr


def prepared_shared(root: Path, env: dict[str, str], commit: str) -> tuple[Path, Path]:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True, policy=True)
    first = prepared(repository, home, env)
    assert first["identity"] == commit and first["mode"] == "shared"
    return repository, home


def assert_cache_and_uninstall(root: Path, env: dict[str, str], commit: str) -> None:
    repository, home = prepared_shared(root, env, commit)
    offline = {**env, "HARD_ENG_SOURCE_URL": f"file://{root / 'missing-source'}"}
    second = prepared(repository, home, offline)
    assert second["identity"] == commit and second["mode"] == "shared"
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=repository).stdout
    launcher(repository, home, env, command="uninstall")
    assert staged == run(["git", "diff", "--cached", "--name-only"], cwd=repository).stdout == ""
    marker = json.loads((repository / "hard-eng.gates.json").read_text(encoding="utf-8"))
    assert "hard_eng" not in marker, marker
    assert not (repository / ".agents/hard-eng").exists()
    for relative in (
        "AGENTS.override.md",
        "CLAUDE.local.md",
        ".github/instructions/hard-eng.instructions.md",
        ".hard-eng/bootstrap.sh",
        ".hard-eng/hook.sh",
        ".codex/hooks.json",
        ".claude/settings.json",
        ".github/hooks/hard-eng.json",
        ".codex/config.toml",
    ):
        assert not (repository / relative).exists(), relative
    again = launcher(repository, home, env, command="uninstall")
    assert "Hard Eng is not installed in this repository" in again.stdout, again.stdout


def assert_heal_and_takeover(root: Path, env: dict[str, str], commit: str, global_payload: Path) -> None:
    repository = root / "repository"
    home = root / "home"
    home.mkdir(parents=True)
    init_repository(repository, marked=True, policy=True)
    assert prepared(repository, home, env)["mode"] == "shared"
    write(repository / "AGENTS.md", f"# Repository rules\n\n{REPOSITORY_MARKER}\nSECOND_RULE = loaded\n")
    commit_all(repository, ["AGENTS.md"])
    status = json.loads(launcher(repository, home, env, command="status").stdout)
    assert status["wiring"] == "stale: AGENTS.override.md is out of date", status
    healed = prepared(repository, home, env)
    assert healed["mode"] == "shared" and healed["wiring"] == "verified", healed
    assert "SECOND_RULE = loaded" in (repository / "AGENTS.override.md").read_text(encoding="utf-8")
    (repository / ".claude/skills/plain-english").unlink()
    status = json.loads(launcher(repository, home, env, command="status").stdout)
    assert status["wiring"] == "stale: .claude/skills/plain-english link is missing", status
    assert prepared(repository, home, env)["wiring"] == "verified"
    assert (repository / ".claude/skills/plain-english").is_symlink()
    override = repository / "AGENTS.override.md"
    generated = override.read_text(encoding="utf-8")
    write(override, generated + "\nhand edit\n")
    edited = launcher(repository, home, env, check=False)
    assert edited.returncode == 1 and "edited by hand" in edited.stderr, edited.stderr
    write(override, generated)
    assert prepared(repository, home, env)["mode"] == "shared"
    write(repository / "hard-eng.gates.json", json.dumps({"schema_version": 1}) + "\n")
    global_commit = install_global(home, global_payload)
    before = tracked_digest(repository)
    taken = prepared(repository, home, env)
    assert taken["mode"] == "global" and taken["identity"] == global_commit, taken
    assert "stale repository copy removed" in taken["wiring"], taken
    assert tracked_digest(repository) == before
    for relative in (
        "AGENTS.override.md",
        "CLAUDE.local.md",
        ".github/instructions/hard-eng.instructions.md",
        ".agents/hard-eng/current",
        ".hard-eng/bootstrap.sh",
        ".hard-eng/hook.sh",
    ):
        assert not (repository / relative).exists(), relative
    assert json.loads(launcher(repository, home, env, command="status").stdout)["mode"] == "global"


def assert_concurrent_prepare(root: Path, env: dict[str, str], commit: str) -> None:
    repository, home = prepared_shared(root, env, commit)
    command = [str(LAUNCHER), "prepare", "--repo", str(repository), "--home", str(home), "--agent", "codex", "--json"]
    with open(repository / ".agents/hard-eng/.wiring.lock", "a+", encoding="utf-8") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        processes = [
            subprocess.Popen(
                command, cwd=repository, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            for _ in range(2)
        ]
        notices = [process.stderr.readline() if process.stderr else "" for process in processes]
        fcntl.flock(held, fcntl.LOCK_UN)
    results = [process.communicate(timeout=90) + (process.returncode,) for process in processes]
    assert all(result[2] == 0 for result in results), results
    assert all(json.loads(result[0])["identity"] == commit for result in results), results
    assert all("waiting for another Hard Eng wiring update" in notice for notice in notices), notices


def assert_unsafe_path(root: Path, env: dict[str, str]) -> None:
    repository = root / "repository"
    home = root / "home"
    outside = root / "outside"
    home.mkdir(parents=True)
    outside.mkdir()
    init_repository(repository, marked=True, policy=True)
    (repository / ".agents").mkdir()
    (repository / ".agents/hard-eng").symlink_to(outside, target_is_directory=True)
    failed = launcher(repository, home, env, check=False)
    assert failed.returncode == 1 and ".agents/hard-eng" in failed.stderr and "is not a directory" in failed.stderr
    assert not tuple(outside.iterdir())


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-repository-native-") as temporary:
        root = Path(temporary)
        source, commit = build_source(root)
        os.environ["HARD_ENG_SOURCE_URL"] = f"file://{source}"
        global_payload = root / "global-payload"
        payload(global_payload)
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_agents(fake_bin, ("codex",))
        env = environment(fake_bin, root)
        assert_matrix(root / "matrix", env, global_payload, source, commit)
        assert_agents(root / "agents", env, fake_bin, global_payload)
        assert_private_owner_admission(root / "private-owners", env, commit)
        assert_rejections(root / "rejections", env)
        assert_cache_and_uninstall(root / "cache", env, commit)
        assert_heal_and_takeover(root / "heal", env, commit, global_payload)
        assert_concurrent_prepare(root / "concurrent", env, commit)
        assert_unsafe_path(root / "unsafe", env)
    print(
        "repository-native-contract: PASS matrix=6 agents=3 owners rejections=5 cache uninstall heal takeover "
        "concurrent unsafe"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
