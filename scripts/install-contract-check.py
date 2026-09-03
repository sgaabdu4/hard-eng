#!/usr/bin/env python3
"""Isolated contracts for the terminal installer: `install.sh --global|--repo`."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from repository_native_contract_loader import CONTRACT, load_contract

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "install.sh"
AGENTS = ("codex", "claude", "copilot")
LABELS = {"codex": "Codex", "claude": "Claude Code", "copilot": "Copilot CLI"}
OWNER_FILES = ("AGENTS.md", "CLAUDE.md", "hard-eng.gates.json")
FAKE_SETUP = f"""#!/usr/bin/env python3
import importlib.util
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
log = os.environ.get("HARD_ENG_INSTALL_TEST_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(f"{{root}} {{' '.join(sys.argv[1:])}}\\n")
if os.environ.get("HARD_ENG_INSTALL_TEST_FAIL_SETUP") == "1":
    raise SystemExit(9)
spec = importlib.util.spec_from_file_location("contract", {json.dumps(str(CONTRACT))})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.wire_global(Path(os.environ["HOME"]), root, ("codex", "claude", "copilot"))
"""


contract = load_contract()
run = contract.run
write = contract.write
commit_all = contract.commit_all
init_repository = contract.init_repository
release_assets = contract.release_assets
fake_gh = contract.fake_gh
fake_agents = contract.fake_agents
environment = contract.environment
tracked_digest = contract.tracked_digest
tree_digest = contract.tree_digest
assert_fallback_files = contract.assert_fallback_files


def release(root: Path, commit: str) -> tuple[Path, dict[str, object]]:
    source = root / "payload"
    contract.payload(source)
    write(source / "setup.sh", FAKE_SETUP, 0o755)
    return release_assets(root, commit)


def install(
    arguments: list[str], *, cwd: Path, env: dict[str, str], check: bool = True
) -> subprocess.CompletedProcess[str]:
    return run(["bash", str(INSTALL), *arguments], cwd=cwd, environment=env, check=check)


def home_env(base: dict[str, str], home: Path, log: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    return {**base, "HOME": str(home), "HARD_ENG_INSTALL_TEST_LOG": str(log)}


def leftovers(home: Path) -> list[str]:
    return sorted(
        path.name for path in home.iterdir() if path.name.startswith((".hard-eng-install-", ".agents.previous-"))
    )


def global_version(home: Path) -> str:
    return json.loads((home / ".agents/.hard-eng-release.json").read_text(encoding="utf-8"))["version"]


def index_names(repository: Path) -> list[str]:
    return sorted(filter(None, run(["git", "diff", "--cached", "--name-only"], cwd=repository).stdout.split()))


def status_lines(repository: Path) -> list[str]:
    return run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout.splitlines()


def assert_arguments(root: Path, env: dict[str, str]) -> None:
    cwd = root / "arguments"
    cwd.mkdir(parents=True)
    helped = install(["--help"], cwd=cwd, env=env)
    assert "--global" in helped.stdout and "--repo" in helped.stdout and "--ignore" in helped.stdout
    assert "--shared" in helped.stdout
    for arguments, message in (
        ([], "choose --global or --repo"),
        (["--global", "--repo"], "choose one of --global or --repo"),
        (["--global", "--ignore"], "--ignore works only with --repo"),
        (["--global", "--shared"], "--shared works only with --repo"),
        (["--repo", "--ignore", "--shared"], "choose one of --ignore or --shared"),
        (["--bogus"], "unknown option"),
    ):
        failed = install(arguments, cwd=cwd, env=env, check=False)
        assert failed.returncode == 1 and message in failed.stderr, (arguments, failed.stderr)
    assert not (cwd / ".agents").exists()
    npx = shutil.which("npx")
    if npx is not None:
        cache = root / "npm-cache"
        cache.mkdir()
        bootstrapped = run(
            ["npx", "-y", str(ROOT), "--help"], cwd=cwd, environment={**env, "npm_config_cache": str(cache)}
        )
        assert "--global" in bootstrapped.stdout


def assert_repository_fallback(root: Path, env: dict[str, str], tag: str) -> None:
    repository = root / "repository"
    home = root / "home"
    init_repository(repository, marked=True)
    write(repository / "notes.txt", "uncommitted\n")
    before = tracked_digest(repository)
    result = install(["--repo"], cwd=repository, env=home_env(env, home, root / "setup.log"))
    assert f"Hard Eng repository setup: fallback ({tag}) in {repository}" in result.stdout, result.stdout
    for agent in AGENTS:
        assert f"{LABELS[agent]}: ready (fallback)" in result.stdout, result.stdout
    assert "were already tracked" in result.stdout
    assert_fallback_files(repository, "?? notes.txt\n")
    assert tracked_digest(repository) == before
    again = install(["--repo"], cwd=repository, env=home_env(env, home, root / "setup.log"))
    assert "fallback" in again.stdout and status_lines(repository) == ["?? notes.txt"]
    nested = repository / "nested"
    nested.mkdir()
    wrong = install(["--repo"], cwd=nested, env=home_env(env, home, root / "setup.log"), check=False)
    assert wrong.returncode == 1 and "run this from the repository root" in wrong.stderr
    plain = root / "plain"
    plain.mkdir()
    missing = install(["--repo"], cwd=plain, env=home_env(env, home, root / "setup.log"), check=False)
    assert missing.returncode == 1 and "not inside a Git repository" in missing.stderr
    assert not tuple(plain.iterdir())


def assert_repository_fresh(root: Path, env: dict[str, str]) -> None:
    for private in (False, True):
        case = root / ("ignored" if private else "staged")
        repository = case / "repository"
        repository.mkdir(parents=True)
        write(repository / "README.md", "fixture\n")
        run(["git", "init", "-q", "-b", "main"], cwd=repository)
        commit_all(repository, ["README.md"])
        arguments = ["--repo", "--ignore"] if private else ["--repo"]
        result = install(arguments, cwd=repository, env=home_env(env, case / "home", case / "setup.log"))
        assert "Hard Eng repository setup: fallback" in result.stdout, result.stdout
        for name in OWNER_FILES:
            assert (repository / name).is_file(), name
        marker = json.loads((repository / "hard-eng.gates.json").read_text(encoding="utf-8"))
        assert marker["hard_eng"]["release_repository"] == "sgaabdu4/hard-eng"
        assert (repository / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
        assert (repository / ".agents/hard-eng/current").is_symlink()
        override = (repository / "AGENTS.override.md").read_text(encoding="utf-8")
        assert override.index("# Repository Rules") < override.index(contract.HARD_ENG_MARKER)
        for generated in ("CLAUDE.local.md", ".github/instructions/hard-eng.instructions.md", ".codex/hooks.json"):
            assert (repository / generated).is_file(), generated
        if private:
            assert "Kept AGENTS.md, CLAUDE.md, hard-eng.gates.json private" in result.stdout, result.stdout
            assert index_names(repository) == [] and status_lines(repository) == []
        else:
            assert "Staged AGENTS.md, CLAUDE.md, hard-eng.gates.json" in result.stdout, result.stdout
            assert index_names(repository) == sorted(OWNER_FILES)
            assert status_lines(repository) == [f"A  {name}" for name in sorted(OWNER_FILES)]
    existing = root / "existing-rules"
    repository = existing / "repository"
    repository.mkdir(parents=True)
    write(repository / "AGENTS.md", "# Existing rules\n")
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    commit_all(repository, ["AGENTS.md"])
    install(["--repo"], cwd=repository, env=home_env(env, existing / "home", existing / "setup.log"))
    assert (repository / "AGENTS.md").read_text(encoding="utf-8") == "# Existing rules\n"
    assert index_names(repository) == ["CLAUDE.md", "hard-eng.gates.json"]


def assert_repository_rollback(root: Path, env: dict[str, str]) -> None:
    marked = root / "marked"
    repository = marked / "repository"
    init_repository(repository, marked=True)
    write(repository / "AGENTS.override.md", "tracked\n")
    commit_all(repository, ["AGENTS.override.md"])
    write(repository / "scratch.txt", "keep\n")
    before = tree_digest(repository)
    index = index_names(repository)
    failed = install(["--repo"], cwd=repository, env=home_env(env, marked / "home", marked / "setup.log"), check=False)
    assert failed.returncode == 1 and "tracked repository state" in failed.stderr, failed.stderr
    assert tree_digest(repository) == before and index_names(repository) == index
    fresh = root / "fresh"
    repository = fresh / "repository"
    repository.mkdir(parents=True)
    write(repository / "AGENTS.override.md", "tracked\n")
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    commit_all(repository, ["AGENTS.override.md"])
    before = tree_digest(repository)
    exclude = run(["git", "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"], cwd=repository).stdout
    exclude_path = Path(exclude.strip())
    exclude_before = exclude_path.read_bytes() if exclude_path.is_file() else None
    failed = install(["--repo"], cwd=repository, env=home_env(env, fresh / "home", fresh / "setup.log"), check=False)
    assert failed.returncode == 1, failed.stdout
    assert tree_digest(repository) == before and index_names(repository) == [] and status_lines(repository) == []
    assert (exclude_path.read_bytes() if exclude_path.is_file() else None) == exclude_before


def assert_repository_concurrency(root: Path, env: dict[str, str]) -> None:
    repository = root / "repository"
    init_repository(repository, marked=True)
    value = home_env(env, root / "home", root / "setup.log")
    processes = [
        subprocess.Popen(
            ["bash", str(INSTALL), "--repo"],
            cwd=repository,
            env=value,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [process.communicate(timeout=120) + (process.returncode,) for process in processes]
    assert all(result[2] == 0 for result in results), results
    assert_fallback_files(repository)


def assert_global_install(root: Path, env: dict[str, str], tag: str, fake_bin: Path) -> None:
    home = root / "home"
    log = root / "setup.log"
    value = home_env(env, home, log)
    result = install(["--global"], cwd=root, env=value)
    assert f"Hard Eng global setup: installed {tag} at {home / '.agents'}" in result.stdout, result.stdout
    for agent in AGENTS:
        assert f"{LABELS[agent]}: ready" in result.stdout, result.stdout
    assert global_version(home) == tag
    assert (home / ".local/bin/hard-eng").resolve() == (home / ".agents/bin/hard-eng").resolve()
    assert log.read_text(encoding="utf-8") == f"{home / '.agents'} install\n"
    assert leftovers(home) == []
    again = install(["--global"], cwd=root, env=value)
    assert f"Hard Eng global setup: repaired {tag} at {home / '.agents'}" in again.stdout, again.stdout
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2 and leftovers(home) == []
    repository = root / "repository"
    init_repository(repository, marked=True)
    prepared = install(["--repo"], cwd=repository, env=value)
    assert "Hard Eng repository setup: global" in prepared.stdout and "Codex: ready (global)" in prepared.stdout
    assert not (repository / ".agents").exists() and status_lines(repository) == []
    skipped_home = root / "skipped-home"
    for agent in AGENTS:
        (fake_bin / agent).unlink()
    try:
        skipped = install(["--global"], cwd=root, env=home_env(env, skipped_home, root / "skipped.log"))
        for agent in AGENTS:
            assert f"{LABELS[agent]}: skipped (the {agent} command is not installed)" in skipped.stdout, skipped.stdout
        assert global_version(skipped_home) == tag
    finally:
        fake_agents(fake_bin, AGENTS)
    foreign = root / "foreign-home"
    write(foreign / ".agents/notes.txt", "mine\n")
    rejected = install(["--global"], cwd=root, env=home_env(env, foreign, root / "foreign.log"), check=False)
    assert rejected.returncode == 1 and "not a Hard Eng install" in rejected.stderr
    assert (foreign / ".agents/notes.txt").read_text(encoding="utf-8") == "mine\n" and leftovers(foreign) == []


def assert_global_concurrency(root: Path, env: dict[str, str], tag: str) -> None:
    home = root / "home"
    log = root / "setup.log"
    value = home_env(env, home, log)
    processes = [
        subprocess.Popen(
            ["bash", str(INSTALL), "--global"],
            cwd=root,
            env=value,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    results = [process.communicate(timeout=180) + (process.returncode,) for process in processes]
    assert all(result[2] == 0 for result in results), results
    outputs = "".join(result[0] for result in results)
    assert outputs.count(f"installed {tag}") == 1 and outputs.count(f"repaired {tag}") == 1, outputs
    assert global_version(home) == tag and leftovers(home) == []


def assert_global_rejections(root: Path, env: dict[str, str]) -> None:
    for name, variable in (("verify", "HARD_ENG_TEST_FAIL_VERIFY"), ("tamper", "HARD_ENG_TEST_TAMPER")):
        home = root / f"{name}-home"
        value = {**home_env(env, home, root / f"{name}.log"), variable: "1"}
        failed = install(["--global"], cwd=root, env=value, check=False)
        assert failed.returncode == 1, (name, failed.stdout)
        assert not (home / ".agents").exists() and leftovers(home) == [], name
        assert not (root / f"{name}.log").exists(), name


def assert_global_update(root: Path) -> None:
    assets_root = root / "assets"
    first_assets, first = release(assets_root / "first", "a" * 40)
    _, second = release(assets_root / "second", "b" * 40)
    _, third = release(assets_root / "third", "c" * 40)
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_gh(fake_bin, [first])
    fake_agents(fake_bin, AGENTS)
    env = environment(fake_bin, assets_root)
    home = root / "home"
    log = root / "setup.log"
    value = home_env(env, home, log)
    first_tag = str(first["tag_name"])
    second_tag = str(second["tag_name"])
    install(["--global"], cwd=root, env=value)
    assert global_version(home) == first_tag
    write(home / ".agents/user-note.txt", "mine\n")
    fake_gh(fake_bin, [second, first])
    updated = install(["--global"], cwd=root, env=value)
    assert f"updated {first_tag} to {second_tag}" in updated.stdout, updated.stdout
    assert global_version(home) == second_tag and leftovers(home) == []
    assert not (home / ".agents/user-note.txt").exists()
    assert (home / ".codex/AGENTS.md").resolve() == (home / ".agents/AGENTS.md").resolve()
    fake_gh(fake_bin, [third, second, first])
    before = tree_digest(home / ".agents")
    failed = install(["--global"], cwd=root, env={**value, "HARD_ENG_INSTALL_TEST_FAIL_SETUP": "1"}, check=False)
    assert failed.returncode == 1 and "install failed with exit code 9" in failed.stderr, failed.stderr
    assert global_version(home) == second_tag and tree_digest(home / ".agents") == before and leftovers(home) == []
    offline_bin = root / "offline-bin"
    offline_bin.mkdir()
    write(offline_bin / "gh", "#!/bin/sh\nprintf '%s\\n' 'network is unreachable' >&2\nexit 1\n", 0o755)
    offline = {**value, "PATH": os.pathsep.join((str(offline_bin), value["PATH"]))}
    repaired = install(["--global"], cwd=root, env=offline)
    assert "WARNING: update check failed" in repaired.stdout and f"repaired {second_tag}" in repaired.stdout
    assert global_version(home) == second_tag
    empty_home = root / "offline-home"
    missing = install(["--global"], cwd=root, env=home_env(offline, empty_home, root / "offline.log"), check=False)
    assert missing.returncode == 1 and "could not read the Hard Eng releases" in missing.stderr
    assert not (empty_home / ".agents").exists()
    assert first_assets.is_dir()


def assert_global_checkout(root: Path, env: dict[str, str], payload: Path) -> None:
    home = root / "home"
    checkout = home / ".agents"
    shutil.copytree(payload, checkout)
    run(["git", "init", "-q", "-b", "main"], cwd=checkout)
    log = root / "setup.log"
    value = home_env(env, home, log)
    result = install(["--global"], cwd=root, env=value)
    assert "repaired the development checkout" in result.stdout, result.stdout
    assert log.read_text(encoding="utf-8") == f"{checkout} install\n"
    assert not (checkout / ".hard-eng-release.json").exists() and leftovers(home) == []


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-install-") as temporary:
        root = Path(temporary).resolve()
        assets, current = release(root / "release", "a" * 40)
        tag = str(current["tag_name"])
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_gh(fake_bin, [current])
        fake_agents(fake_bin, AGENTS)
        env = environment(fake_bin, assets)
        assert_arguments(root / "arguments", env)
        assert_repository_fallback(root / "fallback", env, tag)
        assert_repository_fresh(root / "fresh", env)
        assert_repository_rollback(root / "rollback", env)
        assert_repository_concurrency(root / "repository-concurrency", env)
        assert_global_install(root / "global", env, tag, fake_bin)
        assert_global_concurrency(root / "global-concurrency", env, tag)
        assert_global_rejections(root / "global-rejections", env)
        assert_global_update(root / "update")
        assert_global_checkout(root / "checkout", env, assets / "payload")
    digest = hashlib.sha256(INSTALL.read_bytes()).hexdigest()[:12]
    print(
        f"install-contract: PASS install.sh={digest} arguments=PASS repository=fallback+fresh+ignore+rollback+concurrency "
        "global=install+repair+skipped+foreign+concurrency+verify+tamper+update+setup-rollback+offline+checkout"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
