"""Keep package adaptation to one Git inventory regardless of package count."""

from collections.abc import Iterator
from pathlib import Path
from typing import override

import gate_config
import project_setup
import pytest
from gate_config import GateConfig, Group


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


class PackageVisits(list[Group]):
    """Count sibling package visits, excluding filesystem timing noise."""

    visits: int = 0

    @override
    def __iter__(self) -> Iterator[Group]:
        for group in super().__iter__():
            self.visits += 1
            yield group


def test_baseline_validation_does_not_rescan_siblings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def inventory(root: Path) -> list[Path]:
        assert root == tmp_path
        return []

    monkeypatch.setattr(gate_config, "repository_files", inventory)
    visits = []
    for count in (8, 32):
        packages = PackageVisits()
        for index in range(count):
            packages.append(
                {
                    "path": str(index),
                    "language": "python",
                    "sources": [],
                    "checks": [
                        {"name": role, "role": role, "command": ["true"]}
                        for role in ("lockfiles", "vulnerabilities", "security")
                    ],
                }
            )
        gate_config.validate_required_checks(
            tmp_path,
            {
                "packages": packages,
                "shared": [
                    {"name": role, "role": role, "command": ["true"]}
                    for role in ("secrets-files", "secrets-history")
                ],
            },
        )
        visits.append(packages.visits)
    # With sibling directories at a fixed depth, four times the packages must
    # not exceed four times the visits. An all-packages parent search fails this.
    assert visits[0] > 0
    assert visits[1] <= visits[0] * 4
