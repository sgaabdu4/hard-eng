"""Setup rules: what setup adds to an installed gates file and what it refuses."""

from pathlib import Path

import pytest
from conftest import commit, init
from gate_config import GateConfig, validate_file_sizes
from project_setup import (
    adapt_packages,
    validate_dart_exclusions,
)


@pytest.mark.parametrize(
    ("language", "manifest", "text", "lock"),
    [
        ("dart", "pubspec.yaml", "name: app\n", "pubspec.lock"),
        ("python", "pyproject.toml", '[project]\nname = "app"\n', "uv.lock"),
        ("javascript", "package.json", '{"name": "app"}\n', "bun.lock"),
    ],
)
def test_an_ignored_lock_file_is_refused(
    tmp_path: Path, language: str, manifest: str, text: str, lock: str
) -> None:
    root = tmp_path / "project"
    init(root)
    package = root / "app"
    package.mkdir()
    (package / manifest).write_text(text)
    (package / lock).write_text("# lock\n")
    (root / ".gitignore").write_text(f"{lock}\n")
    commit(root, "start")
    config: GateConfig = {
        "shared": [],
        "packages": [
            {"path": "app", "language": language, "sources": ["lib"], "checks": []}
        ],
    }
    with pytest.raises(ValueError, match=rf"app/{lock} is ignored by Git") as refused:
        adapt_packages(root, config)
    assert ".gitignore" in str(refused.value)
    (root / ".gitignore").write_text("")
    commit(root, "track the lock file")
    adapt_packages(root, config)


def test_the_exclusion_refusal_names_the_file_and_the_entry(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot exclude project files") as refused:
        validate_dart_exclusions(tmp_path, ["lib/**", "**/*.g.dart", "test/**"])
    message = str(refused.value)
    assert str(tmp_path / "analysis_options.yaml") in message
    assert "'lib/**', 'test/**'" in message
    assert "g.dart" not in message
    with pytest.raises(TypeError, match="must be a list of patterns"):
        validate_dart_exclusions(tmp_path, "**/*.g.dart")
    validate_dart_exclusions(tmp_path, ["**/*.g.dart"])


def test_the_line_limit_refusal_names_the_ways_out(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "big.py").write_text("value = 1\n" * 1001)
    with pytest.raises(ValueError, match="big.py: 1001 lines") as refused:
        validate_file_sizes(root, {})
    message = str(refused.value)
    assert "Split the file" in message
    assert "linguist-generated=true" in message
    assert ".gitattributes" in message
    assert "file_size_exceptions" in message
    assert "reason" in message
    assert "evidence" in message
    assert "hard-eng.gates.json" in message
