"""Prove temporary worktrees take submodules from a donor checkout and fetch what it lacks."""

from pathlib import Path

import pytest
import ship_actions
from conftest import commit, init
from shipping import git
from submodules import update_submodules

ALLOW_FILE = ("-c", "protocol.file.allow=always")


def _git(root: Path, *arguments: str) -> str:
    return git(root, *arguments).strip()


def _library(tmp_path: Path, name: str) -> tuple[Path, Path]:
    work, remote = tmp_path / name, tmp_path / f"{name}.git"
    init(work)
    _git(tmp_path, "init", "--bare", "-q", "-b", "main", str(remote))
    _git(work, "remote", "add", "origin", remote.as_uri())
    return work, remote


def _publish(work: Path, message: str) -> str:
    (work / f"{message}.txt").write_text(message)
    revision = commit(work, message)
    _git(work, "push", "-q", "origin", "HEAD:refs/heads/main")
    return revision


@pytest.fixture
def nested_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    for name in ("GIT_ALLOW_PROTOCOL", "GIT_CONFIG_COUNT"):
        monkeypatch.delenv(name, raising=False)
    inner, inner_remote = _library(tmp_path, "inner")
    _publish(inner, "inner pinned")
    module, module_remote = _library(tmp_path, "module")
    _git(module, *ALLOW_FILE, "submodule", "add", "-q", inner_remote.as_uri(), "inner")
    _publish(module, "module pinned")
    root = tmp_path / "project"
    init(root)
    _git(
        root, *ALLOW_FILE, "submodule", "add", "-q", module_remote.as_uri(), "component"
    )
    _git(root, *ALLOW_FILE, "submodule", "update", "-q", "--init", "--recursive")
    commit(root, "project with nested submodules")
    return root, module, module_remote


def _prepare(root: Path, tmp_path: Path) -> Path:
    checkout = tmp_path / "snapshot"
    environment = ship_actions.snapshot_environment(root)
    _git(root, "worktree", "add", "-q", "--detach", str(checkout), "HEAD")
    ship_actions.prepare_checkout(root, checkout, environment)
    return checkout


def _assert_pinned(checkout: Path, module_remote: Path) -> None:
    component = checkout / "component"
    assert _git(component, "rev-parse", "HEAD") == _git(
        checkout, "rev-parse", "HEAD:component"
    )
    assert _git(component / "inner", "rev-parse", "HEAD") == _git(
        component, "rev-parse", "HEAD:inner"
    )
    assert not _git(checkout, "status", "--porcelain")
    assert all(
        line.startswith(" ")
        for line in git(checkout, "submodule", "status", "--recursive").splitlines()
    )
    for directory in (component, component / "inner"):
        assert _git(directory, "rev-parse", "--is-shallow-repository") == "true"
    assert _git(component, "config", "remote.origin.url") == module_remote.as_uri()


def test_prepare_checkout_reuses_main_submodules_without_network(
    nested_project: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    root, _, module_remote = nested_project
    moved = tmp_path / "moved"
    moved.mkdir()
    for remote in tmp_path.glob("*.git"):
        remote.rename(moved / remote.name)
    _assert_pinned(_prepare(root, tmp_path), module_remote)


def test_prepare_checkout_reuses_main_submodules_when_git_variables_are_inherited(
    nested_project: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, module_remote = nested_project
    moved = tmp_path / "moved"
    moved.mkdir()
    for remote in tmp_path.glob("*.git"):
        remote.rename(moved / remote.name)
    monkeypatch.setenv("GIT_DIR", str(root / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(root))
    checkout = _prepare(root, tmp_path)
    monkeypatch.delenv("GIT_DIR")
    monkeypatch.delenv("GIT_WORK_TREE")
    _assert_pinned(checkout, module_remote)


def test_prepare_checkout_checks_out_the_pin_when_main_sits_on_another_commit(
    nested_project: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    root, module, module_remote = nested_project
    newer = _publish(module, "module newer")
    _git(root / "component", "fetch", "-q", "origin")
    _git(root / "component", "checkout", "-q", "--detach", newer)
    moved = tmp_path / "moved"
    moved.mkdir()
    for remote in tmp_path.glob("*.git"):
        remote.rename(moved / remote.name)
    checkout = _prepare(root, tmp_path)
    assert _git(checkout / "component", "rev-parse", "HEAD") != newer
    _assert_pinned(checkout, module_remote)


def test_prepare_checkout_fetches_when_main_lacks_pinned_commit(
    nested_project: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, module, module_remote = nested_project
    newer = _publish(module, "module newer")
    _git(root, "update-index", "--cacheinfo", f"160000,{newer},component")
    _git(root, "commit", "-qm", "pin the newer module revision")
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    checkout = _prepare(root, tmp_path)
    assert _git(checkout / "component", "rev-parse", "HEAD") == newer
    _assert_pinned(checkout, module_remote)


def test_prepare_checkout_fetches_when_main_has_no_submodule(
    nested_project: tuple[Path, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, module_remote = nested_project
    fresh = tmp_path / "fresh"
    _git(tmp_path, "clone", "-q", str(root), str(fresh))
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
    _assert_pinned(_prepare(fresh, tmp_path), module_remote)


def test_previous_revision_tree_takes_its_submodules_from_the_current_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependency, canonical, upstream = (
        tmp_path / name for name in ("dependency", "canonical", "upstream")
    )
    for repository in (dependency, canonical, upstream):
        init(repository)
    allow = ("-c", "protocol.file.allow=always")
    (dependency / "contract.txt").write_text("pinned dependency\n")
    commit(dependency, "pinned dependency")
    _git(canonical, *allow, "submodule", "add", dependency.as_uri(), "dependency")
    commit(canonical, "canonical with dependency")
    _git(upstream, *allow, "submodule", "add", canonical.as_uri(), "canonical")
    pinned = commit(upstream, "pin canonical")
    source, old = tmp_path / "source", tmp_path / "previous"
    _git(tmp_path, "clone", "-q", str(upstream), str(source))
    _git(source, "worktree", "add", "-q", "--detach", str(old), pinned)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "always")
    update_submodules(source)
    monkeypatch.delenv("GIT_CONFIG_COUNT")
    for repository in (dependency, canonical):
        repository.rename(repository.with_name(f"{repository.name}-gone"))
    update_submodules(old, source)
    module = old / "canonical"
    assert (module / "dependency/contract.txt").read_text() == "pinned dependency\n"
    assert _git(module, "config", "remote.origin.url") == canonical.as_uri()
    assert not _git(old, "status", "--porcelain")
    for checkout in (module, module / "dependency"):
        assert _git(checkout, "rev-parse", "--is-shallow-repository") == "true"
