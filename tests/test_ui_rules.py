"""HE-UI-SOURCE: added UI lines hold no every-property transition and no colour literal outside a theme or token file."""

import subprocess
import sys
from pathlib import Path

import pytest
import ui_rules
from comments import UI_SUFFIXES, validate_suppressions
from conftest import SOURCE, commit, git, init

RULE = "HE-UI-SOURCE"
TRANSITION_STEP = "List the properties that change"
COLOUR_STEP = "Use a colour of the theme"


def change(tmp_path: Path, name: str, before: str, after: str) -> Path:
    root = tmp_path / "repo"
    root.parent.mkdir(exist_ok=True)
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(before)
    commit(root, "baseline")
    (root / name).write_text(after)
    return root


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
    ],
)
def test_an_added_dart_colour_literal_is_refused(tmp_path: Path, line: str) -> None:
    """HE-UI-SOURCE: a Dart colour typed in a widget file fails."""
    root = change(tmp_path, "lib/ui/card.dart", "int a = 1;\n", f"int a = 1;\n{line}\n")
    message = refused(root)
    assert "lib/ui/card.dart:2:" in message
    assert COLOUR_STEP in message


@pytest.mark.parametrize(
    "line",
    [
        "let c = Color(red: 1, green: 0, blue: 0)",
        "let c = UIColor(red: 1, green: 0, blue: 0, alpha: 1)",
        "let c = NSColor(red: 1, green: 0, blue: 0, alpha: 1)",
        "let c = #colorLiteral(red: 1, green: 0, blue: 0, alpha: 1)",
    ],
)
def test_an_added_swift_colour_literal_is_refused(tmp_path: Path, line: str) -> None:
    """HE-UI-SOURCE: a Swift colour typed in a view file fails."""
    root = change(
        tmp_path, "Sources/App/Card.swift", "let a = 1\n", f"let a = 1\n{line}\n"
    )
    message = refused(root)
    assert "Sources/App/Card.swift:2:" in message


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("lib/core/theme/app_colors.dart", "const c = Color(0xFF112233);"),
        ("lib/core/theme/app_theme.dart", "final c = Colors.red;"),
        ("src/tokens.ts", "export const a = 'bg-[#FAFAFA]';"),
        ("tailwind.config.ts", "export const a = 'bg-[#FAFAFA]';"),
        ("Sources/App/Palette.swift", "let c = Color(red: 1, green: 0, blue: 0)"),
        ("src/Colour/page.css", "a { color: #fff; } .x { @apply bg-[#fff]; }"),
    ],
)
def test_a_colour_in_a_theme_or_token_file_passes(
    tmp_path: Path, name: str, line: str
) -> None:
    root = change(tmp_path, name, "// base\n", f"// base\n{line}\n")
    validate_suppressions(root, "HEAD")


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("src/a.tsx", 'const c = <i className="transition-colors" />;'),
        ("src/a.tsx", 'const c = <i className="transition-[opacity,transform]" />;'),
        ("src/a.css", "a { transition: opacity 150ms; }"),
        ("lib/a.dart", "final c = Colors.transparent;"),
        (
            "src/a.tsx",
            'const c = <i className="bg-[url(/a.png)] grid-cols-[1fr_2fr]" />;',
        ),
        ("src/a.tsx", "// keep transition-all out of this"),
        ("src/a.css", "/* transition: all 1s */"),
        ("src/a.tsx", 'const c = <i className="text-all-caps my-transition-all" />;'),
        ("src/a.tsx", 'const c = <i className="transition-all-foo" />;'),
        ("src/a.css", "* { transition: none; }"),
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
        "a { transition: opacity 1s, all 2s; }",
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
