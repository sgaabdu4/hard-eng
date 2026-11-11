import json
from pathlib import Path

from gate_config import json_layout


def write(path: Path, config: dict[str, object]) -> None:
    path.write_text(json.dumps(config))


def test_an_extended_local_file_sets_the_json_layout(tmp_path: Path) -> None:
    write(
        tmp_path / "base.json",
        {"formatter": {"indentStyle": "space", "indentWidth": 4}},
    )
    write(tmp_path / "biome.json", {"extends": ["./base.json"]})
    assert json_layout(tmp_path) == ("    ", 4, 80)


def test_the_root_formatter_overrides_the_extended_one(tmp_path: Path) -> None:
    write(
        tmp_path / "base.json",
        {"formatter": {"indentStyle": "space", "lineWidth": 100}},
    )
    write(
        tmp_path / "biome.json",
        {"extends": "./base.json", "formatter": {"indentStyle": "tab"}},
    )
    assert json_layout(tmp_path) == ("\t", 2, 100)


def test_an_extended_package_name_keeps_the_default_layout(tmp_path: Path) -> None:
    write(tmp_path / "biome.json", {"extends": ["some-package", "//"]})
    assert json_layout(tmp_path) == ("\t", 2, 80)


def test_a_file_that_extends_itself_ends(tmp_path: Path) -> None:
    write(
        tmp_path / "biome.json",
        {"extends": ["./biome.json"], "formatter": {"indentStyle": "space"}},
    )
    assert json_layout(tmp_path) == ("  ", 2, 80)
