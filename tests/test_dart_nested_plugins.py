import subprocess
from pathlib import Path
from types import ModuleType

import yaml
from generated_marks import proven_copies
from test_setup import repository


def _write_yaml(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _seed_shared_copy(root: Path, shared: Path, copy_dir: Path) -> None:
    for folder in (shared, copy_dir):
        (folder / "lib").mkdir(parents=True, exist_ok=True)
        (folder / "lib/a.dart").write_text("const a = 1;\n")
        (folder / "pubspec.yaml").write_text(
            "name: shared\nenvironment:\n  sdk: ^3.9.0\n"
        )
        _write_yaml(
            folder / "analysis_options.yaml",
            {"plugins": {"flutter_skill_lints": "^0.14.0"}},
        )
        _write_yaml(
            folder / "integration_test/analysis_options.yaml",
            {
                "include": [
                    "../analysis_options.yaml",
                    "../../../../shared_extra.yaml",
                ],
                "plugins": {"flutter_skill_lints": "^0.14.0"},
            },
        )
    _write_yaml(
        root / "functions/shared_extra.yaml",
        {"plugins": {"flutter_skill_lints": "^0.14.0"}},
    )


def _seed_test_fixtures(consumer: Path) -> None:
    submodule = consumer / "test/submod"
    submodule.mkdir(parents=True)
    (submodule / ".git").write_text("gitdir: ../../.git/modules/submod\n")
    _write_yaml(
        submodule / "analysis_options.yaml",
        {
            "include": "../../analysis_options.yaml",
            "plugins": {"flutter_skill_lints": "^0.14.0"},
        },
    )
    bad = consumer / "test/fixtures/bad/analysis_options.yaml"
    bad.parent.mkdir(parents=True)
    bad.write_text("plugins: [unclosed\n")
    _write_yaml(
        consumer / "test/fixtures/nul_include/analysis_options.yaml",
        {"include": "invalid\0path.yaml"},
    )
    loop = consumer / "test/fixtures/loop"
    loop.mkdir(parents=True)
    (loop / "self.yaml").symlink_to("self.yaml")
    _write_yaml(loop / "analysis_options.yaml", {"include": "self.yaml"})
    _write_yaml(
        consumer / "test/fixtures/standalone/analysis_options.yaml",
        {"plugins": {"flutter_skill_lints": "^0.14.0"}},
    )


def test_dart_setup_migrates_nested_plugin_overrides(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    """Nested analysis_options.yaml files under sources or test must migrate older plugin pins."""
    shared = tmp_path / "shared_test_options.yaml"
    _write_yaml(shared, {"plugins": {"flutter_skill_lints": "^0.14.0"}})
    package = tmp_path / "app"
    (package / "lib/sub").mkdir(parents=True)
    (package / "test").mkdir(parents=True)
    (package / "pubspec.yaml").write_text(
        "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    _write_yaml(
        package / "analysis_options.yaml",
        {"plugins": {"flutter_skill_lints": "^0.14.0"}},
    )
    _write_yaml(
        package / "lib/sub/analysis_options.yaml",
        {
            "include": "../../analysis_options.yaml",
            "plugins": {"flutter_skill_lints": "^0.14.0"},
        },
    )
    _write_yaml(
        package / "test/analysis_options.yaml",
        {
            "include": [
                "../analysis_options.yaml",
                "../../shared_test_options.yaml",
            ],
            "plugins": {"flutter_skill_lints": "^0.14.0"},
        },
    )
    changes: dict[str, str] = {}
    installer.configure_dart(
        tmp_path,
        package,
        {"path": "app", "sources": ["lib"], "checks": []},
        changes,
    )
    for name, content in changes.items():
        (tmp_path / name).write_text(content)
    for checked in (
        package / "lib/sub/analysis_options.yaml",
        package / "test/analysis_options.yaml",
        shared,
    ):
        assert (
            yaml.safe_load(checked.read_text())["plugins"]["flutter_skill_lints"]
            == "^0.15.0"
        )
    runner.validate_typing(package, "dart", ["lib"])


def test_dart_setup_skips_submodules_malformed_fixtures_and_proven_copies(
    installer: ModuleType,
    tmp_path: Path,
) -> None:
    """Nested migration must not touch submodules, malformed or standalone fixtures, or proven generated copies."""
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    consumer = tmp_path / "functions/app"
    _seed_shared_copy(
        tmp_path, tmp_path / "packages/shared", consumer / "vendored/shared"
    )
    (consumer / "lib").mkdir(parents=True)
    (consumer / "lib/main.dart").write_text("void main() {}\n")
    (consumer / "pubspec.yaml").write_text(
        "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    _write_yaml(
        consumer / "analysis_options.yaml",
        {"plugins": {"flutter_skill_lints": "^0.14.0"}},
    )
    (tmp_path / ".gitattributes").write_text(
        "functions/app/vendored/shared/** linguist-generated\n"
    )
    _seed_test_fixtures(consumer)
    _write_yaml(
        consumer / "test/analysis_options.yaml",
        {
            "include": [
                "../analysis_options.yaml",
                "../vendored/shared/integration_test/analysis_options.yaml",
            ],
            "plugins": {"flutter_skill_lints": "^0.14.0"},
        },
    )
    subprocess.run(
        ["git", "add", ".gitattributes", "packages", "functions"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-qm", "seed proven copy"], cwd=tmp_path, check=True
    )
    assert proven_copies(tmp_path, consumer) == {
        "functions/app/vendored/shared": "packages/shared"
    }

    changes: dict[str, str] = {}
    installer.configure_dart(
        tmp_path,
        consumer,
        {"path": "functions/app", "sources": ["lib", "vendored"], "checks": []},
        changes,
    )
    for expected in (
        "functions/app/analysis_options.yaml",
        "functions/app/test/analysis_options.yaml",
        "functions/shared_extra.yaml",
    ):
        assert expected in changes
    for skipped in (
        "functions/app/test/submod/analysis_options.yaml",
        "functions/app/test/fixtures/bad/analysis_options.yaml",
        "functions/app/test/fixtures/nul_include/analysis_options.yaml",
        "functions/app/test/fixtures/loop/analysis_options.yaml",
        "functions/app/test/fixtures/standalone/analysis_options.yaml",
        "functions/app/vendored/shared/integration_test/analysis_options.yaml",
    ):
        assert skipped not in changes
