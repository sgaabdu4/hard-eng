"""The full check judges what Dart Decimate prints as its resolved config, so no spelling of a setting can narrow a scan, raise a limit or switch a rule off."""

import json
import shutil
from pathlib import Path

import pytest
from conftest import git
from decimate_resolved import judge
from gate_config import Gate, Group
from resolved_settings import validate_resolved
from test_strict_refusals import project

SCAN: Gate = {
    "name": "dead-code",
    "role": "dead-code-duplicates",
    "command": [
        "dart-decimate",
        "check",
        ".",
        "--threshold",
        "0",
        "--format",
        "json",
        "--strict",
    ],
    "report": {
        "type": "dart-decimate",
        "path": "coverage/decimate.json",
        "stdout": True,
    },
}
FILES = {
    "pubspec.yaml": "name: app\nversion: 1.0.0\nenvironment:\n  sdk: ^3.0.0\n",
    "lib/main.dart": "void main() {}\n",
    "lib/src/inner.dart": "int inner() => 1;\n",
}


def need_decimate() -> None:
    if shutil.which("dart-decimate") is None:
        from tool_setup import PACKAGES, provision_batch

        provision_batch([PACKAGES["dart-decimate"] + "@latest"], 900)


def repo(
    tmp_path: Path, config: dict[str, object], extra: dict[str, str] | None = None
) -> Path:
    need_decimate()
    files = {**FILES, ".dart-decimaterc.json": json.dumps(config), **(extra or {})}
    return project(tmp_path, files)


def groups() -> list[Group]:
    return [{"path": ".", "language": "dart", "sources": ["lib"], "checks": [SCAN]}]


GOOD = {"boundaries": [{"from": "lib/main.dart", "disallow": "lib/src"}]}


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
    config = {
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


def test_a_coverage_file_that_git_tracks_is_refused(tmp_path: Path) -> None:
    config = {**GOOD, "health": {"maxCrap": 30, "coveragePath": "lcov.info"}}
    refused(
        config,
        r"health\.coverage_path is lcov\.info",
        tmp_path,
        **{"lcov.info": "SF:lib/main.dart\nDA:1,1\nend_of_record\n"},
    )


def test_a_settings_file_that_git_does_not_track_is_refused(tmp_path: Path) -> None:
    root = repo(tmp_path, GOOD)
    git(root, "rm", "-q", "--cached", ".dart-decimaterc.json")
    with pytest.raises(
        ValueError, match=r"\.dart-decimaterc\.json is not tracked by Git"
    ):
        validate_resolved(root, groups(), 900)


def test_a_setting_that_no_table_classes_is_refused_unless_it_is_the_default() -> None:
    defaults: dict[str, object] = {"future": None, "rules": {}}
    hit = judge(
        {"future": 3, "rules": {}}, defaults, lambda _patterns: [], lambda _path: False
    )
    assert any("future is 3, not its default None" in line for line in hit)
    assert (
        judge(
            {"future": None, "rules": {}},
            defaults,
            lambda _patterns: [],
            lambda _path: False,
        )
        == []
    )
