"""A first install commits its files when the hooks folder lies inside the work tree."""

from pathlib import Path
from types import ModuleType

import hook_chain
import pytest
from conftest import commit, git

OWNER_PRE_PUSH = "#!/bin/sh\necho owner pre-push\n"
OWNER_POST_CHECKOUT = '#!/bin/sh\necho "$1" > project.args\n'
HOOKS = ".githooks"


def owner_hook(repository: Path, name: str, text: str) -> None:
    path = repository / HOOKS / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def node_project(root: Path) -> None:
    (root / "package.json").write_text('{"private":true}')
    (root / "bun.lock").write_text('{"lockfileVersion": 1}\n')


def hooks_project(repository: Path, ignores: str, hooks: dict[str, str]) -> None:
    node_project(repository)
    git(repository, "config", "core.hooksPath", HOOKS)
    (repository / ".gitignore").write_text(ignores)
    for name, text in hooks.items():
        owner_hook(repository, name, text)
    commit(repository, "project")


def install(
    installer: ModuleType,
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> str:
    capsys.readouterr()
    installer.install(repository)
    return capsys.readouterr().out


def tracked(repository: Path) -> list[str]:
    return git(repository, "ls-files").splitlines()


def test_a_first_install_commits_its_files_when_the_hooks_folder_is_ignored(
    installer: ModuleType,
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hooks_project(repository, f"{HOOKS}/\n", {"pre-push": OWNER_PRE_PUSH})
    output = install(installer, repository, capsys)
    assert "Committed the installed files locally without pushing." in output
    assert ".hooks/hard-eng.py" in tracked(repository)
    assert git(repository, "status", "--porcelain") == ""
    hook = repository / HOOKS / "pre-push"
    assert hook.read_text() == hook_chain.CHAINED_LAUNCHER
    assert (repository / HOOKS / "pre-push.project").read_text() == OWNER_PRE_PUSH
    assert not [name for name in tracked(repository) if name.startswith(HOOKS)]


def test_a_hooks_folder_that_is_not_ignored_still_commits_its_hook(
    installer: ModuleType,
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hooks_project(repository, ".env\n", {"pre-push": OWNER_PRE_PUSH})
    output = install(installer, repository, capsys)
    assert "Committed the installed files locally without pushing." in output
    assert git(repository, "status", "--porcelain") == ""
    assert git(repository, "show", f"HEAD:{HOOKS}/pre-push") == (
        hook_chain.CHAINED_LAUNCHER.strip()
    )
    assert git(repository, "show", f"HEAD:{HOOKS}/pre-push.project") == (
        OWNER_PRE_PUSH.strip()
    )


def test_a_tracked_hook_takes_its_kept_copy_into_the_commit_when_only_the_copy_is_ignored(
    installer: ModuleType,
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hooks_project(repository, "*.project\n", {"pre-push": OWNER_PRE_PUSH})
    output = install(installer, repository, capsys)
    assert "Committed the installed files locally without pushing." in output
    assert f"{HOOKS}/pre-push" in tracked(repository)
    assert git(repository, "show", f"HEAD:{HOOKS}/pre-push.project") == (
        OWNER_PRE_PUSH.strip()
    )


def test_an_ignored_installed_path_with_local_content_still_blocks_the_commit(
    installer: ModuleType,
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    node_project(repository)
    (repository / ".gitignore").write_text("AGENTS.md\n")
    commit(repository, "project")
    (repository / "AGENTS.md").write_text("# Local rules\n")
    head = git(repository, "rev-parse", "HEAD")
    output = install(installer, repository, capsys)
    assert "Installed files are not committed" in output
    assert "these paths already had local changes: AGENTS.md" in output
    assert git(repository, "rev-parse", "HEAD") == head


def test_the_worktree_hook_and_kept_copies_of_an_ignored_hooks_folder_stay_local(
    installer: ModuleType,
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hooks_project(
        repository,
        f"{HOOKS}/\n",
        {"pre-push": OWNER_PRE_PUSH, "post-checkout": OWNER_POST_CHECKOUT},
    )
    head = git(repository, "rev-parse", "HEAD")
    output = install(installer, repository, capsys)
    assert "Committed the installed files locally without pushing." in output
    assert git(repository, "rev-parse", "HEAD") != head
    assert git(repository, "status", "--porcelain") == ""
    assert not [name for name in tracked(repository) if name.startswith(HOOKS)]
    folder = repository / HOOKS
    assert (folder / "post-checkout").read_text() == hook_chain.WORKTREE_LAUNCHER
    assert (folder / "post-checkout.project").read_text() == OWNER_POST_CHECKOUT
    assert (folder / "pre-push.project").read_text() == OWNER_PRE_PUSH


def test_a_new_worktree_runs_the_owner_hook_and_the_preparation_from_an_ignored_hooks_folder(
    installer: ModuleType,
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    hooks_project(
        repository, f"{HOOKS}/\n.env\n", {"post-checkout": OWNER_POST_CHECKOUT}
    )
    install(installer, repository, capsys)
    assert ".hooks/hard-eng.py" in tracked(repository)
    (repository / ".env").write_text("SECRET=local\n")
    linked = repository.parent / "linked"
    git(repository, "worktree", "add", "-q", str(linked))
    assert set((linked / "project.args").read_text().strip()) == {"0"}
    assert (linked / ".env").resolve() == (repository / ".env").resolve()
