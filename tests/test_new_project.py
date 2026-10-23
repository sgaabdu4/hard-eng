"""`setup.sh --new STACK`: official scaffold, Hard Eng starter files, exact pins, one commit."""

import json
import subprocess
from pathlib import Path

import pytest

import new_project


def test_new_project_refuses_a_repository_that_holds_files(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "notes.txt").write_text("keep\n")
    with pytest.raises(
        ValueError, match="needs an empty repository; it holds notes.txt"
    ):
        new_project.create(tmp_path, "vite")
    assert sorted(path.name for path in tmp_path.iterdir()) == [".git", "notes.txt"]


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
    assert not (tmp_path / ".oxlintrc.json").exists()
    assert (tmp_path / "tests/app.test.tsx").is_file()
    assert ran[1] == ["bun", "update", "--latest", "--exact"]
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
    root: Path, monkeypatch: pytest.MonkeyPatch, stack: str, files: dict[str, str]
) -> list[list[str]]:
    """Create the stack with a fake scaffold that writes these files; the commands run."""
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    ran: list[list[str]] = []

    def run(target: Path, command: list[str]) -> None:
        ran.append(command)
        if command == new_project.SCAFFOLDS[stack]:
            for name, text in files.items():
                (target / name).parent.mkdir(parents=True, exist_ok=True)
                (target / name).write_text(text)

    monkeypatch.setattr(new_project, "run", run)
    new_project.create(root, stack)
    return ran


def test_opennext_keeps_the_scaffold_next_release_after_the_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Newer Next.js releases build but fail at runtime on OpenNext's Worker."""
    manifest = json.dumps({"dependencies": {"next": "16.3.8"}})
    files = {"package.json": manifest, "eslint.config.mjs": "export default [];\n"}
    ran = created(tmp_path, monkeypatch, "opennext", files)
    upgrade = ran.index(["bun", "update", "--latest", "--exact"])
    assert ran[upgrade + 1] == ["bun", "add", "--exact", "next@16.3.8"]
    assert ran[upgrade + 2] == ["bun", "run", "cf-typegen"]
    assert not (tmp_path / "eslint.config.mjs").exists()


def test_nextjs_moves_the_scaffold_to_the_installed_biome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Biome 2.6 rejected the scaffold's older config, Markdown and untitled images."""
    image = '<svg viewBox="0 0 1 1"><path/></svg>'
    files = {"package.json": "{}", "biome.json": "{}", "public/next.svg": image}
    ran = created(tmp_path, monkeypatch, "nextjs", files)
    upgrade = ran.index(["bun", "update", "--latest", "--exact"])
    assert ran[upgrade + 1 : upgrade + 3] == [
        ["bun", "x", "biome", "migrate", "--write"],
        ["bun", "x", "biome", "format", "--write", "."],
    ]
    assert (tmp_path / "public/next.svg").read_text() == (
        '<svg viewBox="0 0 1 1"><title>next</title><path/></svg>'
    )


def test_opennext_replaces_the_vulnerable_glob_its_minifier_pins() -> None:
    """@node-minify/core pins glob 10.3.3 (GHSA-5j98-mcp5-4vw2); it only calls globSync."""
    starter = new_project.SOURCE / ".agents/starters/opennext/package.json"
    assert json.loads(starter.read_text())["overrides"]["glob"] == ">=10.5.0"


def test_python_locks_the_scaffold_and_adds_tested_starter_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A new Python project starts with tests and a performance suite, so its first check passes."""
    ran = created(tmp_path, monkeypatch, "python", {"main.py": "print('hi')\n"})
    assert "--no-package" in ran[0]
    assert ran[1] == ["uv", "lock", "--quiet"]
    assert (tmp_path / "tests/test_main.py").is_file()
    assert (tmp_path / "tests/performance/test_greeting_performance.py").is_file()
    assert "def greeting" in (tmp_path / "main.py").read_text()
