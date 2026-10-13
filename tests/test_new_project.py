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
