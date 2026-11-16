"""A nested Dart settings file reaches the package's own settings through its include chain."""

from pathlib import Path
from types import ModuleType

import pytest
import yaml
from dart_boundaries import DART_TYPING


def nested_file(root: Path, name: str, content: str) -> Path:
    (root / "analysis_options.yaml").write_text(yaml.safe_dump(DART_TYPING))
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def test_a_nested_settings_file_must_include_the_package_settings(
    runner: ModuleType, tmp_path: Path
) -> None:
    """A settings file in a source folder reaches the package's own file by its include chain, so the lint set cannot drop."""
    copy = yaml.safe_dump(DART_TYPING)
    for content in (copy, "analyzer: {}\n", "include: ../lib/shared.yaml\n"):
        nested = nested_file(tmp_path, "tool/analysis_options.yaml", content)
        with pytest.raises(ValueError, match="must include") as error:
            runner.validate_typing(tmp_path, "dart", ["tool"])
        assert f"{nested}" in str(error.value)
        assert "include: ../analysis_options.yaml" in str(error.value)
    nested_file(
        tmp_path, "tool/analysis_options.yaml", "include: ../analysis_options.yaml\n"
    )
    runner.validate_typing(tmp_path, "dart", ["tool"])
    (tmp_path / "tool/deep").mkdir()
    (tmp_path / "tool/deep/analysis_options.yaml").write_text(
        "include: ../analysis_options.yaml\n"
    )
    runner.validate_typing(tmp_path, "dart", ["tool"])
    (tmp_path / "analysis_options.yaml").write_text("linter: {}\n")
    with pytest.raises(TypeError, match="Dart requires analyzer settings") as error:
        runner.validate_typing(tmp_path, "dart", ["tool"])
    assert str(error.value).endswith(f": {tmp_path / 'analysis_options.yaml'}")


def test_a_nested_settings_file_cannot_override_a_strict_setting(
    runner: ModuleType, tmp_path: Path
) -> None:
    """The merged settings of a nested file run through the same typing check."""
    setting = next(iter(DART_TYPING["analyzer"]["language"]))
    content = f"include: ../analysis_options.yaml\nanalyzer:\n  language:\n    {setting}: false\n"
    nested_file(tmp_path, "tool/analysis_options.yaml", content)
    with pytest.raises(ValueError, match="Dart requires strict analyzer.language"):
        runner.validate_typing(tmp_path, "dart", ["tool"])
    rule = next(iter(DART_TYPING["linter"]["rules"]))
    content = (
        f"include: ../analysis_options.yaml\nlinter:\n  rules:\n    {rule}: false\n"
    )
    nested_file(tmp_path, "tool/analysis_options.yaml", content)
    with pytest.raises(ValueError, match=rf"{rule} is set to false"):
        runner.validate_typing(tmp_path, "dart", ["tool"])
