"""Resolve Dart package directories without bypassing included analysis rules."""

import json
import re
import subprocess
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
import yaml
from conftest import git
from dart_boundaries import (
    DART_TYPING,
    nested_package_patterns,
    validate_dart_boundaries,
    validate_dart_includes,
)
from gate_config import (
    Gate,
    Group,
    JsonObject,
    dart_scan_includes_boundaries,
    generated_sources,
)
from project_setup import adapt_package, dependency_command, validate_dart_exclusions


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
    validate_dart_includes(options, tmp_path)
    baseline.write_text("analyzer:\n  errors:\n    avoid_dynamic_calls: ignore\n")
    with pytest.raises(ValueError, match="cannot exclude files or ignore"):
        validate_dart_includes(options, tmp_path)
    baseline.write_text("analyzer:\n  exclude: ['**/*.dart']\n")
    with pytest.raises(ValueError, match="cannot exclude project files"):
        validate_dart_includes(options, tmp_path)
    baseline.write_text("analyzer:\n  language:\n    strict-casts: false\n")
    with pytest.raises(ValueError, match="obsolete Dart language"):
        validate_dart_includes(options, tmp_path)


def test_a_fault_in_an_included_package_names_the_include_to_remove(
    tmp_path: Path,
) -> None:
    """A project cannot change a file of a package, only its own include of it."""
    registry = tmp_path / ".dart_tool/package_config.json"
    registry.parent.mkdir()
    library = tmp_path / "cache/team_lints/lib"
    library.mkdir(parents=True)
    packages = [
        {"name": "team_lints", "rootUri": library.parent.as_uri(), "packageUri": "lib/"}
    ]
    registry.write_text(json.dumps({"packages": packages}))
    (library / "all.yaml").write_text("include: package:team_lints/core.yaml\n")
    core = library / "core.yaml"
    core.write_text("analyzer:\n  language:\n    strict-casts: true\n")
    shared = tmp_path / "shared.yaml"
    shared.write_text("include: package:team_lints/all.yaml\n")
    options = tmp_path / "analysis_options.yaml"
    options.write_text("include: shared.yaml\n")
    with pytest.raises(ValueError, match="obsolete Dart language") as error:
        validate_dart_includes(options, tmp_path)
    message = str(error.value)
    assert f": {core.resolve()}. A package file cannot be changed" in message
    assert (
        f"remove `include: package:team_lints/all.yaml` from {shared.resolve()}"
        in message
    )
    assert message.count("cannot be changed") == 1
    shared.write_text("analyzer:\n  language:\n    strict-casts: true\n")
    with pytest.raises(ValueError, match="obsolete Dart language") as error:
        validate_dart_includes(options, tmp_path)
    assert str(error.value).endswith(f": {shared.resolve()}")


@pytest.mark.parametrize("content", ["include: ../lib/shared.yaml\n", "analyzer: {}\n"])
def test_a_nested_settings_file_that_lacks_the_settings_is_named_with_its_step(
    runner: ModuleType, tmp_path: Path, content: str
) -> None:
    """A settings file in a source folder replaces the package's settings for that folder."""
    (tmp_path / "analysis_options.yaml").write_text(yaml.safe_dump(DART_TYPING))
    runner.validate_typing(tmp_path, "dart", ["tool"])
    nested = tmp_path / "tool/analysis_options.yaml"
    nested.parent.mkdir()
    nested.write_text(content)
    with pytest.raises((TypeError, ValueError), match="Dart requires") as error:
        runner.validate_typing(tmp_path, "dart", ["tool"])
    assert f": {nested}. This file replaces the package's settings" in str(error.value)
    assert "or remove it" in str(error.value)
    nested.unlink()
    (tmp_path / "analysis_options.yaml").write_text("linter: {}\n")
    with pytest.raises(TypeError, match="Dart requires analyzer settings") as error:
        runner.validate_typing(tmp_path, "dart", ["tool"])
    assert str(error.value).endswith(f": {tmp_path / 'analysis_options.yaml'}")


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
    options = json.loads(json.dumps(DART_TYPING))
    options["analyzer"]["language"] = {"strict-inference": True}
    options["linter"]["rules"].update({"no_dynamic_casts": True, "no_raw_types": True})
    options["analyzer"]["exclude"] = excludes
    options["linter"]["rules"] = ["avoid_print", *options["linter"]["rules"]]
    options["plugins"] = {"riverpod_lint": "3.1.9", "flutter_skill_lints": "^0.13.4"}
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
        ("flutter_skill_lints", "0.13.0", True),
        ("flutter_skill_lints", "^0.13.4", False),
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
    options = json.loads(json.dumps(DART_TYPING))
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


@pytest.mark.parametrize(
    ("arguments", "covers"),
    [
        ("--threshold 0 --strict --format json", True),
        ("--format json --threshold 0 --strict", True),
        ("--strict --format json --threshold 0", True),
        ("--format json --threshold 0 --strict --no-boundary-violations", False),
        ("--format json --threshold 1 --strict", False),
    ],
)
def test_dart_scan_covers_boundaries_in_any_argument_order(
    arguments: str, covers: bool
) -> None:
    gate: Gate = {
        "name": "dead-code",
        "role": "dead-code-duplicates",
        "command": ["dart-decimate", "check", ".", *arguments.split()],
        "report": {"type": "dart-decimate", "stdout": True},
    }
    assert dart_scan_includes_boundaries(gate) is covers


def test_dart_package_with_comment_only_dependencies_is_accepted(
    tmp_path: Path,
) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: stock\ndependencies:\n  # none yet\ndev_dependencies:\n  lints: ^6.0.0\n"
    )
    assert dependency_command(tmp_path, "dart")[0] == "dart"


@pytest.mark.parametrize(
    ("dependency", "expected"),
    [
        (
            "flutter:\n    sdk: flutter",
            ["flutter", "test", "--no-pub", "--machine", "test/performance"],
        ),
        ("path: ^1.9.0", ["dart", "test", "test/performance", "--reporter=json"]),
    ],
)
def test_flutter_performance_suite_runs_without_package_test(
    installer: ModuleType, tmp_path: Path, dependency: str, expected: list[str]
) -> None:
    """`dart test` needs package:test, which Flutter's pinned test_api blocks beside build_runner."""
    (tmp_path / "pubspec.yaml").write_text(
        f"name: app\ndependencies:\n  {dependency}\n"
    )
    (tmp_path / "pubspec.lock").write_text("packages: {}\n")
    template = installer.SOURCE / ".agents/skills/he/templates/hard-eng.dart.json"
    package: Group = json.loads(template.read_text())["packages"][0]
    for _ in range(2):
        adapt_package(tmp_path, package)
        performance = [
            gate for gate in package["checks"] if gate["role"] == "performance"
        ]
        assert performance[0]["command"] == expected


def test_generated_sources_reads_paths_from_a_file_not_a_live_pipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue 375: writing paths into git's stdin while it wrote output deadlocked on macOS."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitattributes").write_text("*.g.dart linguist-generated=true\n")
    spy = Mock(wraps=subprocess.run)
    monkeypatch.setattr(subprocess, "run", spy)
    names = [f"lib/file_{index}{'.g' * (index % 2)}.dart" for index in range(5000)]
    assert generated_sources(tmp_path, names) == set(names[1::2])
    assert "input" not in spy.call_args.kwargs
    assert hasattr(spy.call_args.kwargs["stdin"], "fileno")


def test_generated_sources_starts_one_git_process_in_a_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    names = ["lib/a.g.dart", "lib/b.dart"]
    assert generated_sources(tmp_path, names) == set()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitattributes").write_text("*.g.dart linguist-generated=true\n")
    spy = Mock(wraps=subprocess.run)
    monkeypatch.setattr(subprocess, "run", spy)
    assert generated_sources(tmp_path, names) == {"lib/a.g.dart"}
    assert spy.call_count == 1


def test_the_missing_boundary_error_names_the_file_and_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def native_config(*_args: object, cwd: Path, **_kwargs: object) -> str:
        """Dart Decimate's own discovery, for the one file name that the error gives."""
        config: JsonObject = {}
        for path in cwd.glob(".dart-decimaterc.json"):
            config = json.loads(path.read_text())
        return json.dumps({"config": config})

    monkeypatch.setattr(subprocess, "check_output", native_config)
    command = ["dart-decimate", "check", ".", "--strict"]
    with pytest.raises(
        ValueError, match="Dart boundaries are missing or not usable"
    ) as caught:
        validate_dart_boundaries(command, tmp_path, 5)
    step = re.search(r'Set (".+?": \[.+?\]) .* make (\S+) for', str(caught.value))
    assert step, str(caught.value)
    key, name = step.groups()
    (tmp_path / name).write_text("{" + key + "}")
    for folder in ("domain", "ui"):
        (tmp_path / "lib" / folder).mkdir(parents=True)
        (tmp_path / "lib" / folder / "page.dart").write_text("void main() {}\n")
    validate_dart_boundaries(command, tmp_path, 5)


def test_a_settings_file_that_the_tool_rejects_shows_the_tools_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "app"
    package.mkdir()
    reason = "failed to parse config .dart-decimaterc.json: expected `,` or `]`"

    def rejecting_tool(*args: list[str], **_kwargs: object) -> str:
        raise subprocess.CalledProcessError(2, args[0], output="", stderr=reason + "\n")

    monkeypatch.setattr(subprocess, "check_output", rejecting_tool)
    command = ["dart-decimate", "check", ".", "--strict"]
    with pytest.raises(
        ValueError, match=r"^app: dart-decimate config failed"
    ) as caught:
        validate_dart_boundaries(command, package, 5)
    assert reason in str(caught.value)
    assert "\n" not in str(caught.value)
    assert "returned non-zero" not in str(caught.value)


def boundary_tool(monkeypatch: pytest.MonkeyPatch, rules: list[dict[str, str]]) -> None:
    def native_config(*_args: object, **_kwargs: object) -> str:
        return json.dumps({"config": {"boundaries": rules}})

    monkeypatch.setattr(subprocess, "check_output", native_config)


def test_a_boundary_rule_with_a_missing_folder_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "lib/feature_a").mkdir(parents=True)
    (tmp_path / "lib/feature_a/page.dart").write_text("void main() {}\n")
    (tmp_path / "lib/notes").mkdir()
    (tmp_path / "lib/notes/plan.md").write_text("no code here\n")
    (tmp_path / ".dart-decimaterc.json").write_text("{}")
    command = ["dart-decimate", "check", ".", "--strict"]
    boundary_tool(monkeypatch, [{"from": "lib/feature", "disallow": "lib"}])
    validate_dart_boundaries(command, tmp_path, 5)
    for prefix in ("lib/features", "ui/pages", "lib/notes"):
        boundary_tool(monkeypatch, [{"from": "lib/feature_a", "disallow": prefix}])
        with pytest.raises(
            ValueError,
            match=rf"{prefix} in .dart-decimaterc.json matches no .dart file",
        ):
            validate_dart_boundaries(command, tmp_path, 5)


def test_a_linter_rule_set_to_false_is_refused_by_name(
    runner: ModuleType, tmp_path: Path
) -> None:
    options = json.loads(json.dumps(DART_TYPING))
    options["linter"]["rules"]["avoid_print"] = False
    path = tmp_path / "analysis_options.yaml"
    path.write_text(yaml.safe_dump(options))
    with pytest.raises(
        ValueError, match=r"analysis_options.yaml: avoid_print is set to false"
    ) as caught:
        runner.validate_typing(tmp_path, "dart", ["lib"])
    assert str(caught.value).endswith("; remove that entry")
    del options["linter"]["rules"]["avoid_print"]
    path.write_text(yaml.safe_dump(options))
    runner.validate_typing(tmp_path, "dart", ["lib"])


NESTED_ROOT: Group = {"path": ".", "language": "dart", "checks": []}


def nested_group(path: str, language: str = "dart", role: str = "types") -> Group:
    check: Gate = {"name": role, "role": role, "command": ["dart", "analyze", "."]}
    return {"path": path, "language": language, "checks": [check]}


def nested_project(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "pubspec.yaml").write_text("name: outer\n")
    for name in ("packages/inner", "test/support"):
        (root / name / "lib").mkdir(parents=True)
        (root / name / "pubspec.yaml").write_text("name: inner\n")
        (root / name / "lib/b.dart").write_text("void b() {}\n")
    git(root, "add", ".")


@pytest.mark.parametrize(
    "pattern,children,accepted",
    [
        ("packages/inner/**", {"packages/inner/**"}, True),
        ("packages/**", {"packages/inner/**"}, False),
        ("test/support/**", {"packages/inner/**"}, False),
        ("packages/inner/**", set(), False),
    ],
)
def test_dart_exclusions_accept_only_nested_packages_with_own_types_check(
    tmp_path: Path, pattern: str, children: set[str], accepted: bool
) -> None:
    nested_project(tmp_path)
    if accepted:
        validate_dart_exclusions(tmp_path, [pattern], children=frozenset(children))
        return
    with pytest.raises(ValueError, match="cannot exclude project files"):
        validate_dart_exclusions(tmp_path, [pattern], children=frozenset(children))


def test_nested_package_exclusions_follow_child_types_checks() -> None:
    groups: list[Group] = [
        NESTED_ROOT,
        nested_group("packages/inner"),
        nested_group("packages/lint", role="lint"),
        {"path": "packages/docs", "checks": []},
        nested_group("packages/web", language="javascript"),
    ]
    assert nested_package_patterns(NESTED_ROOT, groups) == {"packages/inner/**"}
    parent = nested_group("packages/inner")
    below = nested_group("packages/inner/deep")
    assert nested_package_patterns(parent, [parent, below]) == {"deep/**"}
    assert nested_package_patterns(NESTED_ROOT, [NESTED_ROOT]) == frozenset()


def test_dart_setup_excludes_nested_packages_from_root_analysis(
    installer: ModuleType, runner: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: outer\n")
    children = frozenset({"packages/inner/**"})
    package: Group = {"path": ".", "checks": []}
    changes: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, package, changes, children)
    path = tmp_path / "analysis_options.yaml"
    path.write_text(changes["analysis_options.yaml"])
    assert yaml.safe_load(path.read_text())["analyzer"]["exclude"] == [
        "packages/inner/**"
    ]
    runner.validate_typing(tmp_path, "dart", ["lib"], children=children)
    repeated: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, package, repeated, children)
    assert "analysis_options.yaml" not in repeated
    path.unlink()
    alone: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, package, alone)
    assert "exclude" not in yaml.safe_load(alone["analysis_options.yaml"])["analyzer"]


def test_the_runner_passes_nested_package_patterns_to_the_dart_validation(
    installer: ModuleType, runner: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: outer\n")
    inner = nested_group("packages/inner")
    gate: Gate = {"name": "types", "role": "types", "command": ["dart", "analyze", "."]}
    group: Group = {
        "path": ".",
        "language": "dart",
        "sources": ["lib"],
        "checks": [gate],
    }
    changes: dict[str, str] = {}
    installer.configure_dart(
        tmp_path, tmp_path, group, changes, frozenset({"packages/inner/**"})
    )
    (tmp_path / "analysis_options.yaml").write_text(changes["analysis_options.yaml"])
    assert runner.prepare_command(group, gate, 5, [group, inner])


def test_a_parent_only_change_keeps_the_nested_package_exclusion(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gate_config import load_groups

    with (tmp_path / ".git/config").open("a") as settings:
        settings.write("[user]\n\tname = Fixture\n\temail = fixture@example.invalid\n")
    for path in (".", "packages/inner"):
        (tmp_path / path / "lib").mkdir(parents=True, exist_ok=True)
        (tmp_path / path / "lib/a.dart").write_text("void a() {}\n")
        (tmp_path / path / "pubspec.yaml").write_text("name: fixture\n")
    git(tmp_path, "add", ".")
    config = installer.gate_config(tmp_path)
    packages = config["packages"]
    assert [package["path"] for package in packages] == [".", "packages/inner"]
    for package in packages:
        package["depends_on"] = []
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    children = nested_package_patterns(packages[0], packages)
    changes: dict[str, str] = {}
    installer.configure_dart(tmp_path, tmp_path, packages[0], changes, children)
    (tmp_path / "analysis_options.yaml").write_text(changes["analysis_options.yaml"])
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "baseline")
    (tmp_path / "lib/a.dart").write_text("void a() {}\nvoid b() {}\n")
    selected = load_groups(tmp_path, "HEAD", dependents=False)
    assert [
        group["path"]
        for group in selected
        if any(check["role"] == "types" for check in group["checks"])
    ] == ["."]
    prepared: list[list[str]] = []

    def prepare(group: Group, gate: Gate, _timeout: float, *_rest: object) -> bool:
        if gate.get("role") == "types" and group.get("language") == "dart":
            prepared.append(runner.prepare_command(group, gate, 5, selected))
        return False

    monkeypatch.setattr(runner, "run_gate", prepare)
    runner.run_gates(selected, 5, None)
    assert prepared == [["dart", "analyze", "--fatal-infos", "."]]
