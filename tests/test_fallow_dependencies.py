"""An ignored dependency needs proof that a config or native file uses it; an unmatched-file allowance cannot cover every file."""

import json
from pathlib import Path

import pytest
from gate_config import Group
from resolved_settings import validate_resolved
from test_fallow_resolved import gate, repo

PODFILE = "pod 'CapacitorCamera', :path => '../../node_modules/@capacitor/camera'\n"
PACKAGES = {
    "package.json": json.dumps({"dependencies": {"@capacitor/camera": "1.0.0"}}),
    "src/main.ts": "export {};\n",
}


def groups() -> list[Group]:
    return [{"path": ".", "language": "javascript", "checks": [gate()]}]


def settings(**values: object) -> str:
    return json.dumps(values)


@pytest.mark.parametrize(
    "native",
    [
        ("ios/App/Podfile", PODFILE),
        (
            "android/app/src/main/AndroidManifest.xml",
            "<uses-permission name='@capacitor/camera'/>\n",
        ),
        ("android/app/build.gradle", "implementation project(':@capacitor/camera')\n"),
        (
            "capacitor.config.ts",
            "export default { plugins: { '@capacitor/camera': {} } };\n",
        ),
        ("ios/App/Package.swift", '.package(path: "@capacitor/camera")\n'),
    ],
)
def test_an_ignored_dependency_that_a_native_or_config_file_names_passes(
    tmp_path: Path, native: tuple[str, str]
) -> None:
    """The package is used through a file that Fallow does not read as JavaScript, so the file is the proof."""
    files = {
        **PACKAGES,
        ".fallowrc.json": settings(ignoreDependencies=["@capacitor/camera"]),
        native[0]: native[1],
    }
    validate_resolved(repo(tmp_path, files), groups(), 900)


@pytest.mark.parametrize(
    ("package", "name", "text"),
    [
        (
            "@capacitor/ios",
            "ios/App/CapApp-SPM/Package.swift",
            '.package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", exact: "8.5.2")\n',
        ),
        (
            "@capacitor/android",
            "android/app/build.gradle",
            "implementation project(':capacitor-android')\n",
        ),
    ],
)
def test_a_capacitor_platform_package_is_proved_by_the_native_package_it_stands_for(
    tmp_path: Path, package: str, name: str, text: str
) -> None:
    """The iOS and Android projects depend on the native twin of the package, so that name is the proof."""
    files = {
        "package.json": json.dumps({"dependencies": {package: "1.0.0"}}),
        "src/main.ts": "export {};\n",
        ".fallowrc.json": settings(ignoreDependencies=[package]),
        name: text,
    }
    validate_resolved(repo(tmp_path, files), groups(), 900)


def test_an_ignored_dependency_that_no_file_names_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: with no config or native file that names the package, the entry hides an unused dependency."""
    files = {
        **PACKAGES,
        ".fallowrc.json": settings(ignoreDependencies=["@capacitor/camera"]),
    }
    with pytest.raises(
        ValueError,
        match=r"ignoreDependencies lists '@capacitor/camera'[\s\S]*Podfile[\s\S]*none does",
    ):
        validate_resolved(repo(tmp_path, files), groups(), 900)


def test_an_unmatched_allowance_that_covers_every_file_is_refused(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: `allowUnmatched` of `**` lets every file escape its zone, as no coverage check at all."""
    config = settings(
        boundaries={
            "zones": [{"name": "app", "patterns": ["src/**"]}],
            "rules": [{"from": "app", "allow": []}],
            "coverage": {"requireAllFiles": True, "allowUnmatched": ["**"]},
        }
    )
    files = {"src/main.ts": "export {};\n", ".fallowrc.json": config}
    with pytest.raises(ValueError, match=r"allowUnmatched[\s\S]*every file"):
        validate_resolved(repo(tmp_path, files), groups(), 900)
