"""Swift that `flutter create` wrote is not checked until the project changes it."""

import shutil
from pathlib import Path
from types import ModuleType

import pytest
import swift_setup
from gate_config import Group, validate_required_checks
from swift_setup import add_swift_groups, swift_projects, unchanged_starters
from test_swift import CODE, app_config, flutter_app, write

IOS_APP = """import Flutter
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
  }
}
"""
OLD_IOS_APP = """import UIKit
import Flutter

@UIApplicationMain
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplicationLaunchOptionsKey: Any]?
  ) -> Bool {
    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }
}
"""
IOS_SCENE = (
    "import Flutter\nimport UIKit\n\nclass SceneDelegate: FlutterSceneDelegate {\n\n}\n"
)
MAC_WINDOW = """import Cocoa
import FlutterMacOS

class MainFlutterWindow: NSWindow {
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    let windowFrame = self.frame
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)

    RegisterGeneratedPlugins(registry: flutterViewController)

    super.awakeFromNib()
  }
}
"""
IOS_TESTS = """import Flutter
import UIKit
import XCTest

class RunnerTests: XCTestCase {

  func testExample() {
    // If you add code to the Runner application, consider adding tests here.
    // See https://developer.apple.com/documentation/xctest for more information about using XCTest.
  }

}
"""
STARTERS = [
    ("AppDelegate.swift", IOS_APP),
    ("AppDelegate.swift", OLD_IOS_APP),
    ("SceneDelegate.swift", IOS_SCENE),
    ("MainFlutterWindow.swift", MAC_WINDOW),
    ("RunnerTests.swift", IOS_TESTS),
    ("AppDelegate.swift", IOS_APP.replace("\n\n", "\n").replace("  ", "\t")),
    ("RunnerTests.swift", IOS_TESTS.replace("    // See", "    // Look at")),
]
EDITED = IOS_APP.replace("    return super", "    print(1)\n    return super")


def starter_app(root: Path, platforms: tuple[str, ...] = ("ios",)) -> None:
    swift = {
        "Runner/AppDelegate.swift": IOS_APP,
        "RunnerTests/RunnerTests.swift": IOS_TESTS,
        "Flutter/GeneratedPluginRegistrant.swift": CODE,
    }
    flutter_app(root, platforms, swift)


@pytest.mark.parametrize(("name", "text"), STARTERS)
def test_starter_text_matches_flutter_templates(
    tmp_path: Path, name: str, text: str
) -> None:
    file = tmp_path / name
    file.write_text(text)
    assert unchanged_starters({file}) == {file}


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("AppDelegate.swift", EDITED),
        ("Renamed.swift", IOS_APP),
        (
            "RunnerTests.swift",
            IOS_TESTS.replace("{\n    //", "{\n    XCTAssertTrue(true)\n    //"),
        ),
        ("SceneDelegate.swift", ""),
    ],
)
def test_edited_starter_text_is_not_a_starter(
    tmp_path: Path, name: str, text: str
) -> None:
    file = tmp_path / name
    file.write_text(text)
    assert unchanged_starters({file}) == set()


def test_generated_plugin_registrant_never_counts(tmp_path: Path) -> None:
    file = tmp_path / "GeneratedPluginRegistrant.swift"
    file.write_text(CODE)
    assert unchanged_starters({file}) == {file}


def test_installed_sdk_templates_count_as_starters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    future = IOS_APP.replace("@main", "@main // next template")
    future = future.replace("import UIKit", "import UIKit\nimport Network")
    file = tmp_path / "AppDelegate.swift"
    file.write_text(future)
    assert unchanged_starters({file}) == set()
    sdk = tmp_path / "sdk"
    write(
        sdk,
        {
            "bin/flutter": "",
            "packages/flutter_tools/templates/app/ios.tmpl/Runner/AppDelegate.swift": future,
        },
    )
    monkeypatch.setattr(shutil, "which", lambda _name: str(sdk / "bin/flutter"))
    cached = swift_setup.installed_templates
    cached.cache_clear()
    try:
        assert unchanged_starters({file}) == {file}
    finally:
        cached.cache_clear()


def test_template_only_folder_has_no_swift_group(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    starter_app(root, ("ios", "macos"))
    assert swift_projects(root) == {}
    config = app_config(installer, root)
    assert [group["path"] for group in config["packages"]] == ["."]
    validate_required_checks(root, config)


@pytest.mark.parametrize(
    "change",
    [
        {"ios/Runner/Native/Channel.swift": CODE},
        {"ios/Runner/AppDelegate.swift": EDITED},
        {"ios/Runner/Renamed.swift": IOS_APP},
    ],
)
def test_project_swift_creates_the_group(
    installer: ModuleType, tmp_path: Path, change: dict[str, str]
) -> None:
    root = tmp_path / "app"
    starter_app(root)
    write(root, change)
    assert swift_projects(root) == {"ios": (["Runner"], ["RunnerTests"], False)}
    assert [g["path"] for g in app_config(installer, root)["packages"]] == [".", "ios"]


def test_a_test_only_edit_creates_no_group(tmp_path: Path) -> None:
    root = tmp_path / "app"
    starter_app(root)
    write(
        root, {"ios/RunnerTests/RunnerTests.swift": IOS_TESTS + "// more\nlet a = 1\n"}
    )
    assert swift_projects(root) == {}


def test_sources_skip_starter_only_folders(tmp_path: Path) -> None:
    root = tmp_path / "app"
    starter_app(root)
    write(root, {"ios/Widget/Live.swift": CODE})
    assert swift_projects(root) == {"ios": (["Widget"], ["RunnerTests"], False)}
    write(root, {"ios/Runner/AppDelegate.swift": EDITED})
    assert swift_projects(root)["ios"].sources == ["Runner", "Widget"]


def test_setup_removes_a_group_for_a_template_only_folder(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    assert [g["path"] for g in config["packages"]] == [".", "ios"]
    (root / "ios/Runner/Box.swift").unlink()
    write(root, {"ios/Runner/AppDelegate.swift": IOS_APP})
    (root / "ios/RunnerTests/RunnerTests.swift").write_text(IOS_TESTS)
    add_swift_groups(root, config)
    assert [g["path"] for g in config["packages"]] == ["."]


def test_group_for_a_template_only_folder_fails(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = app_config(installer, root)
    (root / "ios/Runner/Box.swift").unlink()
    write(root, {"ios/Runner/AppDelegate.swift": IOS_APP})
    with pytest.raises(
        ValueError, match="ios: all of its Swift is Flutter starter code"
    ):
        validate_required_checks(root, config)


def test_unchanged_starters_are_not_production_files(
    runner: ModuleType, tmp_path: Path
) -> None:
    write(
        tmp_path, {"Runner/AppDelegate.swift": IOS_APP, "Runner/Native/Box.swift": CODE}
    )
    group: Group = {
        "path": ".",
        "checks": [],
        "language": "swift",
        "sources": ["Runner"],
    }
    box = (tmp_path / "Runner/Native/Box.swift").resolve()
    assert runner.production_files(tmp_path.resolve(), group) == {box}
    write(tmp_path, {"Runner/AppDelegate.swift": EDITED})
    assert runner.production_files(tmp_path.resolve(), group) == {
        box,
        (tmp_path / "Runner/AppDelegate.swift").resolve(),
    }
