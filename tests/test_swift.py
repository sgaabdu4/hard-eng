"""Built-in Swift checks for the Swift in a Flutter app's ios/ and macos/ projects."""

import json
import os
import re
import subprocess
from pathlib import Path
from types import ModuleType

import coverage_sources
import pytest
import reports
import yaml
from basic_mode import announce
from ci_setup import configure_ci, impact_runner
from comments import validate_comments, validate_suppressions
from conftest import SOURCE, commit, init, load_module
from gate_config import GateConfig, Group, validate_group, validate_required_checks
from swift_setup import add_swift_groups, swift_projects

PUBSPEC = (
    "name: app\nenvironment:\n  sdk: '>=3.0.0 <4.0.0'\n"
    "dependencies:\n  flutter:\n    sdk: flutter\n"
)
CODE = "final class Box {\n  func open() -> Int {\n    return 1\n  }\n}\n"
TESTS = (
    "import XCTest\n\nfinal class RunnerTests: XCTestCase {\n"
    "  func testOpen() {\n    XCTAssertEqual(Box().open(), 1)\n  }\n}\n"
)
PBXPROJ = "// !$*UTF8*$!\n"


def write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def flutter_app(root: Path, platforms: tuple[str, ...] = ("ios",)) -> None:
    init(root)
    write(root, {"pubspec.yaml": PUBSPEC, "pubspec.lock": "packages: {}\n"})
    write(root, {"lib/main.dart": "void main() {}\n"})
    for platform in platforms:
        write(
            root,
            {
                f"{platform}/Runner.xcodeproj/project.pbxproj": PBXPROJ,
                f"{platform}/Runner/Box.swift": CODE,
                f"{platform}/RunnerTests/RunnerTests.swift": TESTS,
                f"{platform}/Flutter/Generated.swift": CODE,
                f"{platform}/Pods/Lib/Lib.swift": CODE,
            },
        )


def app_config(installer: ModuleType, root: Path) -> GateConfig:
    config = installer.gate_config(root)
    add_swift_groups(root, config)
    return config


def swift_group(config: GateConfig, path: str = "ios") -> Group:
    return next(group for group in config["packages"] if group["path"] == path)


def reviewed(group: Group) -> Group:
    group["performance_exception"] = "Native shell code with no measured workload."
    return group


def test_swift_groups_follow_tracked_handwritten_swift(tmp_path: Path) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    write(root, {"ios/ExtensionTarget/Controls.swift": CODE})
    write(root, {"ios/Podfile": "platform :ios, '13.0'\n"})
    write(root, {"macos/Runner.xcodeproj/project.pbxproj": PBXPROJ})
    write(root, {"macos/Flutter/Registrant.swift": CODE})
    write(root, {"ios/Entry.swift": CODE, "ios/EntryTests.swift": TESTS})
    found = swift_projects(root)
    assert found == {
        "ios": (
            ["Entry.swift", "ExtensionTarget", "Runner"],
            ["EntryTests.swift", "RunnerTests"],
            True,
        )
    }
    other = tmp_path / "plain"
    flutter_app(other)
    write(other, {"pubspec.yaml": "name: plain\n"})
    assert swift_projects(other) == {}


def test_nested_flutter_app_names_its_platform_folder(tmp_path: Path) -> None:
    root = tmp_path / "mono"
    init(root)
    write(root, {"apps/mobile/pubspec.yaml": PUBSPEC})
    write(root, {"apps/mobile/ios/Runner.xcodeproj/project.pbxproj": PBXPROJ})
    write(root, {"apps/mobile/ios/Runner/Box.swift": CODE})
    assert list(swift_projects(root)) == ["apps/mobile/ios"]


def test_setup_writes_swift_gates(installer: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    group = swift_group(config)
    assert (group["name"], group["language"], group["sources"]) == (
        "ios",
        "swift",
        ["Runner"],
    )
    assert "performance_exception" not in group
    assert group["depends_on"] == [] and swift_group(config, ".")["depends_on"] == []
    assert group["impact_inputs"] == ["pubspec.yaml", "pubspec.lock"]
    gates = {gate["name"]: gate for gate in group["checks"]}
    assert list(gates) == ["format-lint", "tests", "duplicates", "security"]
    assert gates["format-lint"]["command"] == [
        *["swift", "format", "lint", "--strict", "--recursive", "--parallel"],
        *["Runner", "RunnerTests"],
    ]
    assert gates["tests"]["report"] == {
        "type": "xcode-tests",
        "tests": "coverage/swift-tests.json",
        "coverage": "coverage/swift-coverage.json",
    }
    script = gates["tests"]["command"][2]
    assert gates["tests"]["command"][:2] == ["sh", "-c"]
    assert "xcodebuild test" in script and "-enableCodeCoverage YES" in script
    assert "HARD_ENG_STRICT_Runner=YES" in script
    assert "flutter build macos --config-only --no-pub" in script
    assert 'flutter precache --"$platform"' in script
    assert gates["duplicates"]["command"][1:3] == ["Runner", "--format"]
    assert gates["security"]["command"][3] == "../.agents/skills/he/security"
    assert gates["security"]["command"][-2:] == ["Runner", "RunnerTests"]


def monorepo_app(root: Path, pubspec: str = PUBSPEC) -> None:
    init(root)
    write(root, {"apps/mobile/pubspec.yaml": pubspec})
    write(root, {"apps/mobile/ios/Runner.xcodeproj/project.pbxproj": PBXPROJ})
    write(root, {"apps/mobile/ios/Runner/Box.swift": CODE})


def test_swift_group_in_a_monorepo_reads_only_its_apps_pubspec_files(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "mono"
    monorepo_app(root)
    config = installer.gate_config(root)
    swift_group(config, "apps/mobile")["depends_on"] = ["packages/core"]
    add_swift_groups(root, config)
    group = swift_group(config, "apps/mobile/ios")
    assert group["depends_on"] == []
    assert group["impact_inputs"] == [
        "apps/mobile/pubspec.yaml",
        "apps/mobile/pubspec.lock",
    ]


def test_swift_group_watches_the_native_folders_of_local_plugins(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "mono"
    monorepo_app(
        root, PUBSPEC + "  local_plugin:\n    path: ../../plugins/local_plugin\n"
    )
    write(root, {"plugins/local_plugin/pubspec.yaml": "name: local_plugin\n"})
    config = installer.gate_config(root)
    add_swift_groups(root, config)
    assert swift_group(config, "apps/mobile/ios")["impact_inputs"][2:] == [
        "plugins/local_plugin/ios",
        "plugins/local_plugin/darwin",
    ]


def test_swift_group_in_a_dart_workspace_takes_its_roles_from_the_workspace(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "mono"
    monorepo_app(root)
    write(root, {"pubspec.yaml": "name: mono\nworkspace:\n  - apps/mobile\n"})
    config = installer.gate_config(root)
    add_swift_groups(root, config)
    assert swift_group(config, "apps/mobile/ios")["impact_inputs"][2:] == [
        "pubspec.yaml",
        "pubspec.lock",
    ]
    app = swift_group(config, "apps/mobile")
    assert not {"lockfiles", "vulnerabilities"} & {g.get("role") for g in app["checks"]}
    for group in config["packages"]:
        group["depends_on"] = []
    validate_required_checks(root, config)


def test_plugin_added_after_setup_must_be_watched(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    validate_required_checks(root, config)
    write(root, {"pubspec.yaml": PUBSPEC + "  local_plugin:\n    path: plugin\n"})
    with pytest.raises(
        ValueError, match="ios: impact_inputs must list plugin/darwin, plugin/ios"
    ):
        validate_required_checks(root, config)
    group = swift_group(config)
    group["impact_inputs"] += ["plugin/ios", "plugin/darwin"]
    validate_required_checks(root, config)


def test_setup_adds_the_pods_gate_only_with_a_podfile(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    write(root, {"ios/Podfile": "platform :ios, '13.0'\n"})
    first = swift_group(app_config(installer, root))["checks"][0]
    assert first["name"] == "pods-locked" and first["role"] == "lockfiles"
    assert first["command"][:2] == ["sh", "-c"]
    assert first["command"][2].endswith("&& pod install --deployment")
    assert "flutter precache" in first["command"][2]


def test_setup_keeps_a_reviewed_swift_group(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    group = reviewed(swift_group(config))
    group["depends_on"] = []
    group["checks"][0]["command"].append("--configuration")
    before = json.dumps(config)
    add_swift_groups(root, config)
    assert json.dumps(config) == before


def test_missing_swift_group_fails(installer: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    validate_required_checks(root, config)
    config["packages"] = [
        group for group in config["packages"] if group["path"] != "ios"
    ]
    with pytest.raises(
        ValueError, match="Swift code is missing from gate configuration: ios"
    ):
        validate_required_checks(root, config)


@pytest.mark.parametrize("role", ["format-lint", "tests", "duplicates"])
def test_swift_group_needs_its_roles(
    installer: ModuleType, tmp_path: Path, role: str
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    group = reviewed(swift_group(config))
    validate_group(root, group, set())
    group["checks"] = [gate for gate in group["checks"] if gate["role"] != role]
    with pytest.raises(ValueError, match=f"missing mandatory checks: {role}"):
        validate_group(root, group, set())


def test_swift_group_needs_a_security_scan(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    group = swift_group(config)
    group["checks"] = [gate for gate in group["checks"] if gate["role"] != "security"]
    with pytest.raises(ValueError, match="ios: missing mandatory checks: security"):
        validate_required_checks(root, config)


def test_podfile_added_after_setup_needs_the_pods_gate(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    write(root, {"ios/Podfile": "platform :ios, '13.0'\n"})
    with pytest.raises(ValueError, match="ios: a Podfile needs the pods-locked gate"):
        validate_required_checks(root, config)
    config["packages"] = [
        group for group in config["packages"] if group["path"] != "ios"
    ]
    add_swift_groups(root, config)
    validate_required_checks(root, config)


@pytest.mark.parametrize("language", [None, "dart"])
def test_swift_group_must_declare_swift(
    installer: ModuleType, tmp_path: Path, language: str | None
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    group = swift_group(config)
    group.pop("language")
    if language:
        group["language"] = language
    with pytest.raises(ValueError, match="ios: the group holding Swift code must"):
        validate_required_checks(root, config)


def test_swift_folder_added_after_setup_must_be_scanned(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    write(root, {"ios/Notifications/Service.swift": CODE})
    with pytest.raises(ValueError, match="ios: Swift folders Notifications"):
        validate_required_checks(root, config)
    group = swift_group(config)
    group["sources"].append("Notifications")
    for gate in group["checks"]:
        if gate["role"] in {"format-lint", "duplicates", "security"}:
            gate["command"].append("Notifications")
    validate_required_checks(root, config)


def test_swift_group_needs_a_performance_review(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    group = swift_group(app_config(installer, root))
    with pytest.raises(ValueError, match="performance_exception"):
        validate_group(root, group, set())


def test_swift_group_takes_services_from_its_flutter_parent_only(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    validate_required_checks(root, config)
    config["packages"].append({**swift_group(config), "path": "lib"})
    with pytest.raises(ValueError, match="lib: missing mandatory checks: lockfiles"):
        validate_required_checks(root, config)


def write_report(path: Path, report: dict[str, object]) -> Path:
    path.write_text(json.dumps(report))
    return path


@pytest.mark.parametrize(
    ("changes", "passed"),
    [
        ({}, 3),
        ({"passedTests": 0}, 0),
        ({"result": "Failed"}, None),
        ({"failedTests": 1}, None),
        ({"result": None}, None),
    ],
)
def test_xcode_tests_report_must_pass(
    tmp_path: Path, changes: dict[str, object], passed: int | None
) -> None:
    summary = {"result": "Passed", "passedTests": 3, "failedTests": 0} | changes
    path = write_report(tmp_path / "tests.json", summary)
    if passed is None:
        with pytest.raises(ValueError, match="successful completed run"):
            reports.completed_tests(path, "xcode-tests")
    else:
        assert reports.completed_tests(path, "xcode-tests") == passed


def xccov(path: Path, targets: dict[str, dict[str, tuple[int, int]]]) -> Path:
    return write_report(
        path,
        {
            "targets": [
                {
                    "name": name,
                    "files": [
                        {"path": file, "coveredLines": hit, "executableLines": total}
                        for file, (hit, total) in files.items()
                    ],
                }
                for name, files in targets.items()
            ]
        },
    )


def test_xccov_coverage_keeps_the_higher_count_per_file(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    first, second = str(root / "Runner/A.swift"), str(root / "Runner/B.swift")
    path = xccov(
        root / "c.json",
        {"app": {first: (1, 4), second: (2, 2)}, "tests": {first: (3, 4)}},
    )
    expected = {root / "Runner/A.swift", root / "Runner/B.swift"}
    assert reports.line_coverage(path, "xcode-tests", root, expected) == (5, 6)


def test_xccov_coverage_fails_for_a_production_file_missing_from_the_report(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()
    path = xccov(root / "c.json", {"app": {str(root / "Runner/A.swift"): (1, 1)}})
    (root / "Runner").mkdir()
    (root / "Runner/B.swift").write_text(CODE)
    expected = {root / "Runner/A.swift", root / "Runner/B.swift"}
    with pytest.raises(ValueError, match=r"omits production files: Runner/B.swift"):
        reports.line_coverage(path, "xcode-tests", root, expected)


@pytest.mark.parametrize(
    ("dump", "erased"),
    [
        ('(source_file\n  (class_decl "Empty"))', True),
        (
            '(source_file\n  (enum_decl "E"\n    (raw_value_expr=string_literal_expr)))',
            True,
        ),
        ('(source_file\n  (func_decl "f()"\n    (brace_stmt)))', False),
        (
            "(source_file\n  (pattern_entry\n    (original_init=integer_literal_expr)))",
            False,
        ),
        ("(source_file\n  (closure_expr))", False),
        (None, False),
    ],
)
def test_swift_file_without_executable_code_may_be_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dump: str | None,
    erased: bool,
) -> None:
    file = tmp_path / "Empty.swift"
    file.write_text("final class Empty {}\n")

    def parse(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert command[:4] == ["swiftc", "-frontend", "-dump-parse", str(file)]
        return subprocess.CompletedProcess(command, int(dump is None), dump or "", "")

    monkeypatch.setattr(coverage_sources.subprocess, "run", parse)
    assert coverage_sources.erased_swift({file}) == ({file} if erased else set())


def test_conditional_swift_code_is_never_exempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / "Platform.swift"
    file.write_text("#if os(iOS)\nfunc open() { print(1) }\n#endif\n")

    def parse(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, '(source_file "p")', "")

    monkeypatch.setattr(coverage_sources.subprocess, "run", parse)
    assert coverage_sources.erased_swift({file}) == set()


def test_coverage_accepts_a_missing_file_with_no_executable_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve()
    (root / "Runner").mkdir()
    (root / "Runner/Empty.swift").write_text("final class Empty {}\n")
    path = xccov(root / "c.json", {"app": {str(root / "Runner/A.swift"): (2, 2)}})

    def erased(files: set[Path]) -> set[Path]:
        return files - {root / "Runner/A.swift"}

    monkeypatch.setattr(reports, "erased_swift", erased)
    expected = {root / "Runner/A.swift", root / "Runner/Empty.swift"}
    assert reports.line_coverage(path, "xcode-tests", root, expected) == (2, 2)


@pytest.mark.parametrize(
    "flag", ["-only-testing:RunnerTests/A", "-skip-testing:RunnerTests/A", "-testPlan"]
)
def test_swift_test_filters_rejected(
    runner: ModuleType, tmp_path: Path, flag: str
) -> None:
    script = f"set -e; xcodebuild test -scheme Runner {flag} -destination x"
    runner.reject_test_filters(
        ["sh", "-c", script.replace(flag, "")], tmp_path, "swift"
    )
    with pytest.raises(ValueError, match="Focused test selection"):
        runner.reject_test_filters(["sh", "-c", script], tmp_path, "swift")


def test_swift_production_files_exclude_tests(
    runner: ModuleType, tmp_path: Path
) -> None:
    write(tmp_path, {"Runner/Box.swift": CODE, "Runner/BoxTests.swift": TESTS})
    group: Group = {
        "path": ".",
        "checks": [],
        "language": "swift",
        "sources": ["Runner"],
    }
    assert runner.production_files(tmp_path.resolve(), group) == {
        (tmp_path / "Runner/Box.swift").resolve()
    }


def selected_groups(*languages: str) -> list[Group]:
    return [
        {"path": language, "language": language, "checks": []} for language in languages
    ]


def test_impact_runner_is_macos_only_for_swift() -> None:
    assert impact_runner(selected_groups("dart", "python")) == "ubuntu-latest"
    assert impact_runner(selected_groups("dart", "swift")) == "macos-latest"


@pytest.mark.parametrize(
    ("changed", "runner_name"),
    [("ios/Runner/Box.swift", "macos-latest"), ("lib/main.dart", "ubuntu-latest")],
)
def test_impact_prints_the_runner(
    installer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    changed: str,
    runner_name: str,
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    for group in config["packages"]:
        group["depends_on"] = []
        if group["path"] == "ios":
            reviewed(group)
    (root / "hard-eng.gates.json").write_text(json.dumps(config))
    commit(root, "configure")
    write(root, {changed: CODE + "\n"})
    module = load_module("swift_impact", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = root
    assert module.impact("HEAD") == 0
    assert f"runner={runner_name}\n" in capsys.readouterr().out


def generated_workflow(root: Path, config: GateConfig) -> str:
    config["shipping"] = {
        "base": "main",
        "checks": ["hard-eng"],
        "ui_paths": [],
        "ci_seconds": 1200,
        "pre_push_seconds": 600,
        "delivery": [],
    }
    (root / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, config, changes)
    return changes[".github/workflows/hard-eng.yml"]


def test_swift_workflow_selects_runner(installer: ModuleType, tmp_path: Path) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    workflow = yaml.safe_load(generated_workflow(root, app_config(installer, root)))
    jobs = workflow["jobs"]
    assert list(jobs) == ["impact", "hard-eng"]
    assert jobs["impact"]["runs-on"] == "ubuntu-latest"
    assert jobs["impact"]["outputs"] == {"runner": "${{ steps.impact.outputs.runner }}"}
    check = jobs["hard-eng"]
    assert check["name"] == "hard-eng" and check["needs"] == "impact"
    assert check["if"] == "${{ !cancelled() }}"
    assert check["runs-on"] == "${{ needs.impact.outputs.runner || 'macos-latest' }}"
    assert check["timeout-minutes"] == 20 and jobs["impact"]["timeout-minutes"] == 5


def test_workflow_without_swift_keeps_its_jobs(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = installer.gate_config(root)
    workflow = generated_workflow(root, config)
    assert list(yaml.safe_load(workflow)["jobs"]) == ["hard-eng"]
    assert ",," not in workflow
    assert ",," not in (SOURCE / ".github/workflows/hard-eng.yml").read_text()


def test_existing_workflow_gains_the_runner_job_once(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    plain = generated_workflow(root, installer.gate_config(root))
    path = root / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    path.write_text(plain)
    config = app_config(installer, root)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, config, changes)
    assert list(yaml.safe_load(changes[".github/workflows/hard-eng.yml"])["jobs"]) == [
        "impact",
        "hard-eng",
    ]
    path.write_text(changes[".github/workflows/hard-eng.yml"])
    changes.clear()
    configure_ci(root, SOURCE, config, changes)
    assert changes == {}


def test_customised_workflow_is_left_with_a_note(
    installer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    plain = generated_workflow(root, installer.gate_config(root))
    path = root / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    custom = plain.replace("runs-on: ubuntu-latest", "runs-on: [self-hosted, linux]")
    path.write_text(custom)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, app_config(installer, root), changes)
    assert changes == {}
    assert "runner" in capsys.readouterr().err


LEGACY_LAUNCHER = '--package="@jdxcode/mise-linux-${RUNNER_ARCH,,}@latest"'


def test_launcher_migration(tmp_path: Path) -> None:
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    assert '--package="$MISE_PACKAGE"' in template
    echo = next(line for line in template.splitlines() if "MISE_PACKAGE=" in line)
    old = template.replace(echo + "\n", "").replace(
        '"$MISE_PACKAGE"', LEGACY_LAUNCHER[10:]
    )
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    path.write_text(old)
    assert LEGACY_LAUNCHER in old
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes == {".github/workflows/hard-eng.yml": template}
    path.write_text(template)
    changes.clear()
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes == {}


def commit_swift(root: Path, name: str, before: str, after: str) -> Path:
    init(root)
    write(root, {"README.md": "fixture\n"})
    if before:
        write(root, {name: before})
    commit(root, "baseline")
    write(root, {name: after})
    return root


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("ios/Runner/Box.swift", "// swift-format-ignore: AlwaysUseLowerCamelCase"),
        ("ios/RunnerTests/RunnerTests.swift", 'try XCTSkip("later")'),
        ("ios/RunnerTests/RunnerTests.swift", '@Test(.disabled("later")) func a() {}'),
        (
            "ios/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme",
            "<SkippedTests>",
        ),
        (
            "ios/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme",
            "<SelectedTests>",
        ),
        (
            "ios/Runner.xcodeproj/xcshareddata/xcschemes/Runner.xcscheme",
            'skipped = "YES"',
        ),
        ("ios/Runner.xctestplan", '"skippedTests" : ['),
    ],
)
def test_swift_switch_offs_fail(tmp_path: Path, name: str, line: str) -> None:
    root = commit_swift(tmp_path / "repo", name, "", "let a = 1\n" + line + "\n")
    with pytest.raises(ValueError, match="must not switch a check off") as error:
        validate_suppressions(root, "HEAD")
    assert f"{name}:2 adds" in str(error.value)


@pytest.mark.parametrize(
    ("text", "flagged"),
    [
        ("Button(action).disabled(busy)\n", False),
        ("Button(action)\n  .disabled(\n    first && second\n  )\n", False),
        ("@Test(.disabled())\nfunc a() {}\n", True),
        (
            '@Test(\n  .tags(.slow),\n  .disabled(\n    "reason"\n  )\n)\nfunc a() {}\n',
            True,
        ),
        ("@Suite(.disabled(if: ready))\nstruct A {}\n", True),
        ('@Test("closes )", .disabled("later"))\nfunc a() {}\n', True),
        ('@Test("opens (")\nfunc a() {}\nButton(a).disabled(busy)\n', False),
        ('@Test(".disabled(true) blocks")\nfunc a() {}\n', False),
    ],
)
def test_only_swift_testing_disabled_traits_are_switch_offs(
    tmp_path: Path, text: str, flagged: bool
) -> None:
    name = "ios/Runner/Box.swift"
    root = commit_swift(tmp_path / "repo", name, "", text)
    if flagged:
        with pytest.raises(ValueError, match="must not switch a check off"):
            validate_suppressions(root, "HEAD")
    else:
        validate_suppressions(root, "HEAD")


def test_deleting_a_swift_file_does_not_break_the_switch_off_rule(
    tmp_path: Path,
) -> None:
    name = "ios/Runner/Box.swift"
    root = commit_swift(tmp_path / "repo", name, CODE, CODE)
    (root / name).unlink()
    validate_suppressions(root, "HEAD")


def test_swift_assertion_loss_fails(tmp_path: Path) -> None:
    name = "ios/RunnerTests/RunnerTests.swift"
    root = commit_swift(
        tmp_path / "repo",
        name,
        TESTS,
        TESTS.replace("XCTAssertEqual(Box().open(), 1)", "_ = Box().open()"),
    )
    with pytest.raises(ValueError, match="tests lose 1 assertion lines net"):
        validate_suppressions(root, "HEAD")
    replaced = TESTS.replace(
        "XCTAssertEqual(Box().open(), 1)", "#expect(Box().open() == 1)"
    )
    write(root, {name: replaced})
    validate_suppressions(root, "HEAD")


def test_swift_comment_blocks(tmp_path: Path) -> None:
    name = "ios/Runner/Box.swift"
    root = commit_swift(tmp_path / "repo", name, "", "/// Opens.\n/// Twice.\n" + CODE)
    with pytest.raises(ValueError, match="Code comments are none by default"):
        validate_comments(root, "HEAD")
    write(root, {name: "// MARK: - Open\n" + CODE})
    validate_comments(root, "HEAD")


def test_swift_security_rules(tmp_path: Path) -> None:
    rules = SOURCE / ".agents/skills/he/security/swift.yaml"
    fixtures = sorted((SOURCE / "tests/semgrep").iterdir())
    report = tmp_path / "semgrep.json"
    subprocess.run(
        ["uvx", "semgrep@latest", "scan", "--config", str(rules), "--metrics=off"]
        + ["--json", "--output", str(report), *map(str, fixtures)],
        check=True,
        capture_output=True,
        timeout=600,
    )
    found = json.loads(report.read_text())
    expected = {
        (fixture.resolve(), match[1], number + 1)
        for fixture in fixtures
        for number, line in enumerate(fixture.read_text().splitlines(), 1)
        if (match := re.search(r"ruleid: (\S+)", line))
    }
    actual = {
        (Path(result["path"]).resolve(), result["check_id"].rsplit(".", 1)[-1])
        + (result["start"]["line"],)
        for result in found["results"]
    }
    assert found["errors"] == []
    assert actual == expected
    assert {rule for _, rule, _ in actual} == {
        rule["id"] for rule in yaml.safe_load(rules.read_text())["rules"]
    }


@pytest.mark.parametrize(("language", "valid"), [("swift", True), ("go", False)])
def test_duplicates_report_covers_swift(
    tmp_path: Path, language: str, valid: bool
) -> None:
    counts = {"clones": 0, "duplicatedLines": 0, "duplicatedTokens": 0}
    counts |= {"newClones": 0, "newDuplicatedLines": 0, "percentage": 0}
    counts |= {"percentageTokens": 0, "sources": 1, "lines": 21, "tokens": 92}
    statistics = {"formats": {language: counts}, "total": counts}
    path = write_report(
        tmp_path / "jscpd.json", {"duplicates": [], "statistics": statistics}
    )
    if valid:
        reports.validate_jscpd(path)
    else:
        with pytest.raises(ValueError, match="requires Python or Swift"):
            reports.validate_jscpd(path)


@pytest.mark.parametrize("package", [True, False])
def test_swiftpm_packages_keep_a_gap_line(
    installer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    package: bool,
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    if package:
        write(root, {"packages/native/Package.swift": "// swift-tools-version: 5.9\n"})
    announce(root, app_config(installer, root))
    output = capsys.readouterr().out
    assert ("Gap: No built-in checks for SwiftPM packages" in output) is package


BOOTED = "BBBBBBBB-1111-2222-3333-444444444444"
FIRST = "AAAAAAAA-1111-2222-3333-444444444444"
DEVICES = {
    "booted": f"    iPhone 16 ({FIRST}) (Shutdown)\n    iPhone 15 ({BOOTED}) (Booted)\n",
    "shutdown": f"-- iOS 18.5 --\n    iPhone 16 ({FIRST}) (Shutdown)\n-- iOS 26.0 --\n    iPhone 15 ({BOOTED}) (Shutdown)\n",
    "none": "    iPad (CCCCCCCC-1111-2222-3333-444444444444) (Shutdown)\n",
}
FAKE_TOOLS = {
    "xcrun": 'if [ "$1" = simctl ]; then printf "%s" "$FAKE_DEVICES"; else echo "{}"; fi\n',
    "xcodebuild": 'echo "xcodebuild $*" >> "$FAKE_CALLS"\n',
    "flutter": 'echo "flutter $*" >> "$FAKE_CALLS"\n'
    '[ -z "$FAKE_RESOLVE" ] || [ "$1" != build ] || echo moved >> "$FAKE_RESOLVE"\n',
}


def run_tests_script(
    installer: ModuleType, tmp_path: Path, platform: str, devices: str, moved: str
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    root = tmp_path / "app"
    flutter_app(root, (platform,))
    resolved = "Runner.xcworkspace/swiftpm/Package.resolved"
    write(root, {f"{platform}/{resolved}": "{}\n"})
    script = swift_group(app_config(installer, root), platform)["checks"][1]["command"]
    tools = tmp_path / "bin"
    for name, body in FAKE_TOOLS.items():
        write(tools, {name: "#!/bin/sh\n" + body})
        (tools / name).chmod(0o755)
    calls = tmp_path / "calls.log"
    calls.touch()
    environment = {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "FAKE_DEVICES": devices,
        "FAKE_CALLS": str(calls),
        "FAKE_RESOLVE": str(root / platform / moved) if moved else "",
    }
    result = subprocess.run(
        script,
        check=False,
        cwd=root / platform,
        env=environment,
        capture_output=True,
        text=True,
    )
    return result, calls.read_text().splitlines()


@pytest.mark.parametrize(
    ("devices", "destination"),
    [("booted", BOOTED), ("shutdown", BOOTED)],
)
def test_ios_tests_script_picks_a_simulator_by_id(
    installer: ModuleType, tmp_path: Path, devices: str, destination: str
) -> None:
    result, calls = run_tests_script(installer, tmp_path, "ios", DEVICES[devices], "")
    assert result.returncode == 0, result.stderr
    build = next(call for call in calls if call.startswith("xcodebuild"))
    assert f"-destination id={destination} " in build
    assert "-onlyUsePackageVersionsFromResolvedFile" in build
    assert "SWIFT_TREAT_WARNINGS_AS_ERRORS=$(HARD_ENG_STRICT_$(PROJECT_NAME))" in build
    assert build.endswith("HARD_ENG_STRICT_Runner=YES")
    assert calls[0] == "flutter precache --ios"


def test_ios_tests_script_needs_an_iphone_simulator(
    installer: ModuleType, tmp_path: Path
) -> None:
    result, calls = run_tests_script(installer, tmp_path, "ios", DEVICES["none"], "")
    assert result.returncode == 1
    assert "No iPhone simulator is available" in result.stderr
    assert not any(call.startswith("xcodebuild") for call in calls)


@pytest.mark.parametrize(
    "moved", ["", "Runner.xcworkspace/swiftpm/Package.resolved", "Runner/Box.swift"]
)
def test_macos_tests_script_keeps_the_project_files_unchanged(
    installer: ModuleType, tmp_path: Path, moved: str
) -> None:
    result, calls = run_tests_script(installer, tmp_path, "macos", "", moved)
    assert calls[:2] == [
        "flutter precache --macos",
        "flutter build macos --config-only --no-pub",
    ]
    if moved:
        assert result.returncode == 1
        assert "Flutter changed files in macos" in result.stderr
        assert len(calls) == 2
    else:
        assert result.returncode == 0, result.stderr
        assert "-destination platform=macOS " in calls[-1]


def test_xccov_coverage_keeps_the_larger_denominator_per_file(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    file = str(root / "Runner/A.swift")
    path = xccov(root / "c.json", {"app": {file: (7, 100)}, "tests": {file: (8, 10)}})
    expected = {root / "Runner/A.swift"}
    assert reports.line_coverage(path, "xcode-tests", root, expected) == (7, 100)
