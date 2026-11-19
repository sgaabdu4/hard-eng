from pathlib import Path

import pytest
import ship_actions
from conftest import commit, init
from shipping import Shipment, git


def project(root: Path, imported: bool = True, importer_tracked: bool = True) -> str:
    init(root)
    (root / ".gitignore").write_text("lib/firebase_options.dart\nlib/other.dart\n")
    (root / "pubspec.yaml").write_text("name: app\n")
    (root / "lib/screens").mkdir(parents=True)
    (root / "lib/main.dart").write_text(
        "import 'package:app/firebase_options.dart';\nvoid main() {}\n"
        if imported
        else "void main() {}\n"
    )
    (root / "lib/screens/home.dart").write_text(
        "import '../firebase_options.dart' as options;\n" * imported
        + "export 'package:flutter/widgets.dart';\nimport 'dart:io';\n"
    )
    revision = commit(root, "start")
    if not importer_tracked:
        (root / "lib/untracked.dart").write_text("import 'other.dart';\n")
    (root / "lib/firebase_options.dart").write_text("const key = 'secret';\n")
    (root / "lib/other.dart").write_text("const other = 1;\n")
    return revision


def snapshot_of(root: Path, revision: str) -> Path:
    checkout = root.parent / "snapshot"
    git(root, "worktree", "add", "--detach", str(checkout), revision)
    ship_actions.link_local_files(root, checkout)
    return checkout


def test_an_ignored_file_that_tracked_code_imports_is_linked_into_the_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    checkout = snapshot_of(root, project(root))
    link = checkout / "lib/firebase_options.dart"
    assert link.is_symlink()
    assert link.resolve() == (root / "lib/firebase_options.dart").resolve()
    assert (checkout / "lib/main.dart").read_text().startswith("import 'package:app/")
    assert not (checkout / "lib/other.dart").exists()
    assert "!! lib/firebase_options.dart" in ship_actions.placed_by_hard_eng(
        root, checkout
    )
    status = git(checkout, "status", "--porcelain", "--ignored=matching")
    assert "!! lib/firebase_options.dart" in status.splitlines()
    assert "??" not in status


def test_a_missing_imported_file_stays_missing_in_the_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    revision = project(root)
    (root / "lib/firebase_options.dart").unlink()
    checkout = snapshot_of(root, revision)
    assert not (checkout / "lib/firebase_options.dart").exists()
    assert not (checkout / "lib/firebase_options.dart").is_symlink()


def test_an_ignored_file_that_no_tracked_file_imports_is_not_linked(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    checkout = snapshot_of(root, project(root, imported=False))
    assert not (checkout / "lib/firebase_options.dart").is_symlink()
    assert not (checkout / "lib/firebase_options.dart").exists()


def test_an_ignored_file_that_only_an_untracked_file_imports_is_not_linked(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    checkout = snapshot_of(root, project(root, imported=False, importer_tracked=False))
    assert not (checkout / "lib/other.dart").exists()


def test_the_link_stays_placed_by_hard_eng_after_the_import_is_removed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    checkout = snapshot_of(root, project(root))
    for name in ("lib/main.dart", "lib/screens/home.dart"):
        (checkout / name).write_text("void main() {}\n")
    assert "!! lib/firebase_options.dart" in ship_actions.placed_by_hard_eng(
        root, checkout
    )


def kept_by_cleanup(root: Path, checkout: Path, revision: str) -> None:
    ship_actions.unchanged_checkout(
        Shipment(
            root=checkout,
            plan=checkout / "PLAN.md",
            pr_url="https://github.com/fixture/project/pull/1",
            repository="fixture/project",
            remote="origin",
            remote_url=str(root),
            branch="main",
            head_sha=revision,
            base="main",
            merged_sha=revision,
            delivery_target="Merge",
        )
    )


def generated_project(root: Path, tracked_beside: bool) -> str:
    init(root)
    (root / ".gitignore").write_text("lib/gen/key.dart\n")
    (root / "pubspec.yaml").write_text("name: app\n")
    (root / "lib/gen").mkdir(parents=True)
    (root / "lib/main.dart").write_text("import 'gen/key.dart';\n")
    if tracked_beside:
        (root / "lib/gen/beside.dart").write_text("const beside = 1;\n")
    revision = commit(root, "start")
    (root / "lib/gen/key.dart").write_text("const key = 'secret';\n")
    return revision


def test_an_ignored_file_alone_in_its_folder_is_linked_with_the_folder_made(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    revision = generated_project(root, tracked_beside=False)
    checkout = snapshot_of(root, revision)
    assert not (root / "lib/gen/beside.dart").exists()
    link = checkout / "lib/gen/key.dart"
    assert link.is_symlink()
    assert link.resolve() == (root / "lib/gen/key.dart").resolve()
    status = git(
        checkout, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"
    )
    assert set(status.splitlines()) == ship_actions.placed_by_hard_eng(root, checkout)
    kept_by_cleanup(root, checkout, revision)


def test_an_ignored_file_is_linked_when_the_commit_removed_its_folder(
    tmp_path: Path,
) -> None:
    root = tmp_path / "project"
    generated_project(root, tracked_beside=True)
    pushed = tmp_path / "pushed"
    git(root, "worktree", "add", "-b", "pushed", str(pushed))
    git(pushed, "rm", "-q", "lib/gen/beside.dart")
    revision = commit(pushed, "remove the tracked file of the folder")
    checkout = snapshot_of(root, revision)
    assert not (checkout / "lib/gen/beside.dart").exists()
    assert (checkout / "lib/gen/key.dart").is_symlink()
    status = git(
        checkout, "status", "--porcelain", "--untracked-files=all", "--ignored=matching"
    )
    assert set(status.splitlines()) == ship_actions.placed_by_hard_eng(root, checkout)
    kept_by_cleanup(root, checkout, revision)


def refuse_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    def scan(checkout: Path, candidates: set[str]) -> set[str]:
        raise AssertionError(f"scanned for {sorted(candidates)}")

    monkeypatch.setattr(ship_actions, "imported_files", scan)


@pytest.mark.parametrize(
    ("l10n", "outputs"),
    [
        (
            "arb-dir: lib/l10n\n",
            ["lib/l10n/app_localizations.dart", "lib/l10n/app_localizations_en.dart"],
        ),
        (
            "output-localization-file: strings.dart\n",
            ["lib/l10n/strings.dart", "lib/l10n/strings_en.dart"],
        ),
    ],
)
def test_files_that_a_generator_of_the_project_writes_are_not_linked_and_not_scanned_for(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    l10n: str,
    outputs: list[str],
) -> None:
    root = tmp_path / "project"
    init(root)
    generated = [
        "lib/model.g.dart",
        "lib/model.freezed.dart",
        "test/a.mocks.dart",
        *outputs,
    ]
    (root / ".gitignore").write_text("".join(f"{name}\n" for name in generated))
    (root / "pubspec.yaml").write_text("name: app\n")
    (root / "l10n.yaml").write_text(l10n)
    (root / "lib/l10n").mkdir(parents=True)
    (root / "test").mkdir()
    (root / "lib/model.dart").write_text(
        "part 'model.g.dart';\npart 'model.freezed.dart';\n"
        + "".join(f"import 'l10n/{Path(name).name}';\n" for name in outputs)
    )
    (root / "test/a_test.dart").write_text("import 'a.mocks.dart';\n")
    revision = commit(root, "start")
    for name in generated:
        (root / name).write_text("// generated\n")
    refuse_scan(monkeypatch)
    checkout = snapshot_of(root, revision)
    assert not [name for name in generated if (checkout / name).is_symlink()]


def test_the_scan_does_not_run_when_the_commit_already_holds_every_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    project(root)
    pushed = tmp_path / "pushed"
    git(root, "worktree", "add", "-b", "pushed", str(pushed))
    (pushed / "lib/firebase_options.dart").write_text("const key = 'tracked';\n")
    (pushed / "lib/other.dart").write_text("const other = 'tracked';\n")
    git(pushed, "add", "-f", "lib/firebase_options.dart", "lib/other.dart")
    revision = commit(pushed, "track both files")
    refuse_scan(monkeypatch)
    checkout = snapshot_of(root, revision)
    assert not (checkout / "lib/firebase_options.dart").is_symlink()


@pytest.mark.parametrize(
    ("importer", "directive", "expected"),
    [
        ("lib/a.dart", "import 'b.dart';", "lib/b.dart"),
        ("lib/a.dart", 'export "src/b.dart";', "lib/src/b.dart"),
        ("lib/a.dart", "part 'b.g.dart';", "lib/b.g.dart"),
        ("lib/s/a.dart", "import '../b.dart';", "lib/b.dart"),
        ("lib/a.dart", "import 'package:app/b.dart';", "lib/b.dart"),
        ("lib/a.dart", "import 'package:other/b.dart';", None),
        ("lib/a.dart", "import 'dart:io';", None),
        ("lib/a.dart", "import '../../outside.dart';", None),
        ("lib/a.dart", "// import 'b.dart';", None),
        (
            "lib/a.dart",
            "import 'stub.dart'\n    if (dart.library.io) 'b.dart';",
            "lib/b.dart lib/stub.dart",
        ),
        ("test/a.dart", "import 'package:app/b.dart';", "lib/b.dart"),
    ],
)
@pytest.mark.parametrize("name", ["app", '"app"', "'app'"])
def test_an_import_resolves_the_way_dart_resolves_it(
    tmp_path: Path, importer: str, directive: str, expected: str | None, name: str
) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "pubspec.yaml").write_text(f"name: {name}\n")
    (root / importer).parent.mkdir(parents=True, exist_ok=True)
    (root / importer).write_text(directive + "\n")
    commit(root, "start")
    ignored = {
        "lib/b.dart",
        "lib/stub.dart",
        "lib/src/b.dart",
        "lib/b.g.dart",
        "outside.dart",
    }
    found = ship_actions.imported_files(root, ignored)
    assert found == set((expected or "").split())
