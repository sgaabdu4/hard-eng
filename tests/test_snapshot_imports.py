from pathlib import Path

import pytest
import ship_actions
from conftest import commit, init
from shipping import git


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
def test_an_import_resolves_the_way_dart_resolves_it(
    tmp_path: Path, importer: str, directive: str, expected: str | None
) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "pubspec.yaml").write_text("name: app\n")
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
