import subprocess
from pathlib import Path
from types import ModuleType

import yaml
from generated_marks import proven_copies
from test_setup import repository


def test_dart_setup_migrates_nested_plugin_overrides(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
) -> None:
    """Nested analysis_options.yaml files under sources or test must migrate older plugin pins."""
    shared = tmp_path / "shared_test_options.yaml"
    shared.write_text(
        yaml.safe_dump({"plugins": {"flutter_skill_lints": "^0.14.0"}}, sort_keys=False)
    )
    package = tmp_path / "app"
    (package / "lib/sub").mkdir(parents=True)
    (package / "test").mkdir(parents=True)
    (package / "pubspec.yaml").write_text(
        "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    (package / "analysis_options.yaml").write_text(
        yaml.safe_dump({"plugins": {"flutter_skill_lints": "^0.14.0"}}, sort_keys=False)
    )
    (package / "lib/sub/analysis_options.yaml").write_text(
        yaml.safe_dump(
            {
                "include": "../../analysis_options.yaml",
                "plugins": {"flutter_skill_lints": "^0.14.0"},
            },
            sort_keys=False,
        )
    )
    (package / "test/analysis_options.yaml").write_text(
        yaml.safe_dump(
            {
                "include": [
                    "../analysis_options.yaml",
                    "../../shared_test_options.yaml",
                ],
                "plugins": {"flutter_skill_lints": "^0.14.0"},
            },
            sort_keys=False,
        )
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
    assert (
        yaml.safe_load((package / "lib/sub/analysis_options.yaml").read_text())[
            "plugins"
        ]["flutter_skill_lints"]
        == "^0.15.0"
    )
    assert (
        yaml.safe_load((package / "test/analysis_options.yaml").read_text())["plugins"][
            "flutter_skill_lints"
        ]
        == "^0.15.0"
    )
    assert (
        yaml.safe_load(shared.read_text())["plugins"]["flutter_skill_lints"]
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
    shared = tmp_path / "packages/shared"
    (shared / "integration_test").mkdir(parents=True)
    (shared / "lib").mkdir(parents=True)
    (shared / "lib/a.dart").write_text("const a = 1;\n")
    (shared / "pubspec.yaml").write_text("name: shared\nenvironment:\n  sdk: ^3.9.0\n")
    (shared / "analysis_options.yaml").write_text(
        yaml.safe_dump({"plugins": {"flutter_skill_lints": "^0.14.0"}}, sort_keys=False)
    )
    (shared / "integration_test/analysis_options.yaml").write_text(
        yaml.safe_dump(
            {
                "include": [
                    "../analysis_options.yaml",
                    "../../../../shared_extra.yaml",
                ],
                "plugins": {"flutter_skill_lints": "^0.14.0"},
            },
            sort_keys=False,
        )
    )
    (tmp_path / "functions").mkdir(parents=True, exist_ok=True)
    (tmp_path / "functions/shared_extra.yaml").write_text(
        yaml.safe_dump({"plugins": {"flutter_skill_lints": "^0.14.0"}}, sort_keys=False)
    )

    consumer = tmp_path / "functions/app"
    copy_dir = consumer / "vendored/shared"
    (copy_dir / "integration_test").mkdir(parents=True)
    (copy_dir / "lib").mkdir(parents=True)
    (copy_dir / "lib/a.dart").write_text("const a = 1;\n")
    (copy_dir / "pubspec.yaml").write_text(
        "name: shared\nenvironment:\n  sdk: ^3.9.0\n"
    )
    (copy_dir / "analysis_options.yaml").write_text(
        (shared / "analysis_options.yaml").read_text()
    )
    (copy_dir / "integration_test/analysis_options.yaml").write_text(
        (shared / "integration_test/analysis_options.yaml").read_text()
    )
    (consumer / "lib").mkdir(parents=True)
    (consumer / "lib/main.dart").write_text("void main() {}\n")
    (consumer / "pubspec.yaml").write_text(
        "name: app\ndependencies:\n  flutter:\n    sdk: flutter\n"
    )
    (consumer / "analysis_options.yaml").write_text(
        yaml.safe_dump({"plugins": {"flutter_skill_lints": "^0.14.0"}}, sort_keys=False)
    )
    (tmp_path / ".gitattributes").write_text(
        "functions/app/vendored/shared/** linguist-generated\n"
    )

    submodule = consumer / "test/submod"
    submodule.mkdir(parents=True)
    (submodule / ".git").write_text("gitdir: ../../.git/modules/submod\n")
    (submodule / "analysis_options.yaml").write_text(
        yaml.safe_dump(
            {
                "include": "../../analysis_options.yaml",
                "plugins": {"flutter_skill_lints": "^0.14.0"},
            },
            sort_keys=False,
        )
    )
    bad_fixture = consumer / "test/fixtures/bad"
    bad_fixture.mkdir(parents=True)
    (bad_fixture / "analysis_options.yaml").write_text("plugins: [unclosed\n")
    nul_fixture = consumer / "test/fixtures/nul_include"
    nul_fixture.mkdir(parents=True)
    (nul_fixture / "analysis_options.yaml").write_text(
        yaml.safe_dump({"include": "invalid\0path.yaml"}, sort_keys=False)
    )
    loop_fixture = consumer / "test/fixtures/loop"
    loop_fixture.mkdir(parents=True)
    (loop_fixture / "self.yaml").symlink_to("self.yaml")
    (loop_fixture / "analysis_options.yaml").write_text(
        yaml.safe_dump({"include": "self.yaml"}, sort_keys=False)
    )
    standalone_fixture = consumer / "test/fixtures/standalone"
    standalone_fixture.mkdir(parents=True)
    (standalone_fixture / "analysis_options.yaml").write_text(
        yaml.safe_dump({"plugins": {"flutter_skill_lints": "^0.14.0"}}, sort_keys=False)
    )
    (consumer / "test/analysis_options.yaml").write_text(
        yaml.safe_dump(
            {
                "include": [
                    "../analysis_options.yaml",
                    "../vendored/shared/integration_test/analysis_options.yaml",
                ],
                "plugins": {"flutter_skill_lints": "^0.14.0"},
            },
            sort_keys=False,
        )
    )
    subprocess.run(
        ["git", "add", ".gitattributes", "packages", "functions"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-qm", "seed proven copy"],
        cwd=tmp_path,
        check=True,
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
    assert "functions/app/analysis_options.yaml" in changes
    assert "functions/app/test/analysis_options.yaml" in changes
    assert "functions/shared_extra.yaml" in changes
    assert "functions/app/test/submod/analysis_options.yaml" not in changes
    assert "functions/app/test/fixtures/bad/analysis_options.yaml" not in changes
    assert (
        "functions/app/test/fixtures/nul_include/analysis_options.yaml" not in changes
    )
    assert "functions/app/test/fixtures/loop/analysis_options.yaml" not in changes
    assert "functions/app/test/fixtures/standalone/analysis_options.yaml" not in changes
    assert (
        "functions/app/vendored/shared/integration_test/analysis_options.yaml"
        not in changes
    )
