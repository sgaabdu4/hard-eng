"""The tests script of the Swift gate, run with fake Xcode and Flutter tools."""

import json
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from test_swift import app_config, flutter_app, swift_group, write

BOOTED = "BBBBBBBB-1111-2222-3333-444444444444"
FIRST = "AAAAAAAA-1111-2222-3333-444444444444"
DEVICES = {
    "booted": f"    iPhone 16 ({FIRST}) (Shutdown)\n    iPhone 15 ({BOOTED}) (Booted)\n",
    "shutdown": f"-- iOS 18.5 --\n    iPhone 16 ({FIRST}) (Shutdown)\n-- iOS 26.0 --\n    iPhone 15 ({BOOTED}) (Shutdown)\n",
    "none": "    iPad (CCCCCCCC-1111-2222-3333-444444444444) (Shutdown)\n",
}
FAKE_TOOLS = {
    "xcrun": 'case "$1 $2" in\n'
    '"simctl list") printf "%s" "$FAKE_DEVICES" ;;\n'
    '"xccov view") case "$5" in\n'
    '  *.xccovreport) echo \'{"report": "exported"}\' ;;\n'
    '  *) [ -z "$FAKE_XCCOV_FAILS" ] || { echo "Failed to load coverage archive" >&2; exit 1; }; echo "{}" ;;\n'
    "  esac ;;\n"
    '"xcresulttool export") mkdir -p "$7" && touch "$7/0_Test_My Mac_CoverageReport" ;;\n'
    '*) echo "{}" ;;\n'
    "esac\n",
    "xcodebuild": 'echo "xcodebuild $*" >> "$FAKE_CALLS"\n',
    "flutter": 'echo "flutter $*" >> "$FAKE_CALLS"\n'
    '[ -z "$FAKE_RESOLVE" ] || [ "$1" != build ] || echo moved >> "$FAKE_RESOLVE"\n',
}


def run_tests_script(
    installer: ModuleType,
    tmp_path: Path,
    platform: str,
    devices: str,
    moved: str,
    xccov_fails: bool = False,
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
        "FAKE_XCCOV_FAILS": "1" if xccov_fails else "",
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
    assert " -parallel-testing-enabled NO " in build
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
        assert "-parallel-testing-enabled" not in calls[-1]


def test_tests_script_reads_exported_coverage_when_xccov_cannot_load_the_bundle(
    installer: ModuleType, tmp_path: Path
) -> None:
    result, _ = run_tests_script(installer, tmp_path, "macos", "", "", True)
    assert result.returncode == 0, result.stderr
    report = tmp_path / "app/macos/coverage/swift-coverage.json"
    assert json.loads(report.read_text()) == {"report": "exported"}
