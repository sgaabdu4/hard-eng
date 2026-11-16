"""The full check judges every tracked file, old code included."""

import re
import tokenize
from pathlib import Path
from types import ModuleType

import pytest
from comments import validate_rules, validate_suppressions
from conftest import SOURCE, change, commit, configure, gate, git, init
from gitleaks_entries import validate_entries
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
    """HE-NO-SWITCH-OFF: generated output and the folders Hard Eng installs stay exempt."""
    files = {
        ".gitattributes": "*.g.py linguist-generated=true\n",
        "made.g.py": HIDDEN,
        ".hooks/tool.py": HIDDEN,
        ".agents/skills/tool/run.py": HIDDEN,
        ".claude/rules/run.py": HIDDEN,
    }
    validate_whole_project(project(tmp_path, files))
    assert "app.py:2 holds" in refusal(project(tmp_path / "own", {"app.py": HIDDEN}))


def test_binary_files_are_not_read_and_crlf_lines_keep_their_numbers(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: a file Git counts as binary holds no code that a scanner reads."""
    root = project(tmp_path, {})
    (root / "logo.png").write_bytes(b"\x89PNG\0\nx = 1  # no" + b"semgrep\n")
    validate_whole_project(root)
    (root / "notes.txt").write_bytes(b"\0\nx = 1  # no" + b"semgrep\n")
    assert "notes.txt:2 holds" in refusal(root)
    (root / "notes.txt").unlink()
    (root / "lib.ts").write_bytes(b"// \xff\0\nconst a = 1; // TO" + b"DO later\n")
    assert "lib.ts:2 holds a TODO marker" in refusal(root)
    (root / "lib.ts").unlink()
    (root / "sub").mkdir()
    (root / "sub/.gitleaksignore").write_bytes(b"\xff\0\nabc:rule:1\n")
    assert "sub/.gitleaksignore:2 holds" in refusal(root)
    (root / "sub/.gitleaksignore").unlink()
    (root / "app.py").write_bytes(HIDDEN.replace("\n", "\r\n").encode())
    assert "app.py:2 holds" in refusal(root)


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


def test_a_gitleaks_config_that_drops_the_default_rules_fails(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a config without `[extend] useDefault = true` scans with its own rules alone, so it fails; the extended form passes."""
    own = "[[rules]]\nid = 'mine'\nregex = '''AKIA[A-Z0-9]{16}'''\n"
    for name, text in {
        "own": own,
        "empty": "",
        "false": "[extend]\nuseDefault = false\n",
    }.items():
        message = refusal(project(tmp_path / name, {".gitleaks.toml": text}))
        assert ".gitleaks.toml:1 drops the default rules" in message, name
    validate_whole_project(
        project(tmp_path / "kept", {".gitleaks.toml": DETECTION_ONLY})
    )


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


QUOTED_SWITCHES = [
    (
        "test/rule_test.dart",
        "const sample = r'''\n// ig" + "nore_for_file: unused_import\n''';\n",
    ),
    ("test/rule_test.dart", "const s = '// ig" + "nore: x';\n"),
    (
        "test/rule_test.dart",
        "const s = '${a ? {'k': \"'\"} : 1} // ig" + "nore: x';\n",
    ),
    ("src/rule.test.ts", "const sample = `\n// eslint-" + "disable-next-line\n`;\n"),
    ("src/a.ts", "const t = `${f('// @ts-" + "ignore')}`;\n"),
    ("scripts/scan.mjs", "const banned = /(?<!dart-)x|eslint-" + "disable/;\n"),
    (
        "tool/scan.py",
        "MARK = '# pyl" + "int: disable=x'\nRULE = f'{x} # pyright:" + " ignore'\n",
    ),
    *(
        [("tool/tpl.py", "TPL = t'{x} # pyright:" + " ignore'\n")]
        if hasattr(tokenize, "TSTRING_MIDDLE")
        else []
    ),
]


@pytest.mark.parametrize(("name", "text"), QUOTED_SWITCHES)
def test_switch_off_text_inside_a_literal_passes(
    tmp_path: Path, name: str, text: str
) -> None:
    """HE-NO-SWITCH-OFF: a tool reads no switch-off in a string or regex, so an old or added one passes."""
    root = project(tmp_path, {name: "x = 1\n"})
    (root / name).write_text(text)
    validate_suppressions(root, "HEAD")
    commit(root, "old")
    validate_whole_project(root)


QUOTED_NEAR_MISSES = [
    ("lib/a.dart", "final s = r'''x'''; // ig" + "nore: y\n", "// ig" + "nore:"),
    (
        "lib/a.dart",
        'final a = \'${b ? "\'" : ""}\'; // ig' + "nore: avoid_print\n",
        "// ig" + "nore:",
    ),
    (
        "src/a.ts",
        "const t = `${f()}`; // eslint-" + "disable-line\n",
        "eslint-" + "disable",
    ),
    ("src/a.ts", "const k = 'x gitleaks" + ":allow';\n", "gitleaks" + ":allow"),
    ("tool/scan.py", "x = '#'  # no" + "qa\n", "# no" + "qa"),
    (
        "scripts/scan.mjs",
        "const banned = /(?<!dart-)x|fallow-" + "ignore/;\n",
        "fallow-" + "ignore",
    ),
    ("tool/scan.py", "RULE = f'{x} # no" + "semgrep'\n", "no" + "semgrep"),
    ("tool/scan.py", "x = '# pragma: no " + "cover'\n", "# pragma: no " + "cover"),
    ("lib/a.dart", "const s = 'no" + "sem';\n", "no" + "sem"),
    ("lib/a.dart", "const s = 'coverage:" + "ignore-file';\n", "coverage:" + "ignore-"),
    (
        "lib/a.dart",
        "const s = '// dart-decimate-" + "ignore-file';\n",
        "// dart-decimate-" + "ignore-file",
    ),
    ("src/a.ts", "const s = '/* c8 " + "ignore next */';\n", "/* c8 " + "ignore"),
    (
        "src/a.ts",
        "const s = `v8 " + "ignore`; // v8 " + "ignore\n",
        "// v8 " + "ignore",
    ),
    (
        "src/a.jsx",
        "const a = <p>Don't {/* eslint-" + "disable-line x */}</p>;\n",
        "eslint-" + "disable",
    ),
    (
        "src/a.tsx",
        "const a = <p>`</p>; // eslint-" + "disable-line\n",
        "eslint-" + "disable",
    ),
    (
        "app/a.swift",
        'let a = #"a"b"# // swift-format-' + "ignore\n",
        "swift-format-" + "ignore",
    ),
    ("tool/scan.py", "X = '# no" + "qa'\n", "# no" + "qa"),
    ("tool/scan.py", "X = '# isort:" + " skip_file'\n", "# isort:" + " skip_file"),
    (
        "src/a.ts",
        "const r = total! / count + '/' + unit; // eslint-" + "disable-line\n",
        "eslint-" + "disable",
    ),
    (
        "src/a.ts",
        "const h = n++ / 2 + '/' + t; // eslint-" + "disable-line\n",
        "eslint-" + "disable",
    ),
    (
        "src/a.js",
        "const C = () => <p>Don't</p>; // eslint-" + "disable-line\n",
        "eslint-" + "disable",
    ),
    (
        "lib/a.dart",
        "final t = '${f('b' // ig" + "nore: argument_type_not_assignable\n)}';\n",
        "// ig" + "nore:",
    ),
    ("tool/scan.py", "X = '# pyre-" + "fixme[9]'\n", "# pyre-" + "fixme"),
    ("tool/scan.py", "X = '# type:" + " ignore'\n", "# type:" + " ignore"),
    *(
        ("src/a.ts", line + " // eslint-" + "disable-line\n", "eslint-" + "disable")
        for line in [
            "const a = o.in / 2 + `/`;",
            "const a = $in / 2 + `/`;",
            "const a = d.with(1) / 2 + `/`;",
            "const a = [.../'/.exec(s) ?? []];",
            "export default /'/.source;",
            "function f(s){return!/`/.test(s)}",
        ]
    ),
]


def test_a_division_after_a_non_null_mark_hides_no_later_line(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: `/` after a TypeScript non-null `!` divides, so the template after it closes on its line."""
    text = (
        "export const half = size! / 2 + `/${unit}`;\n// @ts-"
        + "ignore\nexport const bad: number = 's';\n"
    )
    assert "src/k1.ts:2 holds '@ts-" + "ignore'" in refusal(
        project(tmp_path, {"src/k1.ts": text})
    )


def test_a_comment_inside_a_dart_interpolation_hides_no_later_line(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: a quote inside a comment in a Dart `${...}` does not open a string, so a later switch-off still fails."""
    text = (
        "final s = '${f(1 /* don't */)}';\nint y = 'a'; // ig"
        + "nore: invalid_assignment\n"
    )
    assert "lib/k1.dart:2 holds '// ig" + "nore:'" in refusal(
        project(tmp_path, {"lib/k1.dart": text})
    )


@pytest.mark.parametrize(
    ("text", "line"),
    [
        (
            "String f(int a) {\n  return '''${a ~//*c*/ 2}''';\n}\n"
            + "int y = 'a'; // ig"
            + "nore: invalid_assignment\nconst n = '''x''';\n",
            4,
        ),
        (
            "const a = 7;\nfinal b = a ~//*c*/ 2; final t = '''\nit's\n''';\n"
            + "int y = 'a'; // ig"
            + "nore: invalid_assignment\n",
            5,
        ),
    ],
    ids=["interpolation", "code"],
)
def test_a_dart_integer_division_before_a_block_comment_hides_no_later_line(
    tmp_path: Path, text: str, line: int
) -> None:
    """HE-NO-SWITCH-OFF: Dart reads `~//*` as `~/` then a block comment, so a later switch-off still fails."""
    assert f"lib/k1.dart:{line} holds '// ig" + "nore:'" in refusal(
        project(tmp_path, {"lib/k1.dart": text})
    )


@pytest.mark.parametrize(("name", "text", "shown"), QUOTED_NEAR_MISSES)
def test_switch_off_after_a_literal_or_a_gitleaks_mark_in_one_fails(
    tmp_path: Path, name: str, text: str, shown: str
) -> None:
    """HE-NO-SWITCH-OFF: a comment after a literal still switches a check off, and Gitleaks reads its mark inside a string."""
    root = project(tmp_path, {name: text})
    assert f"{name}:1 holds {shown!r}" in refusal(root)


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
        ".gitleaks.toml": "[allowlist]\npaths = ['a']\n[extend]\nuseDefault = true\ndisabledRules = ['x']\n",
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
        [".gitleaks.toml:1", ".gitleaks.toml:5", "a.py:2", "a.py:3"],
        ["b.py:1"],
        ["c.py:1"],
        ["notes/extra.md:1"],
    ]


def test_new_findings_and_old_findings_fail_in_one_run(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a new block and a new switch-off in changed files fail in the same run as the old hits."""
    root = project(tmp_path, {"old.py": "x = 1  # TO" + "DO later\n"})
    base = git(root, "rev-parse", "HEAD")
    (root / "new.py").write_text(OLD_BLOCK + "y = 1  # no" + "qa\n")
    with pytest.raises(ValueError) as error:
        validate_rules(root, base, True, True)
    message = str(error.value)
    assert "new.py:1 holds a 2-line comment block" in message
    assert "new.py:4 " in message
    assert "old.py:1 holds a TODO marker" in message
    assert [line.split(":")[0] for line in message.splitlines() if line[0] != " "] == [
        "HE-NO-SWITCH-OFF",
        "HE-COMMENT-LINES",
        "HE-COMMENT-LINES",
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


KEY = 'token = "AKIA' + 'IOSFODNN7EXAMPLQ"\n'
RULE = "aws-access-token"


def leaky_project(tmp_path: Path, removed: bool = True) -> tuple[Path, str]:
    """A repository whose first commit holds a key that a later commit removes."""
    root = project(tmp_path, {"secret.txt": KEY})
    past = git(root, "rev-parse", "HEAD")
    if removed:
        (root / "secret.txt").unlink()
        commit(root, "remove")
    return root, past


def judged(root: Path, entry: str) -> str:
    (root / ".gitleaksignore").write_text(entry + "\n")
    try:
        validate_entries(root, 900)
    except ValueError as error:
        return str(error)
    return ""


def test_a_gitleaks_entry_for_a_past_commit_passes(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: an entry passes when today's scan finds it and the key is gone from the current files."""
    root, past = leaky_project(tmp_path)
    assert judged(root, f"{past}:secret.txt:{RULE}:1") == ""


@pytest.mark.parametrize(
    ("entry", "removed", "reason"),
    [
        (f"{{past}}:secret.txt:{RULE}:9", True, "stale"),
        (f"{{past}}:secret.txt:{RULE}:1", False, "still in the current tree"),
        (f"secret.txt:{RULE}:1", False, "is not in a linguist-generated file"),
        (f"{'a' * 40}:secret.txt:{RULE}:1", True, "commit is not in this clone"),
        ("not a fingerprint", True, "stale"),
    ],
)
def test_a_stale_or_current_gitleaks_entry_fails(
    tmp_path: Path, entry: str, removed: bool, reason: str
) -> None:
    """HE-NO-SWITCH-OFF: a stale entry, an entry whose finding is still in the files and an entry with no commit all fail."""
    root, past = leaky_project(tmp_path, removed)
    message = judged(root, entry.format(past=past))
    assert OFF in message
    assert ".gitleaksignore:1 holds" in message
    assert reason in message


def test_a_gitleaks_entry_in_a_generated_file_passes(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a `linguist-generated` file may keep its finding; a `linguist-vendored` file may not."""
    root, _ = leaky_project(tmp_path, removed=False)
    entry = f"secret.txt:{RULE}:1"
    (root / ".gitattributes").write_text("secret.txt linguist-vendored=true\n")
    assert "is not in a linguist-generated file" in judged(root, entry)
    (root / ".gitattributes").write_text("secret.txt linguist-generated=true\n")
    assert judged(root, entry) == ""


def test_the_quick_check_leaves_root_gitleaks_entries_to_the_full_check(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: the quick check runs no scan; a root entry waits for the full check and any other entry file stays refused."""
    root = project(tmp_path, {})
    base = git(root, "rev-parse", "HEAD")
    (root / ".gitleaksignore").write_text(f"abc:secret.txt:{RULE}:1\n")
    validate_suppressions(root, base)
    validate_whole_project(root)
    (root / "sub").mkdir()
    (root / "sub/.gitleaksignore").write_text(f"abc:secret.txt:{RULE}:1\n")
    with pytest.raises(ValueError, match=OFF):
        validate_suppressions(root, base)
    assert "sub/.gitleaksignore:1 holds" in refusal(root)


def test_the_full_check_judges_root_gitleaks_entries(
    runner: ModuleType, tmp_path: Path
) -> None:
    """HE-NO-SWITCH-OFF: the full check scans for each root entry once the tools are in place; the quick check runs no scan."""
    configure(tmp_path, [gate("suite", "pass", role="lint", parallel=True)])
    (tmp_path / ".gitleaksignore").write_text(f"{'a' * 40}:x.txt:{RULE}:1\n")
    assert runner.check(quick=True) == 0
    with pytest.raises(ValueError, match="commit is not in this clone"):
        runner.check(quick=False)


def test_rust_lint_attributes_are_switch_offs(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: ordinary Rust attributes pass; only the lint switch-offs fail."""
    passing = (
        "#[derive(Debug)]\n#[cfg(test)]\n#[ignored_name]\n#[test]\n"
        '#[cfg_attr(feature = "x", derive(Debug))]\nstruct A;\n'
        "fn allow(x: u8) -> u8 { x }\n"
    )
    validate_whole_project(project(tmp_path, {"src/lib.rs": passing}))


CARGO_LEVELS = {
    "string": '[lints.rust]\nunused = "allow"\n',
    "table": '[lints.clippy]\nall = { level = "allow", priority = -1 }\n',
    "workspace": '[workspace.lints.rust]\nunsafe_code = "allow"\n',
    "section": '[lints.clippy.pedantic]\nlevel = "allow"\n',
}


@pytest.mark.parametrize("form", CARGO_LEVELS)
def test_a_cargo_lint_at_allow_is_a_switch_off(tmp_path: Path, form: str) -> None:
    """HE-NO-SWITCH-OFF: a Cargo lint level of allow turns the lint off from the manifest."""
    message = refusal(project(tmp_path, {"Cargo.toml": CARGO_LEVELS[form]}))
    assert OFF in message
    assert "Cargo.toml:" in message
    assert "allow" in message


def test_cargo_lint_levels_above_allow_pass(tmp_path: Path) -> None:
    kept = '[lints.rust]\nunused = "deny"\n[lints.clippy]\nall = { level = "warn", priority = -1 }\n[lints]\nworkspace = true\n'
    validate_whole_project(project(tmp_path, {"Cargo.toml": kept}))


def test_a_rust_test_files_removed_assertions_count_in_the_balance(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: deleting assertions from a Rust test file loses them in the balance like any other test file."""
    before = "#[test]\nfn a() {\n    assert_eq!(1, 1);\n    assert!(true);\n}\n"
    root = change(tmp_path, "tests/it.rs", before, "#[test]\nfn a() {\n}\n")
    with pytest.raises(ValueError, match=r"tests lose 2 assertion lines net"):
        validate_suppressions(root, "HEAD")
