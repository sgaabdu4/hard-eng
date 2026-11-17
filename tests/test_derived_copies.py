"""A folder mark exempts a folder only when Hard Eng proves it is a byte copy of a package that nothing exempts."""

from pathlib import Path

from conftest import SOURCE as HARD_ENG
from conftest import commit, git
from generated_marks import generated_sources
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

SOURCE = {
    "packages/lib_a/pubspec.yaml": "name: lib_a\nversion: 1.0.0\n",
    "packages/lib_a/lib/a.dart": "int a() => 1;\n",
    "packages/lib_a/lib/src/b.dart": "int b() => 2;\n",
}
COPY = {
    name.replace("packages/lib_a", "functions/f/vendor/lib_a"): text
    for name, text in SOURCE.items()
}
MARK = "functions/f/vendor/lib_a/** linguist-vendored\n"


def exempt(root: Path) -> set[str]:
    return generated_sources(root, sorted(COPY))


def test_a_byte_copy_of_a_judged_package_is_exempt(tmp_path: Path) -> None:
    root = project(tmp_path, {**SOURCE, **COPY, ".gitattributes": MARK})
    assert exempt(root) == set(COPY)
    validate_whole_project(root)


def test_a_runtime_copy_without_dev_dependencies_and_with_a_lock_is_exempt(
    tmp_path: Path,
) -> None:
    """A function ships `lib` and a `pubspec.yaml` without `dev_dependencies`, and pub adds its own lock."""
    source = {
        **SOURCE,
        "packages/lib_a/pubspec.yaml": "name: lib_a\nversion: 1.0.0\n\ndev_dependencies:\n  test: ^1.0.0\n",
        "packages/lib_a/test/a_test.dart": "void main() {}\n",
    }
    copy = {
        **COPY,
        "functions/f/vendor/lib_a/pubspec.lock": "packages: {}\n",
    }
    root = project(tmp_path, {**source, **copy, ".gitattributes": MARK})
    assert generated_sources(root, sorted(copy)) == set(copy)


def test_a_copy_with_one_changed_line_is_refused_and_names_the_file(
    tmp_path: Path,
) -> None:
    changed = {**COPY, "functions/f/vendor/lib_a/lib/src/b.dart": "int b() => 3;\n"}
    root = project(tmp_path, {**SOURCE, **changed, ".gitattributes": MARK})
    assert exempt(root) == set()
    message = refusal(root)
    assert (
        "functions/f/vendor/lib_a/lib/src/b.dart differs from packages/lib_a/lib/src/b.dart"
        in message
    )


def test_a_vendored_folder_with_no_source_is_not_exempt(tmp_path: Path) -> None:
    root = project(tmp_path, {**COPY, ".gitattributes": MARK})
    assert exempt(root) == set()


def test_a_copy_whose_source_is_exempt_is_not_exempt(tmp_path: Path) -> None:
    marks = MARK + "packages/lib_a/lib/a.dart linguist-generated=true\n"
    root = project(tmp_path, {**SOURCE, **COPY, ".gitattributes": marks})
    assert exempt(root) == set()


def test_a_folder_of_hand_written_code_is_not_exempt(tmp_path: Path) -> None:
    files = {
        "src/pubspec.yaml": "name: mine\n",
        "src/a.dart": "int a() => 1;\n",
        ".gitattributes": "src/** linguist-vendored\n",
    }
    root = project(tmp_path, files)
    assert generated_sources(root, ["src/a.dart"]) == set()


def test_a_tracked_file_deleted_from_disk_does_not_crash_the_proof(
    tmp_path: Path,
) -> None:
    """The proof reads what Git tracks, so a file removed but not staged is no crash."""
    root = project(tmp_path, {**SOURCE, **COPY, ".gitattributes": MARK})
    (root / "packages/lib_a/pubspec.yaml").unlink()
    (root / "functions/f/vendor/lib_a/lib/a.dart").unlink()
    assert exempt(root) == set(COPY)
    validate_whole_project(root)


def test_a_source_made_of_links_to_the_copy_is_not_a_source(tmp_path: Path) -> None:
    """A link in the source package carries a path, not the copy's bytes."""
    root = project(tmp_path, {**COPY, ".gitattributes": MARK})
    for name in SOURCE:
        link = root / name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(
            root / name.replace("packages/lib_a", "functions/f/vendor/lib_a")
        )
    git(root, "add", "-A")
    commit(root, "links")
    assert exempt(root) == set()


def test_a_mark_with_a_leading_slash_names_one_root_file(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        {
            "cloudflare-env.d.ts": "/* eslint-disable */\ndeclare const a: 1;\n",
            "sub/cloudflare-env.d.ts": "/* eslint-disable */\ndeclare const a: 1;\n",
            ".gitattributes": "/cloudflare-env.d.ts linguist-generated=true\n",
        },
    )
    assert generated_sources(root, ["cloudflare-env.d.ts"]) == {"cloudflare-env.d.ts"}
    assert generated_sources(root, ["sub/cloudflare-env.d.ts"]) == set()


def test_the_web_starter_marks_the_file_wrangler_writes(tmp_path: Path) -> None:
    """Wrangler writes `eslint-disable` on line 1 of the file that setup commits."""
    starter = HARD_ENG / ".agents/starters/opennext/.gitattributes"
    root = project(
        tmp_path,
        {
            "cloudflare-env.d.ts": "/* eslint-disable */\ndeclare const a: 1;\n",
            ".gitattributes": starter.read_text(),
        },
    )
    validate_whole_project(root)
