"""Resolve Dart package directories without bypassing included analysis rules."""

import json
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from gate_config import validate_dart_exclusions


@pytest.mark.parametrize("style", ["absolute", "trailing-slash", "relative"])
def test_package_include_root_is_a_directory(
    runner: ModuleType, tmp_path: Path, style: str
) -> None:
    registry = tmp_path / ".dart_tool/package_config.json"
    registry.parent.mkdir()
    package = tmp_path / "package cache/lints"
    library = package / "lib"
    library.mkdir(parents=True)
    uri = package.as_uri()
    if style == "trailing-slash":
        uri += "/"
    elif style == "relative":
        uri = "../package%20cache/lints"
    registry.write_text(
        json.dumps(
            {"packages": [{"name": "lints", "rootUri": uri, "packageUri": "lib/"}]}
        )
    )
    options = tmp_path / "analysis_options.yaml"
    options.write_text("include: package:lints/recommended.yaml\n")
    (library / "recommended.yaml").write_text("include: baseline.yaml\n")
    baseline = library / "baseline.yaml"
    baseline.write_text("{}\n")
    runner.validate_dart_includes(options, tmp_path)
    baseline.write_text("analyzer:\n  errors:\n    avoid_dynamic_calls: ignore\n")
    with pytest.raises(ValueError, match="cannot exclude files or ignore"):
        runner.validate_dart_includes(options, tmp_path)
    baseline.write_text("analyzer:\n  exclude: ['**/*.dart']\n")
    with pytest.raises(ValueError, match="cannot exclude project files"):
        runner.validate_dart_includes(options, tmp_path)
    baseline.write_text("analyzer:\n  language:\n    strict-casts: false\n")
    with pytest.raises(ValueError, match="obsolete Dart language"):
        runner.validate_dart_includes(options, tmp_path)


def test_dart_setup_preserves_generated_excludes_and_native_yaml_list(
    installer: ModuleType, runner: ModuleType, tmp_path: Path
) -> None:
    excludes = [
        ".dart_tool/**",
        "**/*.g.dart",
        "**/*.freezed.dart",
        "**/*.gr.dart",
        "**/*.arb",
    ]
    options = json.loads(json.dumps(runner.DART_TYPING))
    options["analyzer"]["language"] = {"strict-inference": True}
    options["linter"]["rules"].update({"no_dynamic_casts": True, "no_raw_types": True})
    options["analyzer"]["exclude"] = excludes
    options["linter"]["rules"] = ["avoid_print", *options["linter"]["rules"]]
    options["plugins"] = {"riverpod_lint": "3.1.8", "flutter_skill_lints": "^0.11.2"}
    path = tmp_path / "analysis_options.yaml"
    path.write_text(yaml.safe_dump(options, sort_keys=False))
    runner.validate_typing(tmp_path, "dart", ["lib"])
    generated = tmp_path / "lib/generated.g.dart"
    generated.parent.mkdir()
    generated.write_text(
        "// GENERATED CODE - DO NOT MODIFY BY HAND\nconst value = 1;\n"
    )
    artifact = tmp_path / ".dart_tool/cache.g.dart"
    artifact.parent.mkdir()
    artifact.write_text("tool-managed artifact\n")
    changes: dict[str, str] = {}
    options["analyzer"]["language"].update(
        {"strict-casts": True, "strict-raw-types": False}
    )
    path.write_text(yaml.safe_dump(options))
    with pytest.raises(ValueError, match="obsolete Dart language"):
        runner.validate_typing(tmp_path, "dart", ["lib"])
    installer.configure_dart(tmp_path, tmp_path, {"path": ".", "checks": []}, changes)
    path.write_text(changes["analysis_options.yaml"])
    result = yaml.safe_load(path.read_text())
    assert result["analyzer"]["language"] == {"strict-inference": True}
    assert result["analyzer"]["exclude"] == excludes
    assert result["linter"]["rules"] == options["linter"]["rules"]
    assert result["plugins"] == options["plugins"]
    runner.validate_typing(tmp_path, "dart", ["lib"])
    commented = "# Project explanation\n" + path.read_text()
    path.write_text(commented)
    repeated: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, {"path": ".", "checks": []}, repeated)
    assert "analysis_options.yaml" not in repeated
    assert path.read_text() == commented
    for rule in ("no_dynamic_casts", "no_raw_types"):
        weakened = json.loads(json.dumps(result))
        weakened["linter"]["rules"].remove(rule)
        path.write_text(yaml.safe_dump(weakened))
        with pytest.raises(ValueError, match="strict linter.rules"):
            runner.validate_typing(tmp_path, "dart", ["lib"])
    path.write_text(changes["analysis_options.yaml"])
    nested = generated.parent / "analysis_options.yaml"
    options["analyzer"]["exclude"] = ["lib/**"]
    nested.write_text(yaml.safe_dump(options))
    with pytest.raises(ValueError, match="cannot exclude project files"):
        runner.validate_typing(tmp_path, "dart", ["lib"])
    result["analyzer"]["language"]["strict-raw-types"] = True
    nested.write_text(yaml.safe_dump(result))
    with pytest.raises(ValueError, match="obsolete Dart language"):
        runner.validate_typing(tmp_path, "dart", ["lib"])


@pytest.mark.parametrize(
    ("plugin", "migrate"),
    [
        ("0.10.2", True),
        ("^0.9.1", True),
        (None, False),
        ("0.11.0", True),
        ("^0.11.0", True),
        ("0.11.1", True),
        ("^0.11.1", True),
        ("0.11.2", False),
        ("^0.11.2", False),
        ("0.12.0", False),
        (">=0.11.0 <0.12.0", False),
        ({"path": "../custom-plugin"}, False),
    ],
)
def test_dart_setup_migrates_known_plugin_with_rules(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    plugin: str | dict[str, str] | None,
    migrate: bool,
) -> None:
    plugins: dict[str, str | dict[str, str]] = {"other_plugin": "1.2.3"}
    if plugin is not None:
        plugins["flutter_skill_lints"] = plugin
    path = tmp_path / "analysis_options.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "plugins": plugins,
                "analyzer": {
                    "language": {"strict-casts": True, "strict-raw-types": True}
                },
            }
        )
    )
    changes: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, {"path": ".", "checks": []}, changes)
    result = yaml.safe_load(changes["analysis_options.yaml"])
    canonical = yaml.safe_load(
        (
            installer.SOURCE
            / ".agents/skills/building-flutter-apps/references/analysis_options.yaml"
        ).read_text()
    )
    expected = dict(plugins)
    if migrate:
        expected["flutter_skill_lints"] = canonical["plugins"]["flutter_skill_lints"]
    assert result["plugins"] == expected
    assert result["analyzer"]["language"] == {"strict-inference": True}
    assert result["linter"]["rules"]["no_dynamic_casts"] is True
    assert result["linter"]["rules"]["no_raw_types"] is True
    path.write_text(changes["analysis_options.yaml"])
    runner.validate_typing(tmp_path, "dart")
    if migrate:
        outdated = {**result, "plugins": plugins}
        path.write_text(yaml.safe_dump(outdated))
        with pytest.raises(ValueError, match="older than the installed canonical"):
            runner.validate_typing(tmp_path, "dart")
        path.write_text(changes["analysis_options.yaml"])
    repeated: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, {"path": ".", "checks": []}, repeated)
    assert "analysis_options.yaml" not in repeated


def test_dart_without_exclusion_key_needs_no_rewrite(
    installer: ModuleType, runner: ModuleType, tmp_path: Path
) -> None:
    options = json.loads(json.dumps(runner.DART_TYPING))
    del options["analyzer"]["exclude"]
    content = "# Keep the project's comments\n" + yaml.safe_dump(options)
    path = tmp_path / "analysis_options.yaml"
    path.write_text(content)
    runner.validate_typing(tmp_path, "dart")
    changes: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, {"path": ".", "checks": []}, changes)
    assert "analysis_options.yaml" not in changes
    assert path.read_text() == content


@pytest.mark.parametrize("pattern", ["lib/**", "**/*.dart", "../**"])
def test_dart_exclusions_reject_project_patterns(tmp_path: Path, pattern: str) -> None:
    with pytest.raises(ValueError, match="cannot exclude project files"):
        validate_dart_exclusions(tmp_path, [pattern])


def test_dart_exclusions_require_generated_evidence(
    runner: ModuleType, tmp_path: Path
) -> None:
    source = tmp_path / "handwritten.g.dart"
    source.write_text("void important() {}\n")
    with pytest.raises(ValueError, match="handwritten source"):
        validate_dart_exclusions(tmp_path, ["**/*.g.dart"])
    attributes = tmp_path / ".gitattributes"
    attributes.write_text("handwritten.g.dart linguist-generated=true\n")
    validate_dart_exclusions(tmp_path, ["**/*.g.dart"])
    attributes.unlink()
    source.write_text("// GENERATED CODE - DO NOT MODIFY BY HAND\nconst value = 1;\n")
    validate_dart_exclusions(tmp_path, ["**/*.g.dart"])


@pytest.mark.parametrize("kind", ["directory", "symlink"])
def test_dart_exclusions_reject_nonfile_matches(tmp_path: Path, kind: str) -> None:
    path = tmp_path / "hidden.g.dart"
    if kind == "directory":
        path.mkdir()
        (path / "real.dart").write_text("void important() {}\n")
    else:
        target = tmp_path / "real.dart"
        target.write_text("void important() {}\n")
        path.symlink_to(target)
    with pytest.raises(ValueError, match="unsafe path"):
        validate_dart_exclusions(tmp_path, ["**/*.g.dart"])
