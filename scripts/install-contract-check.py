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
SOURCE_EXCLUDES = (".git", "node_modules", ".venv-mutation", "mutants", ".a", "features", "__pycache__")
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
fake_agents = contract.fake_agents
environment = contract.environment
tracked_digest = contract.tracked_digest
tree_digest = contract.tree_digest
install_global = contract.install_global


def payload_with_setup(root: Path) -> Path:
    contract.payload(root)
    write(root / "setup.sh", FAKE_SETUP, 0o755)
    return root


def global_source(root: Path) -> Path:
    payload_with_setup(root)
    run(["git", "init", "-q", "-b", "main"], cwd=root)
    commit_all(root, ["-A"])
    return root


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


def global_commit(home: Path) -> str:
    return run(["git", "-C", str(home / ".agents"), "rev-parse", "HEAD"], cwd=home).stdout.strip()


def index_names(repository: Path) -> list[str]:
    return sorted(filter(None, run(["git", "diff", "--cached", "--name-only"], cwd=repository).stdout.split()))


def status_lines(repository: Path) -> list[str]:
    return run(["git", "status", "--short", "--untracked-files=all"], cwd=repository).stdout.splitlines()


def assert_arguments(root: Path, env: dict[str, str]) -> None:
    cwd = root / "arguments"
    cwd.mkdir(parents=True)
    helped = install(["--help"], cwd=cwd, env=env)
    assert "--global" in helped.stdout and "--repo" in helped.stdout
    assert "--ignore" not in helped.stdout and "--shared" not in helped.stdout
    for arguments, message in (
        ([], "choose --global or --repo"),
        (["--global", "--repo"], "choose one of --global or --repo"),
        (["--repo", "--ignore"], "unknown option: --ignore"),
        (["--repo", "--shared"], "unknown option: --shared"),
        (["--bogus"], "unknown option: --bogus"),
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


def source_repository(root: Path) -> str:
    root.mkdir(parents=True)
    excludes = tuple(f"--exclude={name}" for name in SOURCE_EXCLUDES)
    run(["rsync", "-a", *excludes, f"{ROOT}/", f"{root}/"], cwd=root)
    run(["git", "init", "-q", "-b", "main"], cwd=root)
    commit_all(root, ["-A"])
    return run(["git", "rev-parse", "HEAD"], cwd=root).stdout.strip()


def shared_environment(home: Path, url: str, fake_bin: Path) -> dict[str, str]:
    home.mkdir(parents=True, exist_ok=True)
    value = {name: item for name, item in os.environ.items() if not name.startswith("GIT_")}
    value["HOME"] = str(home)
    value["HARD_ENG_SOURCE_URL"] = url
    value["GIT_CONFIG_GLOBAL"] = "/dev/null"
    value["GIT_CONFIG_NOSYSTEM"] = "1"
    value["PYTHONDONTWRITEBYTECODE"] = "1"
    value["PATH"] = os.pathsep.join((str(fake_bin), value["PATH"]))
    return value


def assert_repository_shared(root: Path, source: Path, commit: str, fake_bin: Path) -> None:
    url = f"file://{source}"
    all_names = sorted({*OWNER_FILES, *SHARED_FILES})
    repository = root / "repository"
    repository.mkdir(parents=True)
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    env = shared_environment(root / "home", url, fake_bin)
    result = install(["--repo"], cwd=repository, env=env)
    assert f"Hard Eng repository setup: shared ({commit}) in {repository}" in result.stdout, result.stdout
    for agent in AGENTS:
        assert f"{LABELS[agent]}: ready (shared)" in result.stdout, result.stdout
    staged = f"Staged hard-eng.gates.json, {', '.join(SHARED_FILES)}; commit them so every clone fetches the newest Hard Eng."
    assert staged in result.stdout, result.stdout
    for name in (*OWNER_FILES, *SHARED_FILES):
        assert (repository / name).is_file(), name
    marker = json.loads((repository / "hard-eng.gates.json").read_text(encoding="utf-8"))
    assert marker["hard_eng"] == {"schema_version": 1, "wiring": "shared"}, marker
    assert (repository / "CLAUDE.md").read_text(encoding="utf-8") == "@AGENTS.md\n"
    link = repository / ".agents/hard-eng/current"
    assert link.is_symlink() and os.readlink(link) == f"checkouts/{commit}", os.readlink(link)
    assert index_names(repository) == all_names
    assert status_lines(repository) == [f"A  {name}" for name in all_names]
    again = install(["--repo"], cwd=repository, env=env)
    assert f"Hard Eng repository setup: shared ({commit}) in {repository}" in again.stdout, again.stdout
    assert index_names(repository) == all_names
    nested = repository / "nested"
    nested.mkdir()
    wrong = install(["--repo"], cwd=nested, env=shared_environment(root / "nested-home", url, fake_bin), check=False)
    assert wrong.returncode == 1 and "run this from the repository root" in wrong.stderr, wrong.stderr
    plain = root / "plain"
    plain.mkdir()
    missing = install(["--repo"], cwd=plain, env=shared_environment(root / "plain-home", url, fake_bin), check=False)
    assert missing.returncode == 1 and "not inside a Git repository" in missing.stderr, missing.stderr
    assert not tuple(plain.iterdir())


def assert_repository_existing_marker(root: Path, source: Path, commit: str, fake_bin: Path) -> None:
    repository = root / "repository"
    init_repository(repository, marked=True, policy=False)
    rules = (repository / "AGENTS.md").read_text(encoding="utf-8")
    env = shared_environment(root / "home", f"file://{source}", fake_bin)
    result = install(["--repo"], cwd=repository, env=env)
    assert f"Hard Eng repository setup: shared ({commit}) in {repository}" in result.stdout, result.stdout
    marker = json.loads((repository / "hard-eng.gates.json").read_text(encoding="utf-8"))
    assert marker == {"schema_version": 1, "hard_eng": {"schema_version": 1, "wiring": "shared"}}, marker
    assert (repository / "AGENTS.md").read_text(encoding="utf-8") == rules
    assert index_names(repository) == sorted({"hard-eng.gates.json", *SHARED_FILES})


def assert_repository_rollback(root: Path, fake_bin: Path) -> None:
    url = f"file://{root / 'missing-source'}"
    fresh = root / "fresh"
    repository = fresh / "repository"
    repository.mkdir(parents=True)
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    env = shared_environment(fresh / "home", url, fake_bin)
    failed = install(["--repo"], cwd=repository, env=env, check=False)
    assert failed.returncode == 1 and "could not reach" in failed.stderr, failed.stderr
    assert sorted(path.name for path in repository.iterdir()) == [".git"]
    assert status_lines(repository) == []

    marked = root / "marked"
    repository = marked / "repository"
    init_repository(repository, marked=True, policy=False)
    before = tree_digest(repository)
    index = index_names(repository)
    env = shared_environment(marked / "home", url, fake_bin)
    failed = install(["--repo"], cwd=repository, env=env, check=False)
    assert failed.returncode == 1 and "could not reach" in failed.stderr, failed.stderr
    assert tree_digest(repository) == before and index_names(repository) == index
    assert not (repository / ".agents").exists()


def assert_repository_global_present(root: Path, source: Path, commit: str, fake_bin: Path, payload: Path) -> None:
    home = root / "home"
    install_global(home, payload, AGENTS)
    repository = root / "repository"
    repository.mkdir(parents=True)
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    env = shared_environment(home, f"file://{source}", fake_bin)
    result = install(["--repo"], cwd=repository, env=env)
    assert f"Hard Eng repository setup: shared ({commit}) in {repository}" in result.stdout, result.stdout
    guard = (repository / ".agents/hard-eng/global-guard").read_text(encoding="utf-8").split()
    assert sorted(guard) == sorted(AGENTS), guard


def assert_repository_concurrency(root: Path, source: Path, fake_bin: Path) -> None:
    repository = root / "repository"
    repository.mkdir(parents=True)
    run(["git", "init", "-q", "-b", "main"], cwd=repository)
    env = shared_environment(root / "home", f"file://{source}", fake_bin)
    processes = [
        subprocess.Popen(
            ["bash", str(INSTALL), "--repo"],
            cwd=repository,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(3)
    ]
    results = [process.communicate(timeout=180) + (process.returncode,) for process in processes]
    assert all(result[2] == 0 for result in results), results
    for name in (*OWNER_FILES, *SHARED_FILES):
        assert (repository / name).is_file(), name
    assert (repository / ".agents/hard-eng/current").is_symlink()


def assert_global_install(root: Path, env: dict[str, str], fake_bin: Path, source: Path) -> None:
    home = root / "home"
    log = root / "setup.log"
    value = {**home_env(env, home, log), "HARD_ENG_SOURCE_URL": f"file://{source}"}
    result = install(["--global"], cwd=root, env=value)
    commit = global_commit(home)[:12]
    assert f"Hard Eng global setup: installed {commit} at {home / '.agents'}" in result.stdout, result.stdout
    for agent in AGENTS:
        assert f"{LABELS[agent]}: ready" in result.stdout, result.stdout
    assert (home / ".local/bin/hard-eng").resolve() == (home / ".agents/bin/hard-eng").resolve()
    assert log.read_text(encoding="utf-8") == f"{home / '.agents'} install\n"
    assert leftovers(home) == []
    again = install(["--global"], cwd=root, env=value)
    assert f"Hard Eng global setup: repaired {commit} at {home / '.agents'}" in again.stdout, again.stdout
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2 and leftovers(home) == []
    repository = root / "repository"
    init_repository(repository, marked=True)
    prepared = install(["--repo"], cwd=repository, env=value)
    assert "Hard Eng repository setup: shared (" in prepared.stdout and "Codex: ready (shared)" in prepared.stdout
    assert "codex" in (repository / ".agents/hard-eng/global-guard").read_text(encoding="utf-8").split()
    assert ".hard-eng/bootstrap.sh" in index_names(repository)
    skipped_home = root / "skipped-home"
    for agent in AGENTS:
        (fake_bin / agent).unlink()
    try:
        skipped_env = {**home_env(env, skipped_home, root / "skipped.log"), "HARD_ENG_SOURCE_URL": f"file://{source}"}
        skipped = install(["--global"], cwd=root, env=skipped_env)
        for agent in AGENTS:
            assert f"{LABELS[agent]}: skipped (the {agent} command is not installed)" in skipped.stdout, skipped.stdout
        assert global_commit(skipped_home)[:12] == commit
    finally:
        fake_agents(fake_bin, AGENTS)
    foreign = root / "foreign-home"
    write(foreign / ".agents/notes.txt", "mine\n")
    foreign_env = {**home_env(env, foreign, root / "foreign.log"), "HARD_ENG_SOURCE_URL": f"file://{source}"}
    rejected = install(["--global"], cwd=root, env=foreign_env, check=False)
    assert rejected.returncode == 1 and "not a Hard Eng install" in rejected.stderr
    assert (foreign / ".agents/notes.txt").read_text(encoding="utf-8") == "mine\n" and leftovers(foreign) == []


def assert_global_concurrency(root: Path, env: dict[str, str], source: Path) -> None:
    home = root / "home"
    log = root / "setup.log"
    value = {**home_env(env, home, log), "HARD_ENG_SOURCE_URL": f"file://{source}"}
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
    commit = global_commit(home)[:12]
    outputs = "".join(result[0] for result in results)
    assert outputs.count(f"installed {commit}") == 1 and outputs.count(f"repaired {commit}") == 1, outputs
    assert leftovers(home) == []


def assert_global_replaces_release(root: Path, env: dict[str, str], source: Path, payload: Path) -> None:
    home = root / "home"
    checkout = home / ".agents"
    shutil.copytree(payload, checkout)
    write(checkout / ".hard-eng-release.json", "{}\n")
    log = root / "setup.log"
    value = {**home_env(env, home, log), "HARD_ENG_SOURCE_URL": f"file://{source}"}
    result = install(["--global"], cwd=root, env=value)
    commit = global_commit(home)[:12]
    assert f"Hard Eng global setup: replaced the old release install with {commit} at {checkout}" in result.stdout, (
        result.stdout
    )
    assert (checkout / ".git").exists()
    assert not (checkout / ".hard-eng-release.json").exists()
    assert leftovers(home) == []
    kept = root / "kept-home"
    old = kept / ".agents"
    shutil.copytree(payload, old)
    write(old / ".hard-eng-release.json", "{}\n")
    before = tree_digest(old)
    failed_env = {**home_env(value, kept, root / "kept.log"), "HARD_ENG_INSTALL_TEST_FAIL_SETUP": "1"}
    failed = install(["--global"], cwd=root, env=failed_env, check=False)
    assert failed.returncode == 1 and "install failed with exit code 9" in failed.stderr, failed.stderr
    assert tree_digest(old) == before and not (old / ".git").exists() and leftovers(kept) == []


def assert_global_update(root: Path) -> None:
    source = global_source(root / "source")
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_agents(fake_bin, AGENTS)
    env = environment(fake_bin, root)
    home = root / "home"
    log = root / "setup.log"
    value = {**home_env(env, home, log), "HARD_ENG_SOURCE_URL": f"file://{source}"}
    install(["--global"], cwd=root, env=value)
    commit_a = global_commit(home)
    write(source / "second.txt", "second\n")
    commit_all(source, ["second.txt"])
    commit_b = run(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
    write(home / ".agents/user-note.txt", "mine\n")
    updated = install(["--global"], cwd=root, env=value)
    assert f"updated {commit_a[:12]} to {commit_b[:12]}" in updated.stdout, updated.stdout
    assert global_commit(home) == commit_b and leftovers(home) == []
    assert (home / ".agents/user-note.txt").read_text(encoding="utf-8") == "mine\n"
    (home / ".agents/user-note.txt").unlink()
    assert status_lines(home / ".agents") == []
    tracked = home / ".agents/AGENTS.md"
    original = tracked.read_text(encoding="utf-8")
    write(tracked, original + "dirty\n")
    dirtied = install(["--global"], cwd=root, env=value)
    assert "repaired the development checkout" in dirtied.stdout, dirtied.stdout
    assert global_commit(home) == commit_b
    run(["git", "checkout", "--", "AGENTS.md"], cwd=home / ".agents")
    assert tracked.read_text(encoding="utf-8") == original
    assert status_lines(home / ".agents") == []
    offline = {**value, "HARD_ENG_SOURCE_URL": f"file://{root / 'missing-source'}"}
    repaired = install(["--global"], cwd=root, env=offline)
    assert "WARNING: update failed" in repaired.stdout and f"repaired {commit_b[:12]}" in repaired.stdout, (
        repaired.stdout
    )
    assert global_commit(home) == commit_b
    empty_home = root / "offline-home"
    missing = install(["--global"], cwd=root, env=home_env(offline, empty_home, root / "offline.log"), check=False)
    assert missing.returncode == 1 and "could not clone" in missing.stderr, missing.stderr
    assert not (empty_home / ".agents").exists() and leftovers(empty_home) == []
    fail_home = root / "fail-home"
    fail_env = {**home_env(value, fail_home, root / "fail.log"), "HARD_ENG_INSTALL_TEST_FAIL_SETUP": "1"}
    failed = install(["--global"], cwd=root, env=fail_env, check=False)
    assert failed.returncode == 1 and "install failed with exit code 9" in failed.stderr, failed.stderr
    assert not (fail_home / ".agents").exists() and leftovers(fail_home) == []


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
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        fake_agents(fake_bin, AGENTS)
        env = environment(fake_bin, root)
        assert_arguments(root / "arguments", env)
        source = root / "source"
        commit = source_repository(source)
        repository_bin = root / "repository-bin"
        repository_bin.mkdir()
        fake_agents(repository_bin, AGENTS)
        payload = payload_with_setup(root / "payload")
        assert_repository_shared(root / "shared", source, commit, repository_bin)
        assert_repository_existing_marker(root / "existing-marker", source, commit, repository_bin)
        assert_repository_rollback(root / "rollback", repository_bin)
        assert_repository_global_present(root / "global-present", source, commit, repository_bin, payload)
        assert_repository_concurrency(root / "repository-concurrency", source, repository_bin)
        install_source = global_source(root / "global-source")
        assert_global_install(root / "global", env, fake_bin, install_source)
        assert_global_concurrency(root / "global-concurrency", env, install_source)
        assert_global_replaces_release(root / "release-upgrade", env, install_source, payload)
        assert_global_update(root / "update")
        assert_global_checkout(root / "checkout", env, payload)
    digest = hashlib.sha256(INSTALL.read_bytes()).hexdigest()[:12]
    print(
        f"install-contract: PASS install.sh={digest} arguments=PASS "
        "repository=shared+existing-marker+rollback+global-present+concurrency "
        "global=install+repair+skipped+foreign+concurrency+release-upgrade+update+checkout"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
