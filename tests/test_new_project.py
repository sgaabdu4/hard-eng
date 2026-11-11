"""`setup.sh --new STACK`: official scaffold, Hard Eng starter files, exact pins, one commit."""

import json
import shutil
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

import pytest

import new_project

UPGRADE = ["bun", "update", "--latest", "--exact", "--minimum-release-age=172800"]


def test_new_project_refuses_a_repository_that_holds_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "notes.txt").write_text("keep\n")
    with pytest.raises(
        ValueError,
        match=r"or one with only plain README, license and ignore files \(no links\); it holds notes.txt",
    ):
        new_project.create(tmp_path, "vite")
    assert sorted(path.name for path in tmp_path.iterdir()) == [".git", "notes.txt"]


def test_new_project_refuses_a_linked_ignore_file(tmp_path: Path) -> None:
    root, outside = tmp_path / "repository", tmp_path / "shared-ignore"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    outside.write_text("secret.env\n")
    (root / ".gitignore").symlink_to(outside)
    with pytest.raises(ValueError, match="needs an empty repository"):
        new_project.create(root, "vite")
    assert outside.read_text() == "secret.env\n"
    assert (root / ".gitignore").is_symlink()


def test_new_project_refuses_a_folder_inside_another_repository(
    tmp_path: Path,
) -> None:
    """`git add --all` there would commit the parent repository's unrelated work."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    child = tmp_path / "apps/web"
    child.mkdir(parents=True)
    with pytest.raises(ValueError, match="Git repository root"):
        new_project.create(child, "vite")
    assert list(child.iterdir()) == []


def test_vite_starter_replaces_oxlint_and_pins_after_the_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    scaffold = {
        "scripts": {"build": "tsc -b && vite build", "lint": "oxlint"},
        "devDependencies": {"oxlint": "^1.81.0", "vite": "^8.3.0"},
    }
    ran: list[list[str]] = []

    def run(root: Path, command: list[str]) -> None:
        ran.append(command)
        if command == new_project.SCAFFOLDS["vite"]:
            (root / "package.json").write_text(json.dumps(scaffold))
            (root / ".oxlintrc.json").write_text("{}")
        elif command[0] == "git":
            identity = ["-c", "user.name=Fixture", "-c", "user.email=f@example.test"]
            subprocess.run(["git", *identity, *command[1:]], cwd=root, check=True)

    monkeypatch.setattr(new_project, "run", run)
    new_project.create(tmp_path, "vite")
    manifest = json.loads((tmp_path / "package.json").read_text())
    assert "lint" not in manifest["scripts"]
    assert manifest["scripts"]["build"] == "tsc -b && vite build"
    assert {"test:coverage", "test:performance", "lint:boundaries"} <= set(
        manifest["scripts"]
    )
    assert "oxlint" not in manifest["devDependencies"]
    assert manifest["devDependencies"]["@types/bun"] == "latest"
    assert manifest["devDependencies"]["fallow"] == "latest"
    assert not (tmp_path / ".oxlintrc.json").exists()
    assert (tmp_path / "tests/app.test.tsx").is_file()
    assert ran[1] == UPGRADE
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert status.stdout == ""


def test_flutter_pins_each_any_constraint_to_the_resolved_version() -> None:
    pubspec = (
        "environment:\n  sdk: ^3.13.4\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n  flutter_riverpod: any\n"
        "dev_dependencies:\n  build_runner: any\n"
    )
    lock = {
        "packages": {
            "flutter_riverpod": {"version": "3.4.3"},
            "build_runner": {"version": "2.16.2"},
        }
    }
    pinned = new_project.pinned_pubspec(pubspec, lock)
    assert "  flutter_riverpod: 3.4.3\n" in pinned
    assert "  build_runner: 2.16.2\n" in pinned
    assert "  sdk: ^3.13.4\n" in pinned
    assert ": any" not in pinned


def created(
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
    stack: str,
    files: dict[str, str],
    existing: Mapping[str, str | bytes] | None = None,
    inside: Callable[[Path], None] | None = None,
) -> list[list[str]]:
    """Create the stack with a fake scaffold that writes these files; the commands run."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name, text in (existing or {}).items():
        (root / name).write_bytes(text if isinstance(text, bytes) else text.encode())
    ran: list[list[str]] = []

    def run(target: Path, command: list[str]) -> None:
        ran.append(command)
        if command == new_project.SCAFFOLDS[stack]:
            if inside is not None:
                inside(target)
            for name, text in files.items():
                (target / name).parent.mkdir(parents=True, exist_ok=True)
                (target / name).write_text(text)

    monkeypatch.setattr(new_project, "run", run)
    new_project.create(root, stack)
    return ran


def test_opennext_upgrades_next_like_every_other_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A held-back Next.js release would fail the freshness check on day one."""
    manifest = json.dumps({"dependencies": {"next": "16.4.1"}})
    files = {"package.json": manifest, "eslint.config.mjs": "export default [];\n"}
    ran = created(tmp_path, monkeypatch, "opennext", files)
    upgrade = ran.index(UPGRADE)
    assert ran[upgrade + 1] == ["bun", "run", "cf-typegen"]
    assert not (tmp_path / "eslint.config.mjs").exists()


def test_nextjs_moves_the_scaffold_to_the_installed_biome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Biome 2.6 rejected the scaffold's older config, Markdown and untitled images."""
    image = '<svg viewBox="0 0 1 1"><path/></svg>'
    files = {"package.json": "{}", "biome.json": "{}", "public/next.svg": image}
    ran = created(tmp_path, monkeypatch, "nextjs", files)
    upgrade = ran.index(UPGRADE)
    assert ran[upgrade + 1 : upgrade + 3] == [
        ["bun", "x", "biome", "migrate", "--write"],
        ["bun", "x", "biome", "format", "--write", "."],
    ]
    assert (tmp_path / "public/next.svg").read_text() == (
        '<svg viewBox="0 0 1 1"><title>next</title><path/></svg>'
    )


def test_new_project_keeps_a_readme_license_and_ignore_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = {
        "README.md": "# Acme Shop\n",
        "LICENSE": "MIT\n",
        ".gitignore": "node_modules\nsecret.env\n",
    }
    files = {
        "package.json": "{}",
        ".oxlintrc.json": "{}",
        "README.md": "# scaffold\n",
        ".gitignore": "node_modules\ndist\n",
    }
    created(tmp_path, monkeypatch, "vite", files, existing)
    assert (tmp_path / "README.md").read_text() == "# Acme Shop\n"
    assert (tmp_path / "LICENSE").read_text() == "MIT\n"
    assert (tmp_path / ".gitignore").read_text() == "node_modules\ndist\nsecret.env\n"
    assert (tmp_path / "package.json").exists()


def test_kept_files_wait_in_the_git_folder_during_the_scaffold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    waiting: list[list[str]] = []

    def look(target: Path) -> None:
        folder = target / ".git" / new_project.ASIDE
        waiting.append(sorted(path.name for path in folder.iterdir()))

    created(
        tmp_path,
        monkeypatch,
        "vite",
        {"package.json": "{}", ".oxlintrc.json": ""},
        {"README.md": "mine"},
        look,
    )
    assert waiting == [["README.md"]]
    assert not (tmp_path / ".git" / new_project.ASIDE).exists()


def test_an_error_while_putting_files_back_leaves_the_rest_waiting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    move = shutil.move

    def failing(source: Path, destination: Path) -> object:
        if (
            Path(source).name == "README.md"
            and Path(destination) == tmp_path / "README.md"
        ):
            raise OSError("disk full")
        return move(source, destination)

    existing: dict[str, str | bytes] = {"README.md": "mine", "LICENSE": "MIT\n"}
    files = {"package.json": "{}", ".oxlintrc.json": ""}
    monkeypatch.setattr(shutil, "move", failing)
    with pytest.raises(OSError, match="disk full"):
        created(tmp_path, monkeypatch, "vite", files, existing)
    waiting = tmp_path / ".git" / new_project.ASIDE
    assert (waiting / "README.md").read_text() == "mine"


def test_an_earlier_stopped_run_gets_its_files_back_first(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    waiting = tmp_path / ".git" / new_project.ASIDE
    waiting.mkdir()
    (waiting / "README.md").write_text("mine")
    (tmp_path / "scaffold-leftover.txt").write_text("x")
    with pytest.raises(ValueError, match="needs an empty repository"):
        new_project.create(tmp_path, "vite")
    assert (tmp_path / "README.md").read_text() == "mine"
    assert not waiting.exists()


def test_a_stopped_run_never_replaces_a_file_the_repository_now_holds(
    tmp_path: Path,
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    waiting = tmp_path / ".git" / new_project.ASIDE
    waiting.mkdir()
    (waiting / "README.md").write_text("old")
    (waiting / "LICENSE").write_text("MIT\n")
    (tmp_path / "README.md").write_text("new")
    with pytest.raises(ValueError, match=r"README\.md.*remove the other"):
        new_project.create(tmp_path, "vite")
    assert (tmp_path / "README.md").read_text() == "new"
    assert (waiting / "README.md").read_text() == "old"
    assert (tmp_path / "LICENSE").read_text() == "MIT\n"
    assert not (waiting / "LICENSE").exists()


def test_a_kept_ignore_file_with_odd_bytes_keeps_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = {"package.json": "{}", ".oxlintrc.json": "", ".gitignore": "dist\n"}
    created(tmp_path, monkeypatch, "vite", files, {".gitignore": b"caf\xe9\n"})
    assert (tmp_path / ".gitignore").read_bytes() == b"dist\ncaf\xe9\n"


def test_nextjs_scaffold_installs_nothing_before_the_age_filter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = created(tmp_path, monkeypatch, "nextjs", {"package.json": "{}"})
    assert ran[0] == new_project.SCAFFOLDS["nextjs"]
    assert "--skip-install" in ran[0]
    assert ran[1] == UPGRADE


def test_opennext_replaces_the_vulnerable_glob_its_minifier_pins() -> None:
    """@node-minify/core pins glob 10.3.3 (GHSA-5j98-mcp5-4vw2); it only calls globSync."""
    starter = new_project.SOURCE / ".agents/starters/opennext/package.json"
    assert json.loads(starter.read_text())["overrides"]["glob"] == ">=10.5.0"


def test_opennext_replaces_the_vulnerable_undici_miniflare_pins() -> None:
    """Miniflare pins undici 7.29.1 (GHSA-4qv8-2p9j-2685); dotenvx keeps its own undici 6."""
    starter = new_project.SOURCE / ".agents/starters/opennext/package.json"
    overrides = json.loads(starter.read_text())["overrides"]
    assert overrides["miniflare"] == {"undici": "^7.30.1"}


def test_python_locks_the_scaffold_and_adds_tested_starter_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new Python project starts with tests and a performance suite, so its first check passes."""
    ran = created(tmp_path, monkeypatch, "python", {"main.py": "print('hi')\n"})
    assert "--no-package" in ran[0]
    assert ran[2] == ["uv", "lock", "--quiet"]
    assert (tmp_path / "tests/test_main.py").is_file()
    assert (tmp_path / "tests/performance/test_greeting_performance.py").is_file()
    assert "def greeting" in (tmp_path / "main.py").read_text()


def test_python_declares_pytest_for_the_types_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = created(tmp_path, monkeypatch, "python", {"main.py": "print('hi')\n"})
    declared = ["uv", "add", "--quiet", "--dev", "--bounds", "exact", "--no-sync"]
    assert ran[1] == [*declared, "pytest"]
    assert ran.index(["uv", "lock", "--quiet"]) > 1


def test_the_python_starter_test_calls_main_directly() -> None:
    starter = new_project.SOURCE / ".agents/starters/python/tests/test_main.py"
    text = starter.read_text()
    assert "main.main()" in text
    assert "runpy" not in text
    assert "run_module" not in text
    assert "__main__" not in text
