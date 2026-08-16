#!/usr/bin/env python3
"""Behavior checks for lifecycle-safe managed-skill updates."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
sys.path.insert(0, str(SCRIPTS))

from bounded_run import CapturedRunResult, run_captured  # noqa: E402
from git_env import git_env  # noqa: E402


HELPER = ROOT / "scripts/managed-skill-update-state.py"
UPDATER = ROOT / "scripts/update-managed-skills.sh"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"managed-skill-update-regressions: {message}")


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> CapturedRunResult:
    return run_captured(command, timeout=30, grace=1, cwd=str(cwd), env=env)


def require_ok(result: CapturedRunResult, action: str) -> bytes:
    if result.returncode:
        fail(f"{action} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout.strip()


def git(repo: Path, *args: str) -> None:
    home = repo.parent / "git-home"
    home.mkdir(exist_ok=True)
    environment = git_env(ceiling=repo.parent)
    environment["HOME"] = str(home)
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    result = run(
        [
            "git",
            "--no-optional-locks",
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            *args,
        ],
        cwd=repo,
        env=environment,
    )
    require_ok(result, f"git {' '.join(args)}")


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def fixture(parent: Path, name: str) -> Path:
    repo = parent / name
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Hard Eng Regression")
    git(repo, "config", "user.email", "hard-eng@example.invalid")
    write(repo / ".skill-lock.json", '{"skills":{"managed":{"source":"example/managed"}}}\n')
    write(repo / "skills/managed/value.txt", "old\n")
    write(repo / "skills/local/value.txt", "local\n")
    git(repo, "add", ".skill-lock.json", "skills")
    git(repo, "commit", "-qm", "fixture")
    write(repo / "features/active-plan/PLAN.md", "building\n")
    write(repo / "features/active-plan/receipts/S-1.json", "{}\n")
    write(repo / "features/terminal-plan/PLAN.md", "green\n")
    write(repo / "features/terminal-plan/receipts/full.json", "{}\n")
    write(
        repo / ".git/info/exclude",
        "features/terminal-plan/PLAN.md\n"
        "features/terminal-plan/receipts/full.json\n",
    )
    return repo


def check_host_git_config_isolation(parent: Path) -> None:
    hooks = parent / "host-hooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    write(hook, "#!/bin/sh\nexit 97\n")
    hook.chmod(0o755)
    host_config = parent / "host-gitconfig"
    write(
        host_config,
        f"[core]\n\thooksPath = {hooks.as_posix()}\n"
        "[maintenance]\n\tauto = true\n"
        "[gc]\n\tauto = 1\n\tautoDetach = true\n",
    )
    previous_global = os.environ.get("GIT_CONFIG_GLOBAL")
    os.environ["GIT_CONFIG_GLOBAL"] = str(host_config)
    try:
        probe = parent / "unhermetic-host-config"
        probe.mkdir()
        environment = git_env(ceiling=parent)
        require_ok(run(["git", "init", "-q"], cwd=probe, env=environment), "host config probe init")
        rejected = run(
            [
                "git",
                "-c",
                "user.name=Hard Eng Regression",
                "-c",
                "user.email=hard-eng@example.invalid",
                "commit",
                "--allow-empty",
                "-qm",
                "host config probe",
            ],
            cwd=probe,
            env=environment,
        )
        if rejected.returncode == 0:
            fail("host Git config did not reject the unhermetic commit probe")
        fixture(parent, "host-config-isolation")
    finally:
        if previous_global is None:
            os.environ.pop("GIT_CONFIG_GLOBAL", None)
        else:
            os.environ["GIT_CONFIG_GLOBAL"] = previous_global


def helper(repo: Path, command: str) -> CapturedRunResult:
    return run([sys.executable, str(HELPER), command, "--repo", str(repo)], cwd=repo)


def check_snapshot_boundaries(parent: Path) -> None:
    repo = fixture(parent, "snapshot")
    before = require_ok(helper(repo, "snapshot-before"), "initial lifecycle snapshot")
    write(repo / "skills/managed/value.txt", "new\n")
    after = require_ok(helper(repo, "snapshot-after"), "post-update lifecycle snapshot")
    if before != after:
        fail("a managed-only update changed the lifecycle digest")
    state = require_ok(helper(repo, "validate-changes"), "managed change validation")
    if state != b"changed":
        fail("managed changes were not reported")

    plan = repo / "features/active-plan/PLAN.md"
    write(plan, "changed concurrently\n")
    changed = require_ok(helper(repo, "snapshot-after"), "changed lifecycle snapshot")
    if changed == before:
        fail("Feature Brief content changes did not change the lifecycle digest")
    write(plan, "building\n")

    terminal = repo / "features/terminal-plan/PLAN.md"
    write(terminal, "changed terminal state\n")
    changed = require_ok(helper(repo, "snapshot-after"), "changed ignored lifecycle snapshot")
    if changed == before:
        fail("ignored Feature Brief changes did not change the lifecycle digest")
    write(terminal, "green\n")

    write(repo / "outside.txt", "forbidden\n")
    if helper(repo, "validate-changes").returncode == 0:
        fail("an updater-created path outside managed trees was accepted")
    (repo / "outside.txt").unlink()

    write(repo / "skills/local/value.txt", "changed\n")
    if helper(repo, "validate-changes").returncode == 0:
        fail("a local skill change was accepted")
    write(repo / "skills/local/value.txt", "local\n")

    external = parent / "external-plan"
    write(external, "external\n")
    plan.unlink()
    plan.symlink_to(external)
    if helper(repo, "snapshot-after").returncode == 0:
        fail("a symlinked Feature Brief was accepted")


def fake_updater(repo: Path, body: str) -> dict[str, str]:
    scripts = repo / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "update-managed-skills.sh").write_bytes(UPDATER.read_bytes())
    (scripts / "managed-skill-update-state.py").write_bytes(HELPER.read_bytes())
    write(scripts / "check-managed-skills.js", 'console.log("fixture managed skills: PASS");\n')
    fake_bin = repo / "fake-bin"
    fake_bin.mkdir()
    npx = fake_bin / "npx"
    write(npx, f"#!/bin/sh\nset -eu\n{body}\n")
    npx.chmod(0o755)
    home = repo / "home"
    home.mkdir()
    (home / ".agents").symlink_to(repo, target_is_directory=True)
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    environment["PYTHONPATH"] = str(SCRIPTS)
    environment["HARD_ENG_GIT_ENV_CACHE"] = str(repo.parent / f"{repo.name}-git-env.json")
    environment = git_env(environment, ceiling=repo.parent)
    git(repo, "add", "scripts", "fake-bin", "home")
    git(repo, "commit", "-qm", "updater fixture")
    return environment


def check_updater_wiring(parent: Path) -> None:
    repo = fixture(parent, "updater-pass")
    environment = fake_updater(repo, "printf 'new\\n' > skills/managed/value.txt")
    plan_before = (repo / "features/active-plan/PLAN.md").read_bytes()
    result = run(["bash", "scripts/update-managed-skills.sh", "--ci"], cwd=repo, env=environment)
    require_ok(result, "lifecycle-safe managed update")
    if (repo / "features/active-plan/PLAN.md").read_bytes() != plan_before:
        fail("the valid updater changed Feature Brief bytes")

    repo = fixture(parent, "updater-reject")
    environment = fake_updater(
        repo,
        "printf 'new\\n' > skills/managed/value.txt\n"
        "printf 'corrupt\\n' > features/active-plan/PLAN.md",
    )
    result = run(["bash", "scripts/update-managed-skills.sh", "--ci"], cwd=repo, env=environment)
    if result.returncode == 0:
        fail(
            "the updater accepted a concurrent Feature Brief change: "
            f"{result.stdout.decode('utf-8', 'replace').strip()}"
        )
    if b"changed lifecycle state" not in result.stderr:
        fail("the updater did not identify the lifecycle-state violation")

    repo = fixture(parent, "updater-failure")
    environment = fake_updater(
        repo,
        "printf 'corrupt\\n' > features/active-plan/PLAN.md\nexit 9",
    )
    result = run(["bash", "scripts/update-managed-skills.sh", "--ci"], cwd=repo, env=environment)
    if result.returncode == 0 or b"changed lifecycle state" not in result.stderr:
        fail("a failing updater bypassed lifecycle-state validation")


def check_starting_state(parent: Path) -> None:
    repo = fixture(parent, "starting-state")
    write(repo / "unrelated.txt", "user work\n")
    if helper(repo, "snapshot-before").returncode == 0:
        fail("unrelated starting work was accepted")
    (repo / "unrelated.txt").unlink()
    write(repo / "skills/local/value.txt", "user work\n")
    if helper(repo, "snapshot-before").returncode == 0:
        fail("tracked starting work was accepted")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="managed-skill-update-") as temporary:
        parent = Path(temporary)
        check_host_git_config_isolation(parent)
        check_snapshot_boundaries(parent)
        check_updater_wiring(parent)
        check_starting_state(parent)
    print("managed-skill-update-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
