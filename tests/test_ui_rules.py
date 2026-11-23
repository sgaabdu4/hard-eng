"""HE-UI-SOURCE: added UI lines hold no every-property transition and no colour literal outside a theme or token file."""

import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest
import ui_rules
from comments import UI_MARKS, UI_SUFFIXES, validate_suppressions
from conftest import SOURCE, change, commit, git, init

RULE = "HE-UI-SOURCE"
TRANSITION_STEP = "List the properties that change"
COLOUR_STEP = "Use a colour of the theme"


def refused(root: Path) -> str:
    with pytest.raises(ValueError, match=RULE) as error:
        validate_suppressions(root, "HEAD")
    return str(error.value)


def test_an_added_transition_all_class_is_refused_with_its_step(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: the every-property Tailwind class fails with the step that ends it."""
    root = change(
        tmp_path,
        "src/Card.tsx",
        "const a = 1;\n",
        'const a = 1;\nconst c = <div className="p-2 transition-all duration-700" />;\n',
    )
    message = refused(root)
    assert "src/Card.tsx:2:" in message
    assert TRANSITION_STEP in message


@pytest.mark.parametrize(
    "line",
    [
        "a { transition:  all 200ms; }",
        "a { transition : all 200ms; }",
        "a { transition: opacity 150ms, all 300ms; }",
        'const s = {"transition" : "all 0.2s"};',
        "a { transition-property:  all; }",
    ],
)
def test_a_spaced_or_listed_transition_on_every_property_is_refused(
    tmp_path: Path, line: str
) -> None:
    """HE-UI-SOURCE: every spelling that the rule accepts reaches the rule, not only the exact marks."""
    root = change(
        tmp_path,
        "src/box.ts",
        "export const a = 1;\n",
        f"export const a = 1;\n{line}\n",
    )
    assert "src/box.ts:2:" in refused(root)


def test_an_added_css_transition_on_every_property_is_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a stylesheet or style object that transitions all properties fails."""
    root = change(
        tmp_path,
        "src/app.css",
        "a { color: red; }\n",
        "a { color: red; }\nb { transition: all 0.3s ease; }\nc { transition-property: all; }\n"
        "d { transition:all .2s; }\ne { transition-property:all; }\n",
    )
    message = refused(root)
    assert "src/app.css:2:" in message
    assert "src/app.css:3:" in message
    assert "src/app.css:4:" in message
    assert "src/app.css:5:" in message
    script = change(
        tmp_path / "s",
        "src/box.ts",
        "export const a = 1;\n",
        "export const a = 1;\nexport const s = { transition: 'all 0.2s' };\n"
        "export const t = { transitionProperty: 'all' };\n",
    )
    found = refused(script)
    assert "src/box.ts:2:" in found
    assert "src/box.ts:3:" in found


@pytest.mark.parametrize(
    "line",
    [
        '{"transition": "all 0.2s"}',
        "{'transition': 'all 0.2s'}",
    ],
)
def test_an_added_quoted_transition_key_on_every_property_is_refused(
    tmp_path: Path, line: str
) -> None:
    """HE-UI-SOURCE: a transition key in quotes reaches the check and fails."""
    root = change(
        tmp_path,
        "src/box.ts",
        "export const a = 1;\n",
        f"export const a = 1;\n{line}\n",
    )
    assert "src/box.ts:2:" in refused(root)


def test_an_added_tailwind_colour_literal_is_refused_with_its_step(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: an arbitrary Tailwind colour fails with the step that ends it."""
    forms = ["bg-[#FAFAFA]", "text-[#fff]", "bg-[#11223344]", "bg-[rgb(1,2,3)]"]
    forms += ["bg-[rgba(1,2,3,.5)]", "bg-[hsl(1,2%,3%)]", "bg-[hsla(1,2%,3%,.5)]"]
    forms += ["bg-[oklch(0.5_0.1_20)]"]
    lines = "".join(f'<div class="{form}"></div>\n' for form in forms)
    root = change(tmp_path, "src/page.html", "<p></p>\n", "<p></p>\n" + lines)
    message = refused(root)
    assert COLOUR_STEP in message
    for number in range(2, 2 + len(forms)):
        assert f"src/page.html:{number}:" in message


@pytest.mark.parametrize(
    "line",
    [
        "final c = Color(0xFF112233);",
        "final c = Colors.red;",
        "final c = Color.fromRGBO(1, 2, 3, 1);",
        "final c = Color.fromARGB(255, 1, 2, 3);",
        "final c = Color.from(alpha: 1, red: 1, green: 0, blue: 0);",
    ],
)
def test_an_added_dart_colour_literal_is_refused(tmp_path: Path, line: str) -> None:
    """HE-UI-SOURCE: a Dart colour typed in a widget file fails."""
    root = change(tmp_path, "lib/ui/card.dart", "int a = 1;\n", f"int a = 1;\n{line}\n")
    message = refused(root)
    assert "lib/ui/card.dart:2:" in message
    assert COLOUR_STEP in message


SWIFT_REFUSED = [
    "let c = Color(red: 1, green: 0, blue: 0)",
    "let c = Color(.sRGB, red: 1, green: 0, blue: 0)",
    "let c = Color(.sRGBLinear, red: 1, green: 0, blue: 0)",
    "let c = Color(.displayP3, red: 1, green: 0, blue: 0)",
    "let c = UIColor(red: 1, green: 0, blue: 0, alpha: 1)",
    "let c = NSColor(red: 1, green: 0, blue: 0, alpha: 1)",
    "let c = #colorLiteral(red: 1, green: 0, blue: 0, alpha: 1)",
]


@pytest.mark.parametrize("line", SWIFT_REFUSED)
def test_each_swift_form_that_the_rule_refuses_holds_a_mark(line: str) -> None:
    """HE-UI-SOURCE: a form that the colour pattern refuses reaches the check through a mark."""
    assert ui_rules.SWIFT_COLOUR.search(line)
    assert any(mark in line for mark in UI_MARKS)


@pytest.mark.parametrize("line", SWIFT_REFUSED)
def test_an_added_swift_colour_literal_is_refused(tmp_path: Path, line: str) -> None:
    """HE-UI-SOURCE: a Swift colour typed in a view file fails."""
    root = change(
        tmp_path, "Sources/App/Card.swift", "let a = 1\n", f"let a = 1\n{line}\n"
    )
    message = refused(root)
    assert "Sources/App/Card.swift:2:" in message


THEME_CASES = (
    Path(__file__).parents[1]
    / ".agents/skill-sources/building-flutter-apps/tool/test_fixtures/theme_paths.json"
)
COLOUR_LINES = {
    ".dart": "const c = Color(0xFF112233);",
    ".swift": "let c = Color(red: 1, green: 0, blue: 0)",
}
CLASS_COLOUR = '<i className="bg-[#fff]" />'


def theme_cases() -> list[dict[str, object]]:
    assert THEME_CASES.is_file(), (
        f"the Flutter skill submodule holds no case file at {THEME_CASES}; "
        "run `git submodule update --init`"
    )
    return json.loads(THEME_CASES.read_text())["cases"]


def judged_paths(theme: bool) -> list[str]:
    return [
        str(case["path"])
        for case in theme_cases()
        if case["theme"] is theme and str(case["path"]).endswith(UI_SUFFIXES)
    ]


def test_theme_path_cases_from_the_flutter_skill() -> None:
    """HE-UI-SOURCE: is_theme_path answers each row of the Flutter skill's case file, which the lint plugin's theme-file rule also reads."""
    cases = theme_cases()
    assert cases
    wrong = [
        str(case["path"])
        for case in cases
        if ui_rules.is_theme_path(str(case["path"])) is not case["theme"]
    ]
    assert wrong == []


def test_a_colour_in_a_theme_or_token_file_passes(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a colour typed in a file that the case file marks as theme or token is not refused."""
    names = judged_paths(True)
    assert names
    for number, name in enumerate(names):
        line = COLOUR_LINES.get(PurePosixPath(name).suffix, CLASS_COLOUR)
        root = change(tmp_path / str(number), name, "// base\n", f"// base\n{line}\n")
        validate_suppressions(root, "HEAD")


def test_a_name_that_only_holds_a_theme_word_is_still_judged(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a UI file that the case file marks as no theme file is judged, so a word inside a longer name gains no pass."""
    names = judged_paths(False)
    assert names
    for number, name in enumerate(names):
        line = COLOUR_LINES.get(PurePosixPath(name).suffix, CLASS_COLOUR)
        root = change(tmp_path / str(number), name, "// base\n", f"// base\n{line}\n")
        assert f"{name}:2:" in refused(root), name


def test_the_colour_step_names_the_paths_that_pass_as_the_code_does(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: the step text names the folder, file and config forms that the path rule accepts."""
    root = change(
        tmp_path, "src/a.tsx", "// base\n", '// base\n<i className="bg-[#fff]" />\n'
    )
    message = refused(root)
    assert "named theme, token, color, colour or palette" in message
    assert "tailwind.config" in message


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("src/a.tsx", 'const c = <i className="transition-colors" />;'),
        ("src/a.tsx", 'const c = <i className="transition-[opacity,transform]" />;'),
        ("src/a.css", "a { transition: opacity 150ms; }"),
        ("lib/a.dart", "final c = Colors.transparent;"),
        ("Sources/a.swift", "let c = Color(.systemBackground)"),
        (
            "src/a.tsx",
            'const c = <i className="bg-[url(/a.png)] grid-cols-[1fr_2fr]" />;',
        ),
        ("src/a.tsx", "// keep transition-all out of this"),
        ("src/a.css", "/* transition: all 1s */"),
        ("src/a.tsx", "{/* transition-all was here */}"),
        ("src/a.tsx", 'const c = <i className="text-all-caps my-transition-all" />;'),
        ("src/a.tsx", 'const c = <i className="transition-all-foo" />;'),
        ("src/a.css", "* { transition: none; }"),
        ("src/a.css", "a { transition: opacity 150ms; } /* not all */"),
        ("src/a.tsx", 'const c = <i className="transition-colors small" />;'),
        ("src/a.tsx", 'const c = <i className="bg-[hsl(var(--background))]" />;'),
        ("src/a.tsx", 'const c = <i className="bg-[rgb(var(--primary)/0.5)]" />;'),
        ("src/a.tsx", 'const c = <i className="text-[oklch(var(--x))]" />;'),
    ],
)
def test_allowed_lines_pass(tmp_path: Path, name: str, line: str) -> None:
    """HE-UI-SOURCE: lines that name no every-property transition and no typed colour pass."""
    root = change(tmp_path, name, "// base\n", f"// base\n{line}\n")
    validate_suppressions(root, "HEAD")


def test_an_old_line_with_a_literal_does_not_fail(tmp_path: Path) -> None:
    """HE-UI-SOURCE: only added lines are judged."""
    old = 'const a = <i className="transition-all bg-[#fff]" />;\n'
    root = change(tmp_path, "src/a.tsx", old, old + "const b = 2;\n")
    validate_suppressions(root, "HEAD")


def test_a_test_file_and_a_generated_file_are_not_judged(tmp_path: Path) -> None:
    line = 'const c = <i className="transition-all bg-[#fff]" />;\n'
    root = change(tmp_path, "src/a.test.tsx", "// base\n", "// base\n" + line)
    validate_suppressions(root, "HEAD")
    generated = change(tmp_path / "g", "src/gen.tsx", "// base\n", "// base\n" + line)
    (generated / ".gitattributes").write_text("src/gen.tsx linguist-generated\n")
    validate_suppressions(generated, "HEAD")
    owned = change(tmp_path / "o", ".claude/a.tsx", "// base\n", "// base\n" + line)
    validate_suppressions(owned, "HEAD")


def watch_lookups(monkeypatch: pytest.MonkeyPatch, looked: list[list[str]]) -> None:
    def lookup(_root: Path, names: list[str]) -> set[str]:
        looked.append(names)
        return set()

    monkeypatch.setattr(ui_rules, "generated_sources", lookup)


def ui_rules_loaded(root: Path) -> bool:
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
        "import comments\n"
        "try:\n"
        f"    comments.validate_suppressions(__import__('pathlib').Path({str(root)!r}), 'HEAD')\n"
        "except ValueError:\n"
        "    pass\n"
        "print('ui_rules' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )
    return result.stdout.strip() == "True"


@pytest.mark.parametrize(
    ("name", "line", "loaded"),
    [
        ("src/a.py", "x = 1", False),
        ("src/a.css", "a { color: red; }", False),
        ("src/a.css", "a { transition: all 1s; }", True),
        ("src/a.swift", "let c = Color(.systemBackground)", False),
        ("src/a.swift", "let c = Color(.sRGB, red: 1, green: 0, blue: 0)", True),
    ],
)
def test_a_change_with_no_ui_file_does_not_load_the_ui_rules(
    tmp_path: Path, name: str, line: str, loaded: bool
) -> None:
    root = change(tmp_path, name, "# base\n", f"# base\n{line}\n")
    assert ui_rules_loaded(root) is loaded


@pytest.mark.parametrize(
    "line",
    [
        'const c = <i className="transition-colors duration-200" />;',
        "a { transition: opacity 150ms ease-out; }",
        'const c = <i className="transition-[opacity,transform]" />;',
        "a { transition: opacity 1s, color 2s; }",
    ],
)
def test_a_common_transition_line_does_not_load_the_ui_rules(
    tmp_path: Path, line: str
) -> None:
    root = change(tmp_path, "src/a.tsx", "// base\n", f"// base\n{line}\n")
    assert ui_rules_loaded(root) is False


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("lib/core/theme/app_colors.dart", "final c = Colors.red;"),
        ("src/tokens.ts", "export const a = 'bg-[#FAFAFA]';"),
        ("src/a.test.tsx", 'const c = <i className="transition-all" />;'),
        ("lib/a_test.dart", "final c = Colors.red;"),
        (".claude/a.tsx", 'const c = <i className="transition-all" />;'),
    ],
)
def test_a_colour_in_a_theme_file_starts_no_git_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, line: str
) -> None:
    root = change(tmp_path, name, "// base\n", f"// base\n{line}\n")
    looked: list[list[str]] = []
    watch_lookups(monkeypatch, looked)
    validate_suppressions(root, "HEAD")
    assert looked == []


def test_a_candidate_file_reaches_the_generated_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = change(
        tmp_path,
        "src/a.tsx",
        "// base\n",
        '// base\n<i className="transition-all" />\n',
    )
    looked: list[list[str]] = []
    watch_lookups(monkeypatch, looked)
    refused(root)
    assert looked == [["src/a.tsx"]]


def test_no_starter_file_holds_a_line_that_the_ui_rules_refuse() -> None:
    """HE-UI-SOURCE: the starter files that new projects begin with meet the rule."""
    found: list[str] = []
    for path in sorted((SOURCE / ".agents/starters").rglob("*")):
        name = str(path.relative_to(SOURCE / ".agents/starters"))
        if path.is_file() and path.suffix in UI_SUFFIXES:
            lines = list(enumerate(path.read_text().splitlines(), 1))
            found += ui_rules.line_findings(name, lines)
    assert found == []


def test_lines_from_before_the_install_are_not_judged(tmp_path: Path) -> None:
    """HE-UI-SOURCE: an install change adds no old line; a repository with no commit judges every line, as the switch-off guard does."""
    old = 'const c = <i className="transition-all bg-[#fff]" />;\n'
    root = change(tmp_path, "src/a.tsx", old, old)
    (root / "old.py").write_text("x = 1  # no" + "qa\n")
    commit(root, "project before the install")
    git(root, "branch", "-M", "main")
    git(root, "switch", "-qc", "install")
    (root / "AGENTS.md").write_text("rules\n")
    commit(root, "Install Hard Eng")
    validate_suppressions(root, None)
    validate_suppressions(unborn(tmp_path / "fresh", "a.tsx", old), None)
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_suppressions(
            unborn(tmp_path / "other", "old.py", "x = 1  # no" + "qa\n"), None
        )


def unborn(parent: Path, name: str, text: str) -> Path:
    parent.mkdir()
    root = parent / "repo"
    init(root)
    (root / name).write_text(text)
    return root


def test_the_starting_state_of_a_new_repository_is_not_judged(tmp_path: Path) -> None:
    """HE-UI-SOURCE: when the guard compares with the empty tree, the starting files are not judged."""
    line = '<a className="hover:bg-[#383838]">Docs</a>\n'
    validate_suppressions(unborn(tmp_path / "a", "page.tsx", line), None)
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        mixed = unborn(tmp_path / "b", "page.tsx", line)
        (mixed / "old.py").write_text("x = 1  # no" + "qa\n")
        validate_suppressions(mixed, None)
    first = unborn(tmp_path / "c", "page.tsx", line)
    commit(first, "first commit")
    validate_suppressions(first, "0" * 40)


def test_the_nextjs_starter_holds_its_own_page_that_meets_the_rule() -> None:
    """HE-UI-SOURCE: the page that the nextjs flow keeps is a starter file, so the starter scan covers it."""
    page = SOURCE / ".agents/starters/nextjs/app/page.tsx"
    assert page.is_file()
    lines = list(enumerate(page.read_text().splitlines(), 1))
    assert ui_rules.line_findings("app/page.tsx", lines) == []


def test_the_first_push_of_a_new_branch_with_a_merge_base_is_judged(
    tmp_path: Path, shipping_policy: dict[str, object]
) -> None:
    """HE-UI-SOURCE: a zero base with a merge base to the remote base branch judges the added lines."""
    root = change(tmp_path, "src/a.tsx", "// base\n", "// base\n")
    git(root, "branch", "-M", "main")
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [], "shipping": shipping_policy})
    )
    commit(root, "default branch base")
    git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(root, "switch", "-qc", "task")
    (root / "src/a.tsx").write_text('// base\n<i className="transition-all" />\n')
    commit(root, "task work")
    with pytest.raises(ValueError, match=RULE):
        validate_suppressions(root, "0" * 40)


THEME_CSS = """@import "tailwindcss";
@theme {
  --color-brand: #1b2a4a;
  --color-late: #c83e2b;
  --text-display: 2.5rem;
  --background-image-hero: linear-gradient(90deg, #000, #fff);
}
@utility text-custom {
  letter-spacing: 0.02em;
}
.bg-mesh {
  background: none;
}
"""


def theme_repo(
    tmp_path: Path,
    css: str,
    name: str,
    before: str,
    after: str,
    extra: dict[str, str] | None = None,
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "repo"
    init(root)
    (root / "src/app").mkdir(parents=True)
    (root / "src/app/globals.css").write_text(css)
    for rel, content in (extra or {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    target = root / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(before)
    commit(root, "base")
    target.write_text(after)
    return root


@pytest.mark.parametrize(
    ("name", "line", "expected"),
    [
        (
            "src/Card.tsx",
            '<p className="text-danger font-medium">Late</p>',
            "text-danger",
        ),
        (
            "src/Card.tsx",
            '<div className="hover:bg-surface-elevated/80" />',
            "hover:bg-surface-elevated/80",
        ),
        (
            "src/Card.tsx",
            '<div className="border-t-danger ring-offset-missing" />',
            "border-t-danger",
        ),
        (
            "src/Card.tsx",
            '<svg className="fill-unknown stroke-missing" />',
            "fill-unknown",
        ),
        ("src/app/page.css", ".alert { @apply text-danger bg-brand; }", "text-danger"),
        ("src/ui.ts", 'export const cls = cn("text-danger bg-brand");', "text-danger"),
    ],
)
def test_undefined_tailwind_theme_token_is_refused(
    tmp_path: Path, name: str, line: str, expected: str
) -> None:
    """HE-UI-SOURCE: an added Tailwind colour utility missing from @theme fails."""
    root = theme_repo(tmp_path, THEME_CSS, name, "// base\n", f"// base\n{line}\n")
    message = refused(root)
    assert f"{name}:2:" in message
    assert expected in message


def test_multiline_apply_and_script_class_helper_refuse_undefined_tokens(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: multiline @apply blocks and multiline cn() calls are checked on added lines."""
    css_root = theme_repo(
        tmp_path / "css",
        THEME_CSS,
        "src/app/page.css",
        ".alert {\n  @apply\n    bg-brand;\n}\n",
        ".alert {\n  @apply\n    bg-brand\n    text-danger;\n}\n",
    )
    assert "src/app/page.css:4:" in refused(css_root)

    ts_root = theme_repo(
        tmp_path / "ts",
        THEME_CSS,
        "src/ui.ts",
        'export const cls = cn(\n  "bg-brand",\n);\n',
        'export const cls = cn(\n  "bg-brand",\n  "text-danger",\n);\n',
    )
    assert "src/ui.ts:3:" in refused(ts_root)

    tpl_root = theme_repo(
        tmp_path / "tpl",
        THEME_CSS,
        "src/ui.ts",
        "export const cls = cn(`\n  bg-brand\n`);\n",
        "export const cls = cn(`\n  bg-brand\n  bg-missing\n`);\n",
    )
    assert "src/ui.ts:3:" in refused(tpl_root)

    cmp_root = theme_repo(
        tmp_path / "cmp",
        THEME_CSS,
        "src/ui.ts",
        'export const cls = (v: string) => cn(\n  "bg-brand",\n);\n',
        'export const cls = (v: string) => cn(\n  v === "text-only" && "bg-brand",\n  v ===\n    "text-wrapped" && "bg-brand",\n  "bg-late" !== v && "text-brand",\n);\n',
    )
    validate_suppressions(cmp_root, "HEAD")

    tsx_code_root = theme_repo(
        tmp_path / "tsx_code",
        THEME_CSS,
        "src/Docs.tsx",
        "export const Docs = () => <code />;\n",
        "export const Docs = () => (\n  <code>{`\n  text-input\n  bg-missing\n  `}</code>\n);\n",
    )
    validate_suppressions(tsx_code_root, "HEAD")

    tsx_cls_root = theme_repo(
        tmp_path / "tsx_cls",
        THEME_CSS,
        "src/Box.tsx",
        "export const Box = () => <div />;\n",
        "export const Box = () => (\n  <div className={`\n  bg-brand\n  bg-missing\n  `} />\n);\n",
    )
    assert "src/Box.tsx:4:" in refused(tsx_cls_root)

    tsx_spread_root = theme_repo(
        tmp_path / "tsx_spread",
        THEME_CSS,
        "src/Spread.tsx",
        "export const Spread = () => <div />;\n",
        "export const Spread = () => {\n  const props = {\n    className: `\n      bg-brand\n      bg-missing\n    `,\n  };\n  return <div {...props} />;\n};\n",
    )
    assert "src/Spread.tsx:5:" in refused(tsx_spread_root)

    ts_type_root = theme_repo(
        tmp_path / "ts_type",
        THEME_CSS,
        "src/types.ts",
        "export type Empty = {};\n",
        'export type Props = {\n  className: string\n  variant: "text-only" | "icon-only"\n};\n',
    )
    validate_suppressions(ts_type_root, "HEAD")


def test_css_import_order_governs_color_reset_and_restore(tmp_path: Path) -> None:
    """HE-UI-SOURCE: imported CSS @theme blocks run in exact @import order before their importer."""
    restored = theme_repo(
        tmp_path / "restore",
        '@import "./z_reset.css";\n@import "./a_define.css";\n',
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-red-500" />\n',
        extra={
            "src/app/z_reset.css": "@theme {\n  --color-red-500: initial;\n}\n",
            "src/app/a_define.css": "@theme {\n  --color-red-500: #dc2626;\n}\n",
        },
    )
    validate_suppressions(restored, "HEAD")

    cleared = theme_repo(
        tmp_path / "clear",
        '@import "./a_define.css";\n@import "./z_reset.css";\n',
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-red-500" />\n',
        extra={
            "src/app/z_reset.css": "@theme {\n  --color-red-500: initial;\n}\n",
            "src/app/a_define.css": "@theme {\n  --color-red-500: #dc2626;\n}\n",
        },
    )
    assert "text-red-500" in refused(cleared)

    reimported = theme_repo(
        tmp_path / "reimport",
        '@import "./theme.css";\n@import "./z_reset.css";\n@import "./feature.css";\n',
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-red-500" />\n',
        extra={
            "src/app/theme.css": "@theme {\n  --color-red-500: #dc2626;\n}\n",
            "src/app/z_reset.css": "@theme {\n  --color-red-500: initial;\n}\n",
            "src/app/feature.css": '@import "./theme.css";\n',
        },
    )
    validate_suppressions(reimported, "HEAD")

    separate_builds = theme_repo(
        tmp_path / "separate",
        '@import "./reset.css";\n@theme {\n  --color-brand: #111;\n}\n',
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="bg-brand" />\n',
        extra={
            "src/app/reset.css": "@theme {\n  --color-*: initial;\n}\n",
            "src/app/widget.css": '@import "./reset.css";\n',
        },
    )
    validate_suppressions(separate_builds, "HEAD")


def test_theme_with_color_reset_refuses_default_palette_colours(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: --color-*: initial and --color-<name>: initial clear default Tailwind palette colours."""
    reset_css = "@theme {\n  --color-*: initial;\n  --color-ink: #111;\n}\n"
    root = theme_repo(
        tmp_path,
        reset_css,
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-red-500 text-white" />\n',
    )
    message = refused(root)
    assert "text-red-500" in message
    assert "text-white" in message
    allowed = theme_repo(
        tmp_path / "ok",
        reset_css,
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-ink text-transparent text-current text-inherit" />\n',
    )
    validate_suppressions(allowed, "HEAD")

    single_clear_css = (
        "@theme {\n  --color-red-500: initial;\n  --color-brand: #111;\n}\n"
    )
    single = theme_repo(
        tmp_path / "single",
        single_clear_css,
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-red-500 text-red-600" />\n',
    )
    single_msg = refused(single)
    assert "text-red-500" in single_msg
    assert "text-red-600" not in single_msg


@pytest.mark.parametrize(
    ("name", "line"),
    [
        (
            "src/Card.tsx",
            '<div className="text-brand bg-late text-display bg-hero text-custom bg-mesh" />',
        ),
        (
            "src/Card.tsx",
            '<div className="text-sm/6 text-left text-slate-600 bg-white bg-linear-to-r border-2 border-t-slate-200 ring-2 ring-offset-2 fill-none stroke-2" />',
        ),
        (
            "src/Card.tsx",
            '<input id="text-danger" name="bg-missing" data-testid={"text-input"} aria-label={ok ? "bg-a" : "text-b"} href="/api/text-missing" src="/img/bg-hero.png" />',
        ),
        ("src/Card.tsx", "const cls = `text-${tone} bg-[var(--x)] text-(--brand)`;"),
        (
            "src/app/page.css",
            ".box { box-sizing: border-box; text-align: left; border-radius: 8px; }",
        ),
        (
            "src/api.ts",
            'export const mime = "text-plain"; export const kind = "bg-worker";',
        ),
    ],
)
def test_defined_builtin_and_non_class_tailwind_tokens_pass(
    tmp_path: Path, name: str, line: str
) -> None:
    """HE-UI-SOURCE: defined @theme tokens, built-in utilities and non-class text pass."""
    root = theme_repo(tmp_path, THEME_CSS, name, "// base\n", f"// base\n{line}\n")
    validate_suppressions(root, "HEAD")


def test_packages_with_tailwind_config_or_unknown_plugin_are_skipped(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: external JS configs and third-party colour plugins produce no false positives."""
    with_config = theme_repo(
        tmp_path / "cfg",
        THEME_CSS,
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-danger" />\n',
        extra={"tailwind.config.ts": "export default {};\n"},
    )
    validate_suppressions(with_config, "HEAD")
    with_plugin = theme_repo(
        tmp_path / "plg",
        '@plugin "daisyui";\n' + THEME_CSS,
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="text-danger" />\n',
    )
    validate_suppressions(with_plugin, "HEAD")


def test_monorepo_theme_is_scoped_to_its_own_package(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a Tailwind v4 @theme block governs only its own workspace package, including root-level CSS."""
    root = tmp_path / "mono"
    init(root)
    (root / "package.json").write_text('{"name":"root"}\n')
    (root / "src").mkdir(parents=True)
    (root / "src/Root.tsx").write_text("// base\n")
    (root / "apps/web/src").mkdir(parents=True)
    (root / "apps/web/package.json").write_text('{"name":"web"}\n')
    (root / "apps/web/globals.css").write_text(THEME_CSS)
    (root / "apps/web/src/App.tsx").write_text("// base\n")
    (root / "apps/legacy/src").mkdir(parents=True)
    (root / "apps/legacy/package.json").write_text('{"name":"legacy"}\n')
    (root / "apps/legacy/src/App.tsx").write_text("// base\n")
    commit(root, "base")
    (root / "apps/legacy/src/App.tsx").write_text(
        '// base\n<p className="text-danger" />\n'
    )
    (root / "src/Root.tsx").write_text('// base\n<p className="text-danger" />\n')
    validate_suppressions(root, "HEAD")
    (root / "apps/web/src/App.tsx").write_text(
        '// base\n<p className="text-danger" />\n'
    )
    assert "apps/web/src/App.tsx:2:" in refused(root)


def test_duplicate_sibling_react_keys_are_refused_without_flagging_ternaries_or_maps(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: duplicate sibling React keys in a fragment, element or array are refused."""
    frag_dup = change(
        tmp_path / "frag",
        "src/Panel.tsx",
        "export const Panel = ({ id }: { id: string }) => <div />;\n",
        "export const Panel = ({ id, a, b }: { id: string; a: boolean; b: boolean }) => (\n"
        "  <>\n"
        "    {a && <button key={id}>Approve</button>}\n"
        "    {b && <button key={id}>Remind</button>}\n"
        "  </>\n"
        ");\n",
    )
    assert "duplicate sibling React key ({id})" in refused(frag_dup)

    direct_dup = change(
        tmp_path / "direct",
        "src/Tabs.tsx",
        "export const Tabs = () => <div />;\n",
        'export const Tabs = () => <div><span key="tab" /><span key="tab" /></div>;\n',
    )
    assert 'duplicate sibling React key ("tab")' in refused(direct_dup)

    multiline_key = change(
        tmp_path / "multiline",
        "src/Actions.tsx",
        'export const Actions = () => (\n  <div>\n    <button\n      key="save"\n    >Save</button>\n    <button\n      key="cancel"\n    >Cancel</button>\n  </div>\n);\n',
        'export const Actions = () => (\n  <div>\n    <button\n      key="save"\n    >Save</button>\n    <button\n      key="save"\n    >Cancel</button>\n  </div>\n);\n',
    )
    assert 'duplicate sibling React key ("save")' in refused(multiline_key)

    standalone_array = change(
        tmp_path / "array",
        "src/Items.tsx",
        "export const items = [];\n",
        'export const items = [<span key="row" />, <span key="row" />];\n',
    )
    assert 'duplicate sibling React key ("row")' in refused(standalone_array)

    array_ternary_dup = change(
        tmp_path / "array_ternary_dup",
        "src/ArrayTernary.tsx",
        "export const render = () => [];\n",
        'export const render = (ro: boolean) => [ro ? <span key="st" /> : <em key="st" />, <b key="st" />];\n',
    )
    assert 'duplicate sibling React key ("st")' in refused(array_ternary_dup)

    valid = change(
        tmp_path / "valid",
        "src/Valid.tsx",
        "export const Valid = () => <div />;\n",
        "export const Valid = ({ id, ok, a, b }: { id: string; ok: boolean; a: string[]; b: string[] }) => (\n"
        "  <div>\n"
        "    {ok ? <section key={id} /> : <article key={id} />}\n"
        "    {a.map((x) => <span key={x} />)}\n"
        "    {b.map((x) => <span key={x} />)}\n"
        "    <div key={`outer-${id}`}><span key={`outer-${id}`} /></div>\n"
        "  </div>\n"
        ");\n"
        'export const pick = (ro: boolean) => [ro ? <span key="status" /> : <em key="status" />];\n',
    )
    validate_suppressions(valid, "HEAD")


def test_design_md_font_weight_parity_catches_missing_theme_weight_and_unloaded_font_face(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: DESIGN.md heading fontWeight declarations require matching @theme weight tokens and @font-face coverage."""
    design_doc = (
        "---\n"
        "typography:\n"
        "  heading:\n"
        "    fontSize: 20px\n"
        "    fontWeight: 500\n"
        "---\n"
        "# App Design\n"
    )
    missing_weight = theme_repo(
        tmp_path / "missing_weight",
        "@theme {\n  --text-heading: 1.25rem;\n}\n",
        "DESIGN.md",
        "# App Design\n",
        design_doc,
    )
    assert "--text-heading--font-weight" in refused(missing_weight)

    unloaded_face = theme_repo(
        tmp_path / "unloaded_face",
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 500;\n}\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading: 1.25rem;\n  --text-heading--font-weight: 700;\n}\n',
        "DESIGN.md",
        "# App Design\n",
        design_doc.replace("500", "700"),
    )
    assert "outside loaded @font-face font-weight ranges" in refused(unloaded_face)

    matched = theme_repo(
        tmp_path / "matched",
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 700;\n}\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading: 1.25rem;\n  --text-heading--font-weight: 500;\n}\n',
        "DESIGN.md",
        "# App Design\n",
        design_doc,
    )
    validate_suppressions(matched, "HEAD")

    mismatch = theme_repo(
        tmp_path / "mismatch",
        "@theme {\n  --text-heading: 1.25rem;\n  --text-heading--font-weight: 500;\n}\n",
        "DESIGN.md",
        "# App Design\n",
        design_doc.replace("500", "700"),
    )
    assert "--text-heading--font-weight: 500" in refused(mismatch)

    multi_font = theme_repo(
        tmp_path / "multi_font",
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
        '@font-face {\n  font-family: "Merriweather";\n  font-weight: 700;\n}\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n',
        "DESIGN.md",
        "# App Design\n",
        design_doc.replace("500", "700"),
    )
    validate_suppressions(multi_font, "HEAD")


def test_design_md_weight_parity_handles_monorepo_root_and_generated_css(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: editing root DESIGN.md checks workspace CSS, and linguist-generated CSS is skipped."""
    mono = tmp_path / "mono"
    init(mono)
    (mono / "package.json").write_text('{"name":"root"}\n')
    (mono / "apps/web/src").mkdir(parents=True)
    (mono / "apps/web/package.json").write_text('{"name":"web"}\n')
    (mono / "apps/web/src/app.css").write_text(
        "@theme {\n  --text-heading: 1.25rem;\n}\n"
    )
    (mono / "DESIGN.md").write_text("# Root Design\n")
    commit(mono, "base")
    (mono / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 600\n---\n# Root Design\n"
    )
    assert "--text-heading--font-weight" in refused(mono)

    gen = tmp_path / "gen"
    init(gen)
    (gen / ".gitattributes").write_text("src/theme.css linguist-generated=true\n")
    (gen / "src").mkdir()
    (gen / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 600\n---\n# App\n"
    )
    (gen / "src/theme.css").write_text(
        "@theme {\n  --text-heading: 1.25rem;\n  --text-heading--font-weight: 600;\n}\n"
    )
    commit(gen, "base")
    (gen / "src/theme.css").write_text("@theme {\n  --text-heading: 1.25rem;\n}\n")
    validate_suppressions(gen, "HEAD")

    imp = tmp_path / "imp"
    init(imp)
    (imp / ".gitattributes").write_text("src/fonts.css linguist-generated=true\n")
    (imp / "src").mkdir()
    (imp / "src/fonts.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
    )
    (imp / "src/tokens.css").write_text(
        "@theme {\n  --text-heading: 1.25rem;\n  --text-heading--font-weight: 500;\n}\n"
    )
    (imp / "src/app.css").write_text(
        '@import "./fonts.css";\n@import "./tokens.css";\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading--font-weight: 600;\n}\n'
    )
    (imp / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 600\n---\n# App\n"
    )
    commit(imp, "base")
    (imp / "src/app.css").write_text(
        '@import "./fonts.css";\n@import "./tokens.css";\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading--font-weight: 600;\n}\n/* touch */\n'
    )
    validate_suppressions(imp, "HEAD")
    (imp / "src/app.css").write_text(
        '@import "./fonts.css";\n@import "./tokens.css";\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading--font-weight: 700;\n}\n'
    )
    assert "outside loaded @font-face font-weight ranges" in refused(imp)
