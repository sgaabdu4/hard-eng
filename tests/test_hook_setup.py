"""Codex hook-configuration conflicts preserve target project settings."""

import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from test_setup import snapshot


def installer_project(repository: Path) -> Path:
    (repository / "package.json").write_text('{"private":true}')
    (repository / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    return repository


@pytest.mark.parametrize(
    ("features", "setting"),
    [
        ("hooks = false\n", "hooks"),
        ("codex_hooks = false\n", "codex_hooks"),
    ],
)
def test_project_codex_disabled_hooks_conflict_writes_nothing(
    installer: ModuleType, repository: Path, features: str, setting: str
) -> None:
    root = installer_project(repository)
    config = root / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text("[features]\n" + features)
    before = snapshot(root)

    with pytest.raises(
        ValueError, match=rf"project-local .codex/config.toml \[features\].{setting}"
    ):
        installer.install(root)

    assert snapshot(root) == before


@pytest.mark.parametrize(
    "features",
    [
        "",
        "hooks = true\n",
        "codex_hooks = true\n",
        "hooks = true\ncodex_hooks = false\n",
    ],
)
def test_project_codex_enabled_or_unset_hooks_are_allowed(
    installer: ModuleType, repository: Path, features: str
) -> None:
    root = installer_project(repository)
    if features:
        config = root / ".codex/config.toml"
        config.parent.mkdir()
        config.write_text("[features]\n" + features)

    installer.install(root)


def test_malformed_project_codex_config_fails_before_writes(
    installer: ModuleType, repository: Path
) -> None:
    root = installer_project(repository)
    config = root / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text("[features\n")
    before = snapshot(root)

    with pytest.raises(tomllib.TOMLDecodeError):
        installer.install(root)

    assert snapshot(root) == before
