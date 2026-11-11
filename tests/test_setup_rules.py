"""Setup rules: what setup adds to an installed gates file and what it refuses."""

import json
from pathlib import Path

import gate_config
import pytest
from conftest import SOURCE, commit, configure, gate, git, init
from gate_config import GateConfig, validate_file_sizes
from project_setup import (
    adapt_packages,
    validate_dart_exclusions,
)


@pytest.mark.parametrize(
    ("language", "manifest", "text", "lock"),
    [
        ("dart", "pubspec.yaml", "name: app\n", "pubspec.lock"),
        ("python", "pyproject.toml", '[project]\nname = "app"\n', "uv.lock"),
        ("javascript", "package.json", '{"name": "app"}\n', "bun.lock"),
    ],
)
def test_an_ignored_lock_file_is_refused(
    tmp_path: Path, language: str, manifest: str, text: str, lock: str
) -> None:
    root = tmp_path / "project"
    init(root)
    package = root / "app"
    package.mkdir()
    (package / manifest).write_text(text)
    (package / lock).write_text("# lock\n")
    (root / ".gitignore").write_text(f"{lock}\n")
    commit(root, "start")
    config: GateConfig = {
        "shared": [],
        "packages": [
            {"path": "app", "language": language, "sources": ["lib"], "checks": []}
        ],
    }
    with pytest.raises(ValueError, match=rf"app/{lock} is ignored by Git") as refused:
        adapt_packages(root, config)
    assert ".gitignore" in str(refused.value)
    (root / ".gitignore").write_text("")
    commit(root, "track the lock file")
    adapt_packages(root, config)


def test_the_exclusion_refusal_names_the_file_and_the_entry(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot exclude project files") as refused:
        validate_dart_exclusions(tmp_path, ["lib/**", "**/*.g.dart", "test/**"])
    message = str(refused.value)
    assert str(tmp_path / "analysis_options.yaml") in message
    assert "'lib/**', 'test/**'" in message
    assert "g.dart" not in message
    with pytest.raises(TypeError, match="must be a list of patterns"):
        validate_dart_exclusions(tmp_path, "**/*.g.dart")
    validate_dart_exclusions(tmp_path, ["**/*.g.dart"])


def test_the_line_limit_refusal_names_the_ways_out(tmp_path: Path) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "big.py").write_text("value = 1\n" * 1001)
    with pytest.raises(ValueError, match="big.py: 1001 lines") as refused:
        validate_file_sizes(root, {})
    message = str(refused.value)
    assert "Split the file" in message
    assert "linguist-generated=true" in message
    assert ".gitattributes" in message
    assert "file_size_exceptions" in message
    assert "reason" in message
    assert "evidence" in message
    assert "hard-eng.gates.json" in message


def gated_root(tmp_path: Path, *checks: dict[str, object]) -> Path:
    root = tmp_path / "project"
    init(root)
    configure(root, list(checks) or [gate("suite", "pass")])
    for name in ("PRODUCT.md", "DESIGN.md"):
        (root / name).write_text((SOURCE / name).read_text())
    return root


def line_limit_project(tmp_path: Path) -> Path:
    root = gated_root(tmp_path)
    (root / "big.py").write_text("value = 1\n" * 1001)
    commit(root, "start")
    with pytest.raises(ValueError, match="big.py: 1001 lines"):
        gate_config.load_groups(root)
    return root


def test_splitting_the_long_file_clears_the_line_limit_refusal(tmp_path: Path) -> None:
    root = line_limit_project(tmp_path)
    (root / "big.py").write_text("value = 1\n" * 500)
    (root / "big_more.py").write_text("value = 2\n" * 501)
    assert gate_config.load_groups(root)


def test_marking_the_file_generated_clears_the_line_limit_refusal(
    tmp_path: Path,
) -> None:
    root = line_limit_project(tmp_path)
    (root / ".gitattributes").write_text("big.py linguist-generated=true\n")
    assert gate_config.load_groups(root)


def test_a_file_size_exception_clears_the_line_limit_refusal(tmp_path: Path) -> None:
    root = line_limit_project(tmp_path)
    (root / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [gate("suite", "pass")],
                "file_size_exceptions": {
                    "big.py": {"reason": "fixture", "evidence": "fixture"}
                },
            }
        )
    )
    assert gate_config.load_groups(root)


def ignored_dart_lock(tmp_path: Path) -> tuple[Path, GateConfig]:
    root = tmp_path / "project"
    init(root)
    package = root / "app"
    package.mkdir()
    (package / "pubspec.yaml").write_text("name: app\n")
    (root / ".gitignore").write_text("pubspec.lock\n")
    commit(root, "start")
    config: GateConfig = {
        "shared": [],
        "packages": [
            {"path": "app", "language": "dart", "sources": ["lib"], "checks": []}
        ],
    }
    return root, config


def test_setup_refuses_an_ignored_lockfile_that_is_not_there_yet(
    tmp_path: Path,
) -> None:
    root, config = ignored_dart_lock(tmp_path)
    package = root / "app"
    assert not (package / "pubspec.lock").exists()
    with pytest.raises(ValueError, match=r"app/pubspec.lock is ignored by Git"):
        adapt_packages(root, config)
    (root / ".gitignore").write_text("")
    adapt_packages(root, config)


@pytest.mark.parametrize(
    ("language", "manifest", "workspace", "lock"),
    [
        (
            "python",
            "pyproject.toml",
            '[project]\nname = "app"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n',
            "uv.lock",
        ),
        (
            "javascript",
            "package.json",
            '{"name": "app", "workspaces": ["packages/*"]}\n',
            "bun.lock",
        ),
        (
            "dart",
            "pubspec.yaml",
            "name: app\nworkspace:\n  - packages/part\n",
            "pubspec.lock",
        ),
    ],
)
def test_setup_passes_a_workspace_member_that_uses_the_lockfile_of_its_root(
    tmp_path: Path, language: str, manifest: str, workspace: str, lock: str
) -> None:
    root = tmp_path / "project"
    init(root)
    member = root / "packages/part"
    member.mkdir(parents=True)
    (root / manifest).write_text(workspace)
    (root / lock).write_text("# lock\n")
    text = {
        "python": '[project]\nname = "part"\n',
        "javascript": '{"name": "part"}\n',
        "dart": "name: part\nresolution: workspace\n",
    }
    (member / manifest).write_text(text[language])
    (root / ".gitignore").write_text(f"packages/*/{lock}\n")
    commit(root, "start")

    def config() -> GateConfig:
        return {
            "shared": [],
            "packages": [
                {"path": path, "language": language, "sources": ["lib"], "checks": []}
                for path in (".", "packages/part")
            ],
        }

    adapt_packages(root, config())
    (root / ".gitignore").write_text(f"{lock}\n")
    git(root, "rm", "-q", "--cached", lock)
    commit(root, "ignore the lock file of the root")
    with pytest.raises(ValueError, match=rf"^{lock} is ignored by Git"):
        adapt_packages(root, config())


def ignored_lock_project(
    tmp_path: Path, lock: str, checks: list[dict[str, object]]
) -> Path:
    root = tmp_path / "project"
    init(root)
    configure(root, checks)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (root / name).write_text((SOURCE / name).read_text())
    (root / ".gitignore").write_text(f"{lock}\n")
    commit(root, "start")
    (root / lock).write_text("# lock\n")
    return root


def test_an_ignored_lockfile_of_another_manager_does_not_fail_the_config_load(
    tmp_path: Path,
) -> None:
    root = ignored_lock_project(
        tmp_path,
        "poetry.lock",
        [
            gate(
                "lockfile", "pass", role="lockfiles", command=["uv", "sync", "--locked"]
            )
        ],
    )
    assert gate_config.load_groups(root)


def test_an_ignored_package_resolved_does_not_fail_a_group_with_no_lockfile_gate(
    tmp_path: Path,
) -> None:
    root = ignored_lock_project(tmp_path, "Package.resolved", [gate("suite", "pass")])
    assert gate_config.load_groups(root)


def test_the_step_for_an_ignored_lockfile_that_is_not_on_disk_can_be_done(
    tmp_path: Path,
) -> None:
    root, config = ignored_dart_lock(tmp_path)
    package = root / "app"
    with pytest.raises(ValueError, match=r"app/pubspec.lock is ignored") as refused:
        adapt_packages(root, config)
    message = str(refused.value)
    assert "run the project's install" in message
    assert "then commit app/pubspec.lock" in message
    (root / ".gitignore").write_text("")
    (package / "pubspec.lock").write_text("# lock\n")
    commit(root, "track the lock file")
    adapt_packages(root, config)


def test_check_refuses_a_lockfile_that_git_ignores(tmp_path: Path) -> None:
    root = gated_root(
        tmp_path,
        gate("lockfile", "pass", role="lockfiles", command=["uv", "sync", "--locked"]),
    )
    (root / ".gitignore").write_text("uv.lock\n")
    commit(root, "start")
    (root / "uv.lock").write_text("# lock\n")
    with pytest.raises(ValueError, match=r"uv.lock is ignored by Git") as refused:
        gate_config.load_groups(root)
    assert "git check-ignore -v uv.lock" in str(refused.value)
    (root / ".gitignore").write_text("")
    assert gate_config.load_groups(root)


def lock_rule_project(tmp_path: Path, caller: str, kind: str, tracked: bool) -> Path:
    root = tmp_path / "project"
    init(root)
    configure(
        root,
        [
            gate(
                "lockfile", "pass", role="lockfiles", command=["uv", "sync", "--locked"]
            )
        ],
    )
    for name in ("PRODUCT.md", "DESIGN.md"):
        (root / name).write_text((SOURCE / name).read_text())
    if caller == "setup":
        (root / "pyproject.toml").write_text('[project]\nname = "app"\n')
    (root / "shared").mkdir()
    (root / "shared/uv.lock").write_text("# lock\n")
    if not tracked:
        (root / ".gitignore").write_text("/uv.lock\n")
    if kind == "link":
        (root / "uv.lock").symlink_to("shared/uv.lock")
    else:
        (root / "uv.lock").write_text("# lock\n")
    commit(root, "start")
    return root


def run_lock_rule(root: Path, caller: str) -> None:
    if caller == "load":
        gate_config.load_groups(root)
        return
    config: GateConfig = {
        "shared": [],
        "packages": [
            {"path": ".", "language": "python", "sources": ["lib"], "checks": []}
        ],
    }
    adapt_packages(root, config)


@pytest.mark.parametrize("caller", ["setup", "load"])
def test_a_tracked_lockfile_link_passes_setup_and_the_config_load(
    tmp_path: Path, caller: str
) -> None:
    root = lock_rule_project(tmp_path, caller, "link", tracked=True)
    assert (root / "uv.lock").is_symlink()
    run_lock_rule(root, caller)


@pytest.mark.parametrize("caller", ["setup", "load"])
@pytest.mark.parametrize(
    ("kind", "tracked"),
    [("file", True), ("file", False), ("link", True), ("link", False)],
)
def test_the_lockfile_rule_follows_git_for_files_and_links(
    tmp_path: Path, caller: str, kind: str, tracked: bool
) -> None:
    root = lock_rule_project(tmp_path, caller, kind, tracked)
    if tracked:
        run_lock_rule(root, caller)
        return
    with pytest.raises(ValueError, match=r"uv.lock is ignored by Git"):
        run_lock_rule(root, caller)
