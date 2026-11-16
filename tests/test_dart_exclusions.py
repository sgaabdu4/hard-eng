"""Dart analysis excludes: only generated, native, nested-package and localization output may leave strict analysis."""

import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from conftest import git
from dart_boundaries import validate_dart_exclusions, validate_dart_includes


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


def test_an_included_parent_exclude_is_judged_where_it_applies(tmp_path: Path) -> None:
    """The analyzer applies a parent file's exclude from the including folder: one that matches nothing there passes; one that hides a file fails and names the parent file."""
    parent = tmp_path / "analysis_options.yaml"
    parent.write_text("analyzer:\n  exclude:\n    - example/**\n")
    example = tmp_path / "example"
    (example / "lib").mkdir(parents=True)
    (example / "pubspec.yaml").write_text("name: ex\n")
    (example / "lib/a.dart").write_text("void a() {}\n")
    child = example / "analysis_options.yaml"
    child.write_text("include: ../analysis_options.yaml\n")
    validate_dart_includes(child, example)
    parent.write_text("analyzer:\n  exclude:\n    - example/**\n    - lib/a.dart\n")
    with pytest.raises(ValueError) as refused:
        validate_dart_includes(child, example)
    assert f"remove 'lib/a.dart' from exclude in {parent.resolve()}" in str(
        refused.value
    )
    child.write_text("analyzer:\n  exclude:\n    - example/**\n")
    with pytest.raises(ValueError, match="remove 'example/\\*\\*' from exclude"):
        validate_dart_includes(child, example)


@pytest.mark.parametrize("pattern", ["{lib,bin}/**", "lib/{a,b}.dart", "li**/a.dart"])
def test_an_inherited_pattern_with_braces_or_a_partial_double_star_is_refused(
    tmp_path: Path, pattern: str
) -> None:
    """Python glob expands neither braces nor a partial `**`, so such an inherited pattern may hide a child file and fails."""
    parent = tmp_path / "analysis_options.yaml"
    parent.write_text(f'analyzer:\n  exclude:\n    - "{pattern}"\n')
    package = tmp_path / "pkg"
    (package / "lib").mkdir(parents=True)
    (package / "pubspec.yaml").write_text("name: pkg\n")
    (package / "lib/a.dart").write_text("void a() {}\n")
    child = package / "analysis_options.yaml"
    child.write_text("include: ../analysis_options.yaml\n")
    with pytest.raises(ValueError, match="cannot exclude project files"):
        validate_dart_includes(child, package)


def test_an_inherited_pattern_is_judged_from_the_folder_of_the_analyzed_options_file(
    tmp_path: Path,
) -> None:
    """A nested test options file that includes a file above the package applies its pattern from test/, not from the package root."""
    (tmp_path / "analysis_options.yaml").write_text(
        'analyzer:\n  exclude:\n    - "*_test.dart"\n'
    )
    package = tmp_path / "pkg"
    (package / "test").mkdir(parents=True)
    (package / "pubspec.yaml").write_text("name: pkg\n")
    (package / "test/a_test.dart").write_text("void main() {}\n")
    nested = package / "test/analysis_options.yaml"
    nested.write_text("include: ../../analysis_options.yaml\n")
    with pytest.raises(ValueError, match="remove '\\*_test.dart' from exclude"):
        validate_dart_includes(nested, package)
