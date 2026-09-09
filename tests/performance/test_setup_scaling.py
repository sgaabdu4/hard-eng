"""Keep package adaptation to one Git inventory regardless of package count."""

from pathlib import Path

import project_setup
import pytest
from gate_config import GateConfig


@pytest.mark.parametrize("count", [1, 60, 240])
def test_package_adaptation_reads_inventory_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    config: GateConfig = {"packages": [], "shared": []}
    files = []
    for index in range(count):
        directory = tmp_path / str(index)
        directory.mkdir()
        (directory / "pyproject.toml").write_text('[project]\nname="example"\n')
        files.append(directory / "app.py")
        config["packages"].append(
            {"path": str(index), "language": "python", "sources": ["src"], "checks": []}
        )
    calls = 0

    def inventory(root: Path) -> list[Path]:
        nonlocal calls
        assert root == tmp_path
        calls += 1
        return files

    monkeypatch.setattr(project_setup, "repository_files", inventory)
    project_setup.adapt_packages(tmp_path, config)
    assert calls == 1
    assert len(config["packages"]) == count
    assert all(package["sources"] == ["app.py"] for package in config["packages"])
