"""The full check judges what Dart Decimate prints as its resolved config, so no spelling of a setting can narrow a scan, raise a limit or switch a rule off."""

import json
from pathlib import Path

import pytest
from conftest import git
from decimate_resolved import judge, option_hits
from gate_config import Gate, Group, dart_scan_includes_boundaries
from resolved_settings import validate_resolved
from test_proven_copy_judged_once import SCAN, need_decimate
from test_strict_refusals import project

FILES = {
    "pubspec.yaml": "name: app\nversion: 1.0.0\nenvironment:\n  sdk: ^3.0.0\n",
    "lib/main.dart": "void main() {}\n",
    "lib/src/inner.dart": "int inner() => 1;\n",
}


def repo(
    tmp_path: Path, config: dict[str, object], extra: dict[str, str] | None = None
) -> Path:
    need_decimate()
    files = {**FILES, ".dart-decimaterc.json": json.dumps(config), **(extra or {})}
    return project(tmp_path, files)


def groups(command: list[str] | None = None) -> list[Group]:
    gate: Gate = {**SCAN, "command": command or SCAN["command"]}
    return [{"path": ".", "language": "dart", "sources": ["lib"], "checks": [gate]}]


GOOD: dict[str, object] = {
    "boundaries": [{"from": "lib/main.dart", "disallow": "lib/src"}]
}


def refused(
    config: dict[str, object], reason: str, tmp_path: Path, **extra: str
) -> None:
    root = repo(tmp_path, config, extra)
    with pytest.raises(ValueError, match=rf"HE-NO-SWITCH-OFF[\s\S]*{reason}"):
        validate_resolved(root, groups(), 900)


SWITCHED_OFF = [
    ({"ignorePatterns": ["lib/src/**"]}, r"ignore_patterns: drops lib/src/inner\.dart"),
    ({"ignorePatterns": ["**/*.dart"]}, r"ignore_patterns: drops lib/main\.dart"),
    ({"health": {"maxCyclomatic": 99}}, r"health\.max_cyclomatic is 99"),
    ({"health": {"maxCognitive": 99}}, r"health\.max_cognitive is 99"),
    ({"health": {"maxUnitSize": 500}}, r"health\.max_unit_size is 500"),
    ({"health": {"maxCrap": 31}}, r"health\.max_crap is 31"),
    (
        {
            "health": {
                "thresholdOverrides": [
                    {"files": ["lib/main.dart"], "maxCyclomatic": 80, "reason": "r"}
                ]
            }
        },
        r"threshold_overrides.*max_cyclomatic is 80",
    ),
    ({"dupes": {"minTokens": 500}}, r"dupes\.min_tokens is 500"),
    ({"dupes": {"minLines": 50}}, r"dupes\.min_lines is 50"),
    ({"dupes": {"threshold": 5}}, r"dupes\.threshold is 5"),
    ({"dupes": {"skipLocal": True}}, r"dupes\.skip_local is True"),
    (
        {"ignorePatterns": ["**/repo/lib/src/*.dart"]},
        r"ignore_patterns: drops lib/src/inner\.dart",
    ),
    (
        {"ignorePatterns": ["**/repo?lib/src/*.dart"]},
        r"ignore_patterns lists '\*\*/repo\?lib/src/\*\.dart'",
    ),
    (
        {"ignorePatterns": ["lib/[m]ain.dart"]},
        r"ignore_patterns lists 'lib/\[m\]ain\.dart'",
    ),
    ({"health": {"top": 0}}, r"health\.top is 0"),
    ({"dupes": {"top": 0}}, r"dupes\.top is 0"),
    ({"ignoreDependencies": ["foo"]}, r"ignore_dependencies is \['foo'\]"),
    (
        {"rules": {"dart-decimate/dead-file": "off"}},
        r"rule dart-decimate/dead-file is off",
    ),
    ({"entry": ["lib/**/*.dart"]}, r"entry_points lists 'lib/\*\*/\*.dart'"),
]


@pytest.mark.parametrize(("config", "reason"), SWITCHED_OFF)
def test_a_dart_decimate_config_that_narrows_the_scan_is_refused(
    tmp_path: Path, config: dict[str, object], reason: str
) -> None:
    """HE-NO-SWITCH-OFF: `dart-decimate config` shows the setting after defaults, whatever its spelling."""
    refused({**GOOD, **config}, reason, tmp_path)


def test_a_dart_decimate_config_that_keeps_every_check_passes(tmp_path: Path) -> None:
    config: dict[str, object] = {
        **GOOD,
        "ignorePatterns": [".agents/**"],
        "health": {"maxCrap": 30, "maxCyclomatic": 10},
        "dupes": {"minTokens": 30},
        "rules": {"dart-decimate/missing-suppression-reason": "warn"},
        "entry": ["lib/main.dart"],
    }
    validate_resolved(repo(tmp_path, config), groups(), 900)


def test_generated_output_may_be_ignored_when_the_attributes_name_it(
    tmp_path: Path,
) -> None:
    extra = {
        "lib/gen/a.g.dart": "int a() => 1;\n",
        ".gitattributes": "lib/gen/a.g.dart linguist-generated\n",
    }
    root = repo(tmp_path, {**GOOD, "ignorePatterns": ["lib/gen/**"]}, extra)
    validate_resolved(root, groups(), 900)
    (root / "lib/gen/b.dart").write_text("int b() => 1;\n")
    git(root, "add", "-A")
    with pytest.raises(ValueError, match=r"ignore_patterns: drops lib/gen/b\.dart"):
        validate_resolved(root, groups(), 900)


def test_a_coverage_path_is_refused_whatever_file_it_names(tmp_path: Path) -> None:
    """A stale or partial LCOV file would replace the coverage that the tests write."""
    config = {**GOOD, "health": {"maxCrap": 30, "coveragePath": "cov/lcov.info"}}
    refused(config, r"health\.coverage_path is 'cov/lcov\.info'", tmp_path)


@pytest.mark.parametrize("name", ["dart-decimate.toml", ".dart-decimate.toml"])
def test_a_toml_settings_file_that_git_does_not_track_is_refused(
    tmp_path: Path, name: str
) -> None:
    root = repo(tmp_path, {})
    (root / name).write_text("")
    with pytest.raises(ValueError, match=rf"{name} is not tracked by Git"):
        validate_resolved(root, groups(), 900)


def test_the_root_option_form_of_the_scan_is_judged_too(tmp_path: Path) -> None:
    root = repo(tmp_path, {**GOOD, "health": {"maxCyclomatic": 99}})
    with pytest.raises(ValueError, match=r"health\.max_cyclomatic is 99"):
        validate_resolved(root, groups(["dart-decimate", "check", "--root", "."]), 900)


def test_a_settings_file_that_git_does_not_track_is_refused(tmp_path: Path) -> None:
    root = repo(tmp_path, GOOD)
    git(root, "rm", "-q", "--cached", ".dart-decimaterc.json")
    with pytest.raises(
        ValueError, match=r"\.dart-decimaterc\.json is not tracked by Git"
    ):
        validate_resolved(root, groups(), 900)


def test_a_setting_that_no_table_classes_is_refused_unless_it_is_the_default() -> None:
    defaults: dict[str, object] = {"future": None, "rules": {}}
    hit = judge({"future": 3, "rules": {}}, defaults, lambda _patterns: [])
    assert any("future is 3, not its default None" in line for line in hit)
    assert (
        judge(
            {"future": None, "rules": {}},
            defaults,
            lambda _patterns: [],
        )
        == []
    )


@pytest.mark.parametrize(
    "command",
    [
        ["dart-decimate", "check", "other"],
        ["dart-decimate", "check", "--root", "other"],
        ["dart-decimate", "check", "--root=other", "--strict"],
        ["dart-decimate", "check", ".", "--root", "other"],
        ["dart-decimate", "check", "--max-cyclomatic", "10", "other"],
    ],
)
def test_a_scan_of_another_folder_is_refused(
    tmp_path: Path, command: list[str]
) -> None:
    """The tool reads the settings of the folder it scans, so a scan of another folder judges and reads the wrong ones."""
    root = repo(tmp_path, GOOD, {"other/pubspec.yaml": FILES["pubspec.yaml"]})
    with pytest.raises(ValueError, match=r"scans `other`, not the gate folder"):
        validate_resolved(root, groups(command), 900)


@pytest.mark.parametrize(
    "command",
    [
        ["dart-decimate", "check", "./"],
        ["dart-decimate", "check", "--max-cyclomatic", "10"],
        ["dart-decimate", "check", ".", "--root", "."],
    ],
)
def test_a_scan_of_the_whole_gate_folder_is_judged_in_every_spelling(
    tmp_path: Path, command: list[str]
) -> None:
    root = repo(tmp_path, {**GOOD, "health": {"maxCyclomatic": 99}})
    with pytest.raises(ValueError, match=r"health\.max_cyclomatic is 99"):
        validate_resolved(root, groups(command), 900)


REFUSED_OPTIONS = [
    ["--file", "lib/main.dart"],
    ["--entry", "lib/main.dart"],
    ["--dart-platform", "web"],
    ["--production"],
    ["--no-production"],
    ["--workspace", "app"],
    ["--changed-workspaces", "main"],
    ["--changed-since", "main"],
    ["--compare", "main"],
    ["--baseline", "b.json"],
    ["--save-baseline", "b.json"],
    ["--regression-baseline", "b.json"],
    ["--save-regression-baseline", "b.json"],
    ["--fail-on-regression"],
    ["--tolerance", "5"],
    ["--coverage", "l.info"],
    ["--runtime-coverage", "c.json"],
    ["--max-cyclomatic", "99"],
    ["--max-cognitive", "99"],
    ["--max-unit-size", "99"],
    ["--max-crap", "99"],
    ["--min-score", "1"],
    ["--mode", "weak"],
    ["--min-tokens", "500"],
    ["--min-lines", "50"],
    ["--min-occurrences", "9"],
    ["--top", "0"],
    ["--threshold", "5"],
    ["--format", "human"],
    ["--skip-local"],
    ["--cross-language"],
    ["--ignore-imports"],
    ["--no-ignore-imports"],
    ["--include-entry-exports"],
    ["--unused-files"],
    ["--unused-exports"],
    ["--unused-types"],
    ["--unused-deps"],
    ["--unlisted-deps"],
    ["--private-src-imports"],
    ["--duplicate-exports"],
    ["--unused-enum-members"],
    ["--unused-class-members"],
    ["--unresolved-imports"],
    ["--stale-suppressions"],
    ["--unused-dependency-overrides"],
    ["--misconfigured-dependency-overrides"],
    ["--package-cycles"],
    ["--circular-deps"],
    ["--re-export-cycles"],
    ["--boundary", "a:b"],
    ["--boundary-call", "a:b"],
    ["--policy-pack", "p.json"],
    ["--min-invocations-hot", "1"],
    ["--min-observation-volume", "1"],
    ["--low-traffic-threshold", "0.5"],
    ["--max-cognitive=99"],
    ["--file=lib/main.dart"],
]
INSTALLED_FORMS = [
    ["--threshold", "0", "--strict", "--format", "json"],
    ["--format", "json", "--threshold", "0", "--strict"],
    ["--boundary-violations", "--strict"],
    ["--strict", "--format=json", "--threshold=0"],
    ["--strict", "--config", ".dart-decimaterc.json"],
    ["--root", ".", "--strict"],
]


@pytest.mark.parametrize("extra", REFUSED_OPTIONS, ids=" ".join)
def test_an_option_that_changes_the_scope_or_a_limit_is_refused(
    extra: list[str],
) -> None:
    """HE-NO-SWITCH-OFF: the tool reads these options before the settings file, so only the installed forms may run."""
    hits = option_hits(
        ["dart-decimate", "check", ".", "--strict", *extra], "dead-code-duplicates"
    )
    assert len(hits) == 1
    assert extra[0].split("=")[0] in hits[0]


@pytest.mark.parametrize("extra", INSTALLED_FORMS, ids=" ".join)
def test_the_installed_forms_of_the_scan_pass_the_option_check(
    extra: list[str],
) -> None:
    role = "boundaries" if "--boundary-violations" in extra else "dead-code-duplicates"
    assert option_hits(["dart-decimate", "check", ".", *extra], role) == []
    assert option_hits(["dart-decimate", "check", "./", *extra], role) == []


def test_a_refused_option_fails_the_settings_judgment_of_the_gate(
    tmp_path: Path,
) -> None:
    root = repo(tmp_path, GOOD)
    command = [*SCAN["command"], "--max-cognitive", "99"]
    with pytest.raises(ValueError, match=r"option --max-cognitive"):
        validate_resolved(root, groups(command), 900)


def test_the_boundary_flag_is_refused_on_a_full_scan_gate() -> None:
    """HE-NO-SWITCH-OFF: with a separate boundaries gate, the flag on the full scan drops every other finding."""
    command = [*SCAN["command"], "--boundary-violations"]
    assert len(option_hits(command, "dead-code-duplicates")) == 1


@pytest.mark.parametrize("launcher", [["bun", "x"], ["bunx"]])
def test_a_launcher_does_not_hide_a_refused_option(
    tmp_path: Path, launcher: list[str]
) -> None:
    root = repo(tmp_path, GOOD)
    command = [*launcher, "dart-decimate@0.0.76", *SCAN["command"][1:]]
    command[command.index("--strict")] = "--file=classify.dart"
    with pytest.raises(ValueError, match=r"option --file"):
        validate_resolved(root, groups(command), 900)


def test_a_dot_slash_scan_is_the_combined_gate() -> None:
    command = ["dart-decimate", "check", "./", *SCAN["command"][3:]]
    assert dart_scan_includes_boundaries(
        {
            **SCAN,
            "command": command,
            "report": {"type": "dart-decimate", "stdout": True},
        }
    )
