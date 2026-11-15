"""The full check judges every tracked file, old code included."""

import re
from pathlib import Path
from types import ModuleType

import pytest
from comments import validate_suppressions
from conftest import SOURCE, commit, configure, gate, init
from requirement_registry import registry_entries
from switch_off_forms import RETRY_FORMS, SWITCHES
from whole_project import NEEDS_NO_LINK, NEEDS_NO_LINK_FOLDERS, validate_whole_project

OFF = "A change must not switch a check off"
HIDDEN = "ok = 1\nx = 1  # no" + "qa\n"


def project(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    tmp_path.mkdir(parents=True, exist_ok=True)
    init(root)
    for name, text in {"README.md": "fixture\n", **files}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    commit(root, "baseline")
    return root


def refusal(root: Path) -> str:
    with pytest.raises(ValueError) as error:
        validate_whole_project(root)
    return str(error.value)


OLD_FORMS = [row for row in [*SWITCHES, *RETRY_FORMS] if row[0] != ".gitleaks.toml"]


@pytest.mark.parametrize(("name", "text", "pattern"), OLD_FORMS)
def test_old_switch_offs_anywhere_in_the_project_fail(
    tmp_path: Path, name: str, text: str, pattern: str
) -> None:
    """HE-NO-SWITCH-OFF: a switch-off that the project held before the change fails too."""
    root = project(tmp_path, {name: "ok = 1\n" + text})
    message = refusal(root)
    assert OFF in message
    assert f"{name}:2 holds {pattern!r}" in message


def test_switch_offs_in_generated_output_pass(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: generated output and scaffold paths stay exempt."""
    files = {
        ".gitattributes": "*.g.py linguist-generated=true\n",
        "made.g.py": HIDDEN,
        ".hooks/tool.py": HIDDEN,
        ".agents/skills/tool/run.py": HIDDEN,
        ".claude/rules/run.py": HIDDEN,
    }
    validate_whole_project(project(tmp_path, files))
    assert "app.py:2 holds" in refusal(project(tmp_path / "own", {"app.py": HIDDEN}))


ALLOWLIST_FORMS = {
    "[allowlist]": "[allowlist]\npaths = ['''a''']\n",
    "[[allowlists]]": "[[allowlists]]\npaths = ['''a''']\n",
    "rule allowlists": "[[rules]]\nid = 'mine'\nregex = '''a'''\n[[rules.allowlists]]\npaths = ['''a''']\n",
    "rule allowlist": "[[rules]]\nid = 'mine'\nregex = '''a'''\n[rules.allowlist]\npaths = ['''a''']\n",
}
DETECTION_ONLY = "[extend]\nuseDefault = true\n[[rules]]\nid = 'mine'\nregex = '''AKIA[A-Z0-9]{16}'''\n"


def test_gitleaks_rules_pass_and_allowlists_fail(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: an allowlist entry in the Gitleaks config fails; a detection rule does not."""
    notes = {".gitleaksignore": "# a note\n\n", ".semgrepignore": "# a note\n"}
    validate_whole_project(
        project(tmp_path / "rules", {".gitleaks.toml": DETECTION_ONLY, **notes})
    )
    for form, text in ALLOWLIST_FORMS.items():
        message = refusal(
            project(
                tmp_path / form.strip("[]").replace(" ", "-"), {".gitleaks.toml": text}
            )
        )
        assert re.search(r"\.gitleaks\.toml:[1-4] holds an allowlist", message), form


def test_gitleaks_disabled_rules_fail(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a Gitleaks config that turns a rule off fails; an empty list turns none off."""
    empty = "[extend]\nuseDefault = true\ndisabledRules = []\n"
    validate_whole_project(project(tmp_path / "empty", {".gitleaks.toml": empty}))
    off = "[extend]\nuseDefault = true\ndisabledRules = ['aws-access-token']\n"
    message = refusal(project(tmp_path / "off", {".gitleaks.toml": off}))
    assert ".gitleaks.toml:3 disables the rules ['aws-access-token']" in message
    assert "fix the cause" in message


DART_FORMS = [
    (
        "// dart-decimate-ignore-next-line complexity",
        "// dart-decimate-ignore-next-line",
    ),
    ("// dart-decimate-ignore-next-line", "// dart-decimate-ignore-next-line"),
    ("//dart-decimate-ignore-next-line all", "//dart-decimate-ignore-next-line"),
    (
        "    // dart-decimate-ignore-next-line\tall",
        "// dart-decimate-ignore-next-line",
    ),
    ("// dart-decimate-ignore-file", "// dart-decimate-ignore-file"),
    ("// dart-decimate-ignore-file all", "// dart-decimate-ignore-file"),
]


@pytest.mark.parametrize(("form", "shown"), DART_FORMS)
def test_dart_decimate_ignore_is_a_switch_off(
    tmp_path: Path, form: str, shown: str
) -> None:
    """HE-NO-SWITCH-OFF: a dart-decimate ignore comment fails in an added line and in an old one."""
    root = project(tmp_path, {"lib/a.dart": "int a() => 1;\n"})
    (root / "lib/a.dart").write_text(f"{form}\nint a() => 1;\n")
    with pytest.raises(ValueError, match=OFF) as added:
        validate_suppressions(root, "HEAD")
    assert f"lib/a.dart:1 adds {shown!r}" in str(added.value)
    commit(root, "old")
    assert f"lib/a.dart:1 holds {shown!r}" in refusal(root)


MARKERS = [
    ("app.py", "x = 1\n# TODO: later\n", 2, "TODO"),
    ("app.py", "x = 1  # FIXME later\n", 1, "FIXME"),
    ("lib/a.dart", "final a = 1; // HACK\n", 1, "HACK"),
    ("src/a.ts", "/* XXX */\nconst a = 1;\n", 1, "XXX"),
    ("src/a.ts", "const b = 1; // later TODO\n", 1, "TODO"),
    ("run.sh", "echo hi # TODO\n", 1, "TODO"),
    ("run.sh", "# FIXME\necho hi\n", 1, "FIXME"),
]


@pytest.mark.parametrize(("name", "text", "line", "word"), MARKERS)
def test_excuse_markers_fail_anywhere_in_the_project(
    tmp_path: Path, name: str, text: str, line: int, word: str
) -> None:
    """HE-COMMENT-LINES: a TODO, FIXME, HACK or XXX marker in any comment fails, old ones too."""
    message = refusal(project(tmp_path, {name: text}))
    assert f"{name}:{line} holds a {word} marker" in message


MARKER_STRINGS = [
    ("app.py", "x = 'TODO'\ny = \"# FIXME\"\nz = 1  # a TODOS list\n"),
    ("src/a.ts", "const t = 'HACK';\nconst u = `// XXX`;\n"),
    ("lib/a.dart", "final s = 'TODO // FIXME';\n"),
    ("run.sh", "echo 'TODO' \"# HACK\"\n"),
]


@pytest.mark.parametrize(("name", "text"), MARKER_STRINGS)
def test_marker_words_in_strings_pass(tmp_path: Path, name: str, text: str) -> None:
    validate_whole_project(project(tmp_path, {name: text}))


def test_an_unnamed_markdown_file_fails(tmp_path: Path) -> None:
    """HE-NAMED-MARKDOWN: a markdown file that no other tracked file names fails, old ones too."""
    root = project(tmp_path, {"notes/extra.md": "text\n", "app.py": "x = 'y.md'\n"})
    message = refusal(root)
    assert "notes/extra.md:1 is named by no other tracked file" in message
    assert "y.md" not in message
    (root / "own.md").write_text("own.md\n")
    assert "own.md:1 is named by no other tracked file" in refusal(root)


NO_LINK_NEEDED = [
    "AGENTS.md",
    "AGENTS.override.md",
    "PRODUCT.md",
    "DESIGN.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "DECISION.md",
    "features/a/PLAN.md",
    "features/b/plan.md",
    "docs/adr/0001-first.md",
    "docs/requirements.md",
    ".agents/skills/a/SKILL.md",
    ".claude/rules/a.md",
    ".hooks/a.md",
    "pkg/README.md",
]


def test_a_named_markdown_file_passes(tmp_path: Path) -> None:
    named = {
        "README.md": "see notes/extra.md and guide.md\n",
        "notes/extra.md": "text\n",
        "sub/guide.md": "text\n",
    }
    others = dict.fromkeys(NO_LINK_NEEDED, "text\n")
    validate_whole_project(project(tmp_path, {**named, **others}))


OLD_BLOCK = "# written long ago\n# across two lines\nx = 1\n"


def test_old_comment_blocks_in_untouched_files_fail(tmp_path: Path) -> None:
    """HE-COMMENT-LINES: the full check fails a comment block in a file that no change touched."""
    exempt = {
        ".gitattributes": "*.g.py linguist-generated=true\n",
        "made.g.py": OLD_BLOCK,
        ".agents/skills/a/run.py": OLD_BLOCK,
    }
    validate_whole_project(project(tmp_path / "exempt", exempt))
    for name in ("old.py", "lib/old.dart", "src/old.ts", "old.sh", ".hooks/old.py"):
        text = OLD_BLOCK.replace("x = 1", "x") if name.endswith(".sh") else OLD_BLOCK
        text = text.replace("#", "//") if name.endswith((".dart", ".ts")) else text
        message = refusal(project(tmp_path / name.replace("/", "-"), {name: text}))
        assert f"{name}:1 holds a 2-line comment block" in message


def test_each_refusal_names_the_fix_at_the_cause(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: every whole-project refusal tells the agent to fix the cause, never to suppress."""
    cases = {
        "switch-off": {"app.py": HIDDEN},
        "dart-decimate": {
            "lib/a.dart": "// dart-decimate-ignore-next-line\nint a() => 1;\n"
        },
        "gitleaks": {".gitleaks.toml": "[allowlist]\npaths = ['''a''']\n"},
        "marker": {"app.py": "x = 1  # TO" + "DO later\n"},
        "comment block": {"app.py": OLD_BLOCK},
        "markdown": {"notes/extra.md": "text\n"},
    }
    for kind, files in cases.items():
        message = refusal(project(tmp_path / kind.replace(" ", "-"), files))
        assert "fix" in message.lower(), kind
        assert "suppress" in message.lower(), kind
        assert "never" in message.lower() or "instead of" in message.lower(), kind


def test_quick_check_skips_the_whole_project_pass(
    runner: ModuleType, tmp_path: Path
) -> None:
    """HE-NAMED-MARKDOWN: the quick check leaves the whole-project pass to the full check."""
    configure(tmp_path, [gate("suite", "pass", role="lint", parallel=True)])
    (tmp_path / "stray.md").write_text("no file names this\n")
    assert runner.check(quick=True) == 0
    with pytest.raises(ValueError, match=r"stray\.md:1 is named by no other"):
        runner.check(quick=False)


def test_one_run_reports_every_kind_and_every_hit(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a full check lists each refusal kind with every hit, so one run gives the whole work list."""
    files = {
        "a.py": HIDDEN + "z = 1  # no" + "qa\n",
        "b.py": "x = 1  # TO" + "DO later\n",
        "c.py": OLD_BLOCK,
        "notes/extra.md": "text\n",
        ".gitleaks.toml": "[allowlist]\npaths = ['a']\n[extend]\ndisabledRules = ['x']\n",
    }
    groups: list[tuple[str, list[str]]] = []
    for line in refusal(project(tmp_path, files)).splitlines():
        if line.startswith("  "):
            groups[-1][1].append(line.strip())
        else:
            groups.append((line, []))
    assert [header.split(":")[0] for header, _ in groups] == [
        "HE-NO-SWITCH-OFF",
        "HE-COMMENT-LINES",
        "HE-COMMENT-LINES",
        "HE-NAMED-MARKDOWN",
    ]
    assert [[hit.split(" ")[0] for hit in hits] for _, hits in groups] == [
        [".gitleaks.toml:1", ".gitleaks.toml:4", "a.py:2", "a.py:3"],
        ["b.py:1"],
        ["c.py:1"],
        ["notes/extra.md:1"],
    ]


def test_a_marker_before_a_second_comment_on_the_same_line_fails(
    tmp_path: Path,
) -> None:
    """HE-COMMENT-LINES: a marker in one comment fails when another comment follows it on the line."""
    root = project(
        tmp_path, {"a.ts": "const a = 1; /* TODO fix */ /* explanation */\n"}
    )
    assert "a.ts:1 holds a TODO marker" in refusal(root)


FIXED_NAME_FILES = [
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SUPPORT.md",
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "CODEOWNERS.md",
    "LICENSE.md",
    "NOTICE.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/SECURITY.md",
    "pkg/contributing.md",
]


def test_files_that_a_tool_opens_by_its_fixed_name_or_path_pass(
    tmp_path: Path,
) -> None:
    """HE-NAMED-MARKDOWN: a contributing guide and a pull request template need no link."""
    files = dict.fromkeys(FIXED_NAME_FILES, "text\n")
    validate_whole_project(project(tmp_path, files))
    message = refusal(project(tmp_path / "other", {"docs/guide.md": "text\n"}))
    assert "docs/guide.md:1 is named by no other tracked file" in message


def test_the_markdown_entry_points_to_the_list_and_does_not_copy_it() -> None:
    """HE-NAMED-MARKDOWN: the skipped names live in one constant; the entry names it and copies none."""
    entry = registry_entries(SOURCE)[0]["HE-NAMED-MARKDOWN"][1]
    assert "NEEDS_NO_LINK" in entry
    assert ".hooks/whole_project.py" in entry
    prose = entry.replace(".hooks/whole_project.py", "").lower()
    copied = [
        word
        for word in (*NEEDS_NO_LINK, *NEEDS_NO_LINK_FOLDERS)
        if word.lower() in prose
    ]
    assert copied == []
