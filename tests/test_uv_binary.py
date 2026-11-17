"""`uv run --no-sync ruff` runs the binary the project environment holds; the full check proves that binary is the ruff package's own file."""

import subprocess
from pathlib import Path

import pytest
from gate_config import Gate, Group
from resolved_settings import validate_resolved

LINT = ["uv", "run", "--no-sync", "ruff", "check", "."]


LOCK = (
    'version = 1\n[[package]]\nname = "ruff"\nversion = "0.17.5"\nsource = {{ {} }}\n'
)
REGISTRY = 'registry = "https://pypi.org/simple"'


def environment(root: Path, fake: bool, source: str = REGISTRY) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "0"\nrequires-python = ">=3.10"\n'
    )
    (root / "a.py").write_text("x = 1\n")
    (root / "uv.lock").write_text(LOCK.format(source))
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["uv", "venv", "-q", str(root / ".venv")], cwd=root, check=True)
    if fake:
        script = root / ".venv/bin/ruff"
        script.write_text(
            '#!/bin/sh\ncase "$*" in *--show-*) exec uvx ruff@latest "$@";; esac\nexit 0\n'
        )
        script.chmod(0o755)
    else:
        subprocess.run(
            ["uv", "pip", "install", "-q", "--python", str(root / ".venv"), "ruff"],
            cwd=root,
            check=True,
        )


def judge(root: Path) -> None:
    gate: Gate = {"name": "lint", "role": "lint", "command": LINT}
    groups: list[Group] = [{"path": ".", "checks": [gate]}]
    validate_resolved(root, groups, 900)


def test_a_ruff_file_that_the_ruff_package_did_not_install_is_refused(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: a workspace member's script or a copied file in .venv/bin can stand in for Ruff and exit 0."""
    environment(tmp_path, fake=True)
    with pytest.raises(ValueError, match=r"not installed by the ruff package"):
        judge(tmp_path)


def test_the_ruff_package_own_file_passes(tmp_path: Path) -> None:
    environment(tmp_path, fake=False)
    judge(tmp_path)


@pytest.mark.parametrize(
    "source",
    [
        'directory = "tools/ruff"',
        'editable = "tools/ruff"',
        'path = "tools/ruff.whl"',
        'git = "https://example.invalid/ruff"',
    ],
)
def test_a_ruff_that_the_lockfile_takes_from_anywhere_but_the_registry_is_refused(
    tmp_path: Path, source: str
) -> None:
    """HE-NO-SWITCH-OFF: a local package named `ruff` is not the tool: only a registry source in uv.lock counts."""
    environment(tmp_path, fake=False, source=source)
    with pytest.raises(ValueError, match=r"registry"):
        judge(tmp_path)
