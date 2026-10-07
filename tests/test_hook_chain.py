"""A project's own pre-push hook is kept and runs before Hard Eng's."""

import json
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import agent_hooks
import hook_chain
import pytest
from conftest import git
from shipping import ShippingPolicy
from test_basic_mode import go_project

PROJECT_HOOK = '#!/bin/sh\necho "$@" > project.args\ncat > project.stdin\nexit $(cat project.exit)\n'
STUB = (
    "import sys\n"
    "open('stub.args', 'w').write(' '.join(sys.argv[1:]))\n"
    "open('stub.stdin', 'w').write(sys.stdin.read())\n"
    "sys.exit(5)\n"
)


def install_over(
    installer: ModuleType, repository: Path, shipping_policy: ShippingPolicy, hook: str
) -> Path:
    go_project(repository)
    path = repository / ".git/hooks/pre-push"
    path.write_text(hook)
    path.chmod(0o755)
    config = installer.gate_config(repository)
    config["shipping"] = shipping_policy
    (repository / "hard-eng.gates.json").write_text(json.dumps(config))
    installer.install(repository)
    return path


def push(repository: Path, exit_code: int) -> subprocess.CompletedProcess[str]:
    (repository / "project.exit").write_text(f"{exit_code}\n")
    (repository / ".hooks/hard-eng.py").write_text(STUB)
    return subprocess.run(
        [str(repository / ".git/hooks/pre-push"), "origin", "https://example.test/r"],
        cwd=repository,
        input="refs/heads/a 1 refs/heads/a 0\n",
        capture_output=True,
        text=True,
        check=False,
    )


def test_setup_keeps_a_project_pre_push_hook_and_runs_it_first(
    installer: ModuleType,
    repository: Path,
    shipping_policy: ShippingPolicy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hook = install_over(installer, repository, shipping_policy, PROJECT_HOOK)
    assert hook_chain.KEPT in capsys.readouterr().out.splitlines()
    kept = hook_chain.project_copy(hook)
    assert kept.read_text() == PROJECT_HOOK
    assert kept.stat().st_mode & 0o111
    assert hook.read_text() == hook_chain.CHAINED_LAUNCHER
    installer.install(repository)
    assert kept.read_text() == PROJECT_HOOK
    assert hook.read_text() == hook_chain.CHAINED_LAUNCHER
    assert hook_chain.KEPT not in capsys.readouterr().out
    failed = push(repository, 3)
    assert failed.returncode == 3
    assert not (repository / "stub.args").exists()
    assert (
        repository / "project.args"
    ).read_text() == "origin https://example.test/r\n"
    passed = push(repository, 0)
    assert passed.returncode == 5
    assert (repository / "stub.args").read_text() == "pre-push"
    assert (repository / "stub.stdin").read_text() == "refs/heads/a 1 refs/heads/a 0\n"
    assert (
        repository / "project.stdin"
    ).read_text() == "refs/heads/a 1 refs/heads/a 0\n"


def test_setup_chains_a_husky_projects_own_pre_push_script(
    installer: ModuleType,
    repository: Path,
    shipping_policy: ShippingPolicy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    go_project(repository)
    shim = repository / ".husky/_/pre-push"
    shim.parent.mkdir(parents=True)
    shim.write_text('#!/usr/bin/env sh\n. "$(dirname "$0")/h"')
    (shim.parent / "h").write_text(
        'n=$(basename "$0")\ns=$(dirname "$(dirname "$0")")/$n\nsh -e "$s" "$@"\n'
    )
    script = repository / ".husky/pre-push"
    script.write_text(PROJECT_HOOK.removeprefix("#!/bin/sh\n"))
    original = script.read_bytes()
    git(repository, "config", "core.hooksPath", ".husky/_")
    config = installer.gate_config(repository)
    config["shipping"] = shipping_policy
    (repository / "hard-eng.gates.json").write_text(json.dumps(config))
    installer.install(repository)
    assert hook_chain.KEPT in capsys.readouterr().out.splitlines()
    kept = repository / ".husky/pre-push.project"
    assert kept.read_bytes() == original
    assert script.read_text() == hook_chain.HUSKY_CHAINED_LAUNCHER
    installer.install(repository)
    assert kept.read_bytes() == original
    assert script.read_text() == hook_chain.HUSKY_CHAINED_LAUNCHER
    (repository / ".hooks/hard-eng.py").write_text(STUB)
    arguments = ["sh", str(shim), "origin", "https://example.test/r"]
    for code, expected, ran in ((3, 3, False), (0, 5, True)):
        (repository / "project.exit").write_text(f"{code}\n")
        (repository / "stub.args").unlink(missing_ok=True)
        result = subprocess.run(
            arguments,
            cwd=repository,
            input="refs/heads/a 1 refs/heads/a 0\n",
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == expected
        assert (repository / "stub.args").exists() == ran
    assert (
        repository / "project.args"
    ).read_text() == "origin https://example.test/r\n"
    assert (
        repository / "project.stdin"
    ).read_text() == "refs/heads/a 1 refs/heads/a 0\n"
    assert (repository / "stub.stdin").read_text() == "refs/heads/a 1 refs/heads/a 0\n"
    (repository / "stub.args").unlink()
    kept.write_text("false\necho later > later.txt\n")
    result = subprocess.run(
        arguments, cwd=repository, input="", capture_output=True, check=False
    )
    assert result.returncode != 0
    assert not (repository / "later.txt").exists()
    assert not (repository / "stub.args").exists()


def test_session_notes_a_replaced_launcher_and_says_how_to_restore(
    installer: ModuleType,
    repository: Path,
    shipping_policy: ShippingPolicy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = install_over(installer, repository, shipping_policy, PROJECT_HOOK)
    monkeypatch.setattr("update_runner.start_update", Mock(return_value=""))
    assert hook_chain.RESTORE not in agent_hooks.session_context(repository, {})
    hook.write_text("#!/bin/sh\nexec lefthook run pre-push\n")
    message = agent_hooks.session_context(repository, {})
    assert hook_chain.RESTORE in message.splitlines()[:2]
    assert "Rerun setup" in message
    hook.unlink()
    assert hook_chain.restore_note(repository) == hook_chain.RESTORE


def test_replaced_launcher_with_another_project_hook_asks_for_a_merge(
    installer: ModuleType, repository: Path, shipping_policy: ShippingPolicy
) -> None:
    hook = install_over(installer, repository, shipping_policy, PROJECT_HOOK)
    hook.write_text("#!/bin/sh\nexit 0\n")
    with pytest.raises(ValueError, match="merge them into pre-push.project"):
        installer.prepare_hook(repository)
    assert hook_chain.project_copy(hook).read_text() == PROJECT_HOOK
    git(repository, "status", "--short")


LEFTHOOK_HOOK = '#!/bin/sh\nif [ "$LEFTHOOK" = "0" ]; then exit 0; fi\n# {version}\nexec lefthook run pre-push\n'


def test_a_hook_manager_reinstalling_its_own_hook_replaces_the_kept_copy(
    installer: ModuleType, repository: Path, shipping_policy: ShippingPolicy
) -> None:
    older = LEFTHOOK_HOOK.format(version="1.0")
    hook = install_over(installer, repository, shipping_policy, older)
    assert hook_chain.project_copy(hook).read_text() == older
    newer = LEFTHOOK_HOOK.format(version="2.0")
    hook.write_text(newer)
    hook.chmod(0o755)
    installer.install(repository)
    assert hook_chain.project_copy(hook).read_text() == newer
    assert hook.read_text() == hook_chain.CHAINED_LAUNCHER
    hook.write_text("#!/bin/sh\nexit 0\n")
    with pytest.raises(ValueError, match="merge them into pre-push.project"):
        installer.prepare_hook(repository)
    assert hook_chain.project_copy(hook).read_text() == newer


def test_update_candidate_keeps_a_relative_hooks_path_of_its_own(
    repository: Path,
) -> None:
    git(repository, "config", "extensions.worktreeConfig", "true")
    candidate = repository.parent / "candidate"
    git(repository, "worktree", "add", "-q", "--detach", str(candidate), "HEAD")
    git(candidate, "config", "--worktree", "core.hooksPath", ".githooks")
    hook_chain.use_own_hooks(candidate)
    assert git(candidate, "config", "core.hooksPath") == ".githooks"
