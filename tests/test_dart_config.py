"""Resolve Dart package directories without bypassing included analysis rules."""

import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from conftest import git
from gate_config import JsonObject, generated_sources, validate_dart_exclusions


def dart_format_command(installer: ModuleType) -> list[str]:
    return json.loads(
        (
            installer.SOURCE / ".agents/skills/he/templates/hard-eng.dart.json"
        ).read_text()
    )["packages"][0]["checks"][1]["command"]


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


@pytest.mark.parametrize(
    "section,group,rule",
    [
        ("analyzer", "language", "strict-inference"),
        ("linter", "rules", "avoid_dynamic_calls"),
    ],
)
def test_dart_setup_rejects_explicit_conflicts_without_writes(
    installer: ModuleType, tmp_path: Path, section: str, group: str, rule: str
) -> None:
    path = tmp_path / "analysis_options.yaml"
    original = yaml.safe_dump({section: {group: {rule: False}}})
    path.write_text(original)
    changes: dict[str, str] = {}
    with pytest.raises(ValueError, match="Conflicting setting"):
        installer.configure_dart(
            tmp_path, tmp_path, {"path": ".", "checks": []}, changes
        )
    assert path.read_text() == original
    assert not changes


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
    options["plugins"] = {"riverpod_lint": "3.1.9", "flutter_skill_lints": "^0.13.0"}
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
    ("name", "plugin", "migrate"),
    [
        ("flutter_skill_lints", "0.10.2", True),
        ("flutter_skill_lints", "^0.9.1", True),
        ("flutter_skill_lints", None, False),
        ("flutter_skill_lints", "0.11.0", True),
        ("flutter_skill_lints", "^0.11.0", True),
        ("flutter_skill_lints", "0.11.1", True),
        ("flutter_skill_lints", "^0.11.1", True),
        ("flutter_skill_lints", "0.11.2", True),
        ("flutter_skill_lints", "^0.11.2", True),
        ("flutter_skill_lints", "0.12.0", True),
        ("flutter_skill_lints", "^0.12.0", True),
        ("flutter_skill_lints", "0.13.0", False),
        ("flutter_skill_lints", "^0.13.0", False),
        ("flutter_skill_lints", ">=0.11.0 <0.12.0", False),
        ("flutter_skill_lints", {"path": "../custom-plugin"}, False),
        (
            "flutter_skill_lints",
            {"version": "^0.9.1", "diagnostics": {"use_ref_mounted_after_await": True}},
            True,
        ),
        ("riverpod_lint", "3.1.8", True),
        ("riverpod_lint", "2.6.5", True),
        ("riverpod_lint", "^2.6.5", True),
        ("riverpod_lint", {"version": "^2.6.5"}, True),
        ("riverpod_lint", {"version": "3.1.8"}, True),
        ("riverpod_lint", {"version": "^3.1.9"}, False),
        ("riverpod_lint", {"version": "^4.0.0"}, False),
        ("riverpod_lint", {"version": "3.1.8", "path": "../custom"}, False),
        (
            "riverpod_lint",
            {"version": "3.1.8", "git": "https://example.invalid/plugin"},
            False,
        ),
        (
            "riverpod_lint",
            {"version": "3.1.8", "hosted": "https://example.invalid"},
            False,
        ),
    ],
)
def test_dart_setup_migrates_known_plugin_with_rules(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    name: str,
    plugin: str | JsonObject | None,
    migrate: bool,
) -> None:
    plugins: JsonObject = {"other_plugin": "1.2.3"}
    if plugin is not None:
        plugins[name] = plugin
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
        version = canonical["plugins"][name]
        expected[name] = (
            {**plugin, "version": version} if isinstance(plugin, dict) else version
        )
    assert result["plugins"] == expected
    assert result["analyzer"]["language"] == {"strict-inference": True}
    assert result["linter"]["rules"]["no_dynamic_casts"] is True
    assert result["linter"]["rules"]["no_raw_types"] is True
    path.write_text(changes["analysis_options.yaml"])
    runner.validate_typing(tmp_path, "dart")
    if migrate:
        outdated = {**result, "plugins": plugins}
        path.write_text(yaml.safe_dump(outdated))
        with pytest.raises(
            ValueError, match="older than the installed canonical"
        ) as error:
            runner.validate_typing(tmp_path, "dart")
        assert name in str(error.value)
        assert canonical["plugins"][name] in str(error.value)
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


@pytest.mark.parametrize(
    "content",
    ["linter:\n  rules:\n    # avoid_print: false\n", "analyzer:\nlinter:\n"],
)
def test_dart_setup_fills_sections_that_hold_only_comments(
    installer: ModuleType, runner: ModuleType, tmp_path: Path, content: str
) -> None:
    path = tmp_path / "analysis_options.yaml"
    path.write_text(content)
    changes: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, {"path": ".", "checks": []}, changes)
    path.write_text(changes["analysis_options.yaml"])
    runner.validate_typing(tmp_path, "dart")


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


@pytest.mark.parametrize(
    "kind", ["empty", "generated", "ignored", "handwritten", "tracked", "symlink"]
)
def test_flutter_build_exclusion_preserves_source_checks(
    runner: ModuleType, tmp_path: Path, kind: str
) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: native_exclusions\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    excludes = ["build/**", "**/*.g.dart"]
    if kind != "empty":
        relative = (
            "build/source.g.dart"
            if kind in {"ignored", "tracked"}
            else "build/source.dart"
        )
        source = tmp_path / relative
        source.parent.mkdir()
        header = (
            "// GENERATED CODE - DO NOT MODIFY BY HAND\n" if kind == "generated" else ""
        )
        source.write_text(header + "void important() {}\n")
        if kind in {"ignored", "tracked"}:
            (tmp_path / ".gitignore").write_text("build/\n")
        if kind == "tracked":
            git(tmp_path, "add", "-f", relative)
        if kind == "symlink":
            source.unlink()
            target = tmp_path / "outside.dart"
            target.write_text("void important() {}\n")
            source.symlink_to(target)
    if kind in {"handwritten", "tracked", "symlink"}:
        with pytest.raises(ValueError, match="handwritten source|unsafe path"):
            validate_dart_exclusions(tmp_path, excludes)
    else:
        validate_dart_exclusions(tmp_path, excludes)


def test_pure_dart_platform_sources_remain_required(
    runner: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: plain_dart\n")
    with pytest.raises(ValueError, match="cannot exclude project files"):
        validate_dart_exclusions(tmp_path, ["web/**"])


@pytest.mark.parametrize(
    "kind",
    [
        "empty",
        "generated",
        "vendored",
        "handwritten-untracked",
        "handwritten-tracked",
        "handwritten-test-untracked",
        "handwritten-test-tracked",
    ],
)
def test_flutter_platform_exclusions_require_no_authored_dart(
    runner: ModuleType, tmp_path: Path, kind: str
) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: platform_exclusions\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    android = tmp_path / "android"
    android.mkdir()
    if kind != "empty":
        relative = (
            "android/test/fixture_test.dart"
            if kind.startswith("handwritten-test")
            else "android/main.dart"
        )
        source = tmp_path / relative
        source.parent.mkdir(exist_ok=True)
        source.write_text("void important() {}\n")
        if kind == "generated":
            source.write_text("// GENERATED CODE - DO NOT MODIFY BY HAND\n")
        if kind == "vendored":
            (tmp_path / ".gitattributes").write_text(
                "android/main.dart linguist-vendored=true\n"
            )
        if kind in {"handwritten-tracked", "handwritten-test-tracked"}:
            git(tmp_path, "add", relative)
    if kind.startswith("handwritten"):
        with pytest.raises(ValueError, match="handwritten source"):
            validate_dart_exclusions(tmp_path, ["android/**"])
    else:
        validate_dart_exclusions(tmp_path, ["android/**"])
    with pytest.raises(ValueError, match="cannot exclude project files"):
        validate_dart_exclusions(tmp_path, ["ios/**"])


def test_dart_format_discovers_authored_files_and_skips_deleted_or_generated_output(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = dart_format_command(installer)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/baseline.dart").write_text("void main() {}\n")
    (tmp_path / "lib/deleted.dart").write_text("void main() {}\n")
    git(tmp_path, "add", "lib/deleted.dart")
    (tmp_path / "lib/deleted.dart").unlink()
    for name in (
        "top_level_test.dart",
        "test/unit_test.dart",
        "integration_test/new_journey.dart",
        "test_driver/driver.dart",
        "android/entrypoint.dart",
    ):
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("void main() {}\n")
    for name in ("build/generated.dart", "android/build/generated.dart"):
        source = tmp_path / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("void malformed( {\n")
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    output = tmp_path / "format-arguments"
    dart = bin_directory / "dart"
    dart.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$FORMAT_ARGUMENTS"\n')
    dart.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_directory) + ":/usr/bin:/bin")
    monkeypatch.setenv("FORMAT_ARGUMENTS", str(output))
    subprocess.run(command, cwd=tmp_path, check=True)
    arguments = output.read_text().splitlines()
    assert {
        "lib/baseline.dart",
        "top_level_test.dart",
        "test/unit_test.dart",
        "integration_test/new_journey.dart",
        "test_driver/driver.dart",
        "android/entrypoint.dart",
    } <= set(arguments)
    assert {
        "lib/deleted.dart",
        "build/generated.dart",
        "android/build/generated.dart",
    }.isdisjoint(arguments)


def test_dart_format_fails_when_git_inventory_fails(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = dart_format_command(installer)
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    failed_git = bin_directory / "git"
    failed_git.write_text("#!/bin/sh\nexit 19\n")
    failed_git.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_directory) + ":/usr/bin:/bin")
    result = subprocess.run(command, cwd=tmp_path, check=False)
    assert result.returncode == 19


def test_dart_format_skips_an_empty_inventory(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command = dart_format_command(installer)
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    empty_git = bin_directory / "git"
    empty_git.write_text("#!/bin/sh\nexit 0\n")
    empty_git.chmod(0o755)
    failed_dart = bin_directory / "dart"
    failed_dart.write_text("#!/bin/sh\nexit 23\n")
    failed_dart.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_directory) + ":/usr/bin:/bin")
    result = subprocess.run(command, cwd=tmp_path, check=False)
    assert result.returncode == 0


@pytest.mark.parametrize(
    "l10n",
    ["", "arb-dir: lib/my strings\noutput-localization-file: messages.i18n.dart\n"],
)
def test_dart_generator_output_is_marked_generated_once(
    installer: ModuleType, tmp_path: Path, l10n: str
) -> None:
    git(tmp_path, "init", "-q")
    app = tmp_path / "apps/mobile"
    arbs = app / ("lib/my strings" if l10n else "lib/l10n")
    arbs.mkdir(parents=True)
    for name, content in (("app_en-US.arb", "{}"), ("x.arb", '{"@@locale":"fr"}')):
        (arbs / name).write_text(content)
    (app / "l10n.yaml").write_text(l10n)
    project = "*.gr.dart eol=lf\napps/mobile/lib/manual.g.dart -linguist-generated\n"
    (tmp_path / ".gitattributes").write_text(project)
    changes: dict[str, str] = {}
    installer.configure_dart_generated(tmp_path, app, changes)
    installer.configure_dart_generated(tmp_path, app, changes)
    output = "apps/mobile/" + arbs.relative_to(app).as_posix()
    quote = '"' if " " in output else ""
    stem, extension = (
        ("messages", "i18n.dart") if l10n else ("app_localizations", "dart")
    )
    assert changes[".gitattributes"] == (
        "*.g.dart linguist-generated=true\n*.freezed.dart linguist-generated=true\n"
        "*.gr.dart linguist-generated=true\n"
        + "".join(
            f"{quote}{output}/{name}{quote} linguist-generated=true\n"
            for name in (
                f"{stem}.{extension}",
                f"{stem}_en.{extension}",
                f"{stem}_fr.{extension}",
            )
        )
        + project
    )
    (tmp_path / ".gitattributes").write_text(changes[".gitattributes"])
    local = arbs.relative_to(app).as_posix()
    names = [
        "lib/claim.freezed.dart",
        "lib/manual.g.dart",
        "lib/route.gr.dart",
        f"{local}/{stem}_service.{extension}",
        f"{local}/{stem}_en.{extension}",
        "lib/claim.dart",
    ]
    assert generated_sources(app, names) == set(names[::2])
    repeated: dict[str, str] = {}
    installer.configure_dart_generated(tmp_path, app, repeated)
    assert repeated == {}
