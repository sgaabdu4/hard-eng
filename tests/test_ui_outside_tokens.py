"""HE-UI-SOURCE: a CSS @import of a file outside the app is one finding at the import, not an undefined token on each class."""

from pathlib import Path

import pytest
import ui_css_imports
import ui_rules
from comments import validate_suppressions
from test_ui_rules import refused, theme_repo

OUTSIDE_TOKENS = "@theme {\n  --color-brand: #1b2a4a;\n}\n"
APP_GLOBALS = "apps/web/src/app/globals.css"


def outside_repo(tmp_path: Path, globals_css: str, tokens: dict[str, str]) -> Path:
    return theme_repo(
        tmp_path,
        "",
        "apps/web/src/Card.tsx",
        "// base\n",
        '// base\n<p className="bg-brand" />\n',
        extra={
            "apps/web/package.json": '{"name":"web"}\n',
            APP_GLOBALS: globals_css,
            **tokens,
        },
    )


def import_added_repo(
    tmp_path: Path, globals_css: str, files: dict[str, str] | None = None
) -> Path:
    """An app whose stylesheet gains the import line and nothing else."""
    return theme_repo(
        tmp_path,
        "",
        APP_GLOBALS,
        '@import "tailwindcss";\n',
        globals_css,
        extra={"apps/web/package.json": '{"name":"web"}\n', **(files or {})},
    )


def test_a_token_file_outside_the_app_is_one_finding_at_its_import(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: an @import of a CSS file outside the app is one finding at the import, not an undefined token on each class."""
    root = outside_repo(
        tmp_path,
        '@import "tailwindcss";\n@import "../../../../styles/tokens.css";\n@theme {\n  --color-local: #111;\n}\n',
        {"styles/tokens.css": OUTSIDE_TOKENS},
    )
    message = refused(root)
    assert (
        f"{APP_GLOBALS}:2: imports ../../../../styles/tokens.css from outside"
        in message
    )
    assert "inside the app's folder" in message
    assert "(bg-brand)" not in message


def test_an_import_above_the_repository_is_outside_the_app(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a token file beside the repository folder is outside the app too."""
    (tmp_path / "styles").mkdir()
    (tmp_path / "styles/tokens.css").write_text(OUTSIDE_TOKENS)
    root = theme_repo(
        tmp_path,
        '@import "../../../styles/tokens.css";\n@theme {\n  --color-local: #111;\n}\n',
        "src/Card.tsx",
        "// base\n",
        '// base\n<p className="bg-brand" />\n',
    )
    message = refused(root)
    assert (
        "src/app/globals.css:1: imports ../../../styles/tokens.css from outside"
        in message
    )
    assert "(bg-brand)" not in message


def test_an_outside_import_replaces_the_design_weight_finding_it_causes(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a changed DESIGN.md with tokens outside the app gets the import finding, not a missing-weight finding."""
    design = "---\ntypography:\n  heading:\n    fontSize: 20px\n    fontWeight: 500\n---\n# App Design\n"
    root = theme_repo(
        tmp_path,
        "",
        "apps/web/DESIGN.md",
        "# App Design\n",
        design,
        extra={
            "apps/web/package.json": '{"name":"web"}\n',
            APP_GLOBALS: '@import "../../../../styles/tokens.css";\n@theme {\n  --text-heading: 1.25rem;\n}\n',
            "styles/tokens.css": "@theme {\n  --text-heading--font-weight: 500;\n}\n",
        },
    )
    message = refused(root)
    assert f"{APP_GLOBALS}:1: imports" in message
    assert "fontWeight" not in message


@pytest.mark.parametrize(
    ("globals_css", "files"),
    [
        (
            '@import "../../../../styles/tokens.css";\n',
            {"styles/tokens.css": OUTSIDE_TOKENS},
        ),
        (
            '@import "../../../../styles/tokens.css";\n@theme {\n  --color-local: #111;\n}\n',
            {
                "styles/tokens.css": OUTSIDE_TOKENS,
                "apps/web/tailwind.config.ts": "export default {};\n",
            },
        ),
        (
            '@import "../../../../styles/base";\n',
            {"styles/base.css": "body {\n  margin: 0;\n}\n"},
        ),
    ],
    ids=["no local @theme", "tailwind config", "outside file without tokens"],
)
def test_an_outside_import_is_a_finding_whatever_the_app_theme_holds(
    tmp_path: Path, globals_css: str, files: dict[str, str]
) -> None:
    """HE-UI-SOURCE: an added import is refused with no @theme in the app, with an external theme and when the outside file holds no token."""
    message = refused(import_added_repo(tmp_path, globals_css, files))
    assert f"{APP_GLOBALS}:1: imports ../../../../styles/" in message


def test_a_relative_import_into_node_modules_is_not_outside_the_app(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a package folder inside the app's own node_modules is not another app."""
    root = import_added_repo(
        tmp_path,
        '@import "../../node_modules/ui/theme.css";\n',
        {
            "apps/web/node_modules/ui/package.json": '{"name":"ui"}\n',
            "apps/web/node_modules/ui/theme.css": OUTSIDE_TOKENS,
        },
    )
    validate_suppressions(root, "HEAD")


def test_an_old_outside_import_does_not_fail_a_class_the_app_defines(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a line that existed before the change is not flagged when the added class is valid."""
    root = theme_repo(
        tmp_path,
        "",
        "apps/web/src/Card.tsx",
        "// base\n",
        '// base\n<p className="bg-local" />\n',
        extra={
            "apps/web/package.json": '{"name":"web"}\n',
            APP_GLOBALS: '@import "../../../../styles/tokens.css";\n@theme {\n  --color-local: #111;\n}\n',
            "styles/tokens.css": OUTSIDE_TOKENS,
        },
    )
    validate_suppressions(root, "HEAD")


def test_a_generated_stylesheet_is_not_judged_for_its_import(tmp_path: Path) -> None:
    """HE-UI-SOURCE: generated files are exempt, as for every other finding."""
    root = import_added_repo(
        tmp_path,
        '@import "../../../../styles/tokens.css";\n',
        {
            "styles/tokens.css": OUTSIDE_TOKENS,
            ".gitattributes": f"{APP_GLOBALS} linguist-generated=true\n",
        },
    )
    validate_suppressions(root, "HEAD")


def test_an_import_added_to_a_token_file_is_refused(tmp_path: Path) -> None:
    """HE-UI-SOURCE: the app's own token file may not pull tokens from outside the app either."""
    root = theme_repo(
        tmp_path,
        "",
        "apps/web/src/app/tokens.css",
        OUTSIDE_TOKENS,
        '@import "../../../../styles/tokens.css";\n' + OUTSIDE_TOKENS,
        extra={
            "apps/web/package.json": '{"name":"web"}\n',
            "styles/tokens.css": OUTSIDE_TOKENS,
        },
    )
    assert "apps/web/src/app/tokens.css:1: imports" in refused(root)


def test_a_generated_import_does_not_hide_a_typo_in_authored_code(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: when the only outside import is in a generated stylesheet, an undefined token stays a finding."""
    root = theme_repo(
        tmp_path,
        "",
        "apps/web/src/Card.tsx",
        "// base\n",
        '// base\n<p className="bg-brnad" />\n',
        extra={
            "apps/web/package.json": '{"name":"web"}\n',
            APP_GLOBALS: '@import "../../../../styles/reset.css";\n@theme {\n  --color-local: #111;\n}\n',
            "styles/reset.css": "body {\n  margin: 0;\n}\n",
            ".gitattributes": f"{APP_GLOBALS} linguist-generated=true\n",
        },
    )
    message = refused(root)
    assert "(bg-brnad)" in message
    assert "from outside" not in message


def test_a_generated_import_does_not_hide_a_design_weight_mismatch(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: the DESIGN.md weight audit skips generated stylesheets for the import finding too."""
    design = "---\ntypography:\n  heading:\n    fontSize: 20px\n    fontWeight: 700\n---\n# App Design\n"
    root = theme_repo(
        tmp_path,
        "",
        "apps/web/DESIGN.md",
        "# App Design\n",
        design,
        extra={
            "apps/web/package.json": '{"name":"web"}\n',
            APP_GLOBALS: '@import "../../../../styles/reset.css";\n',
            "apps/web/src/app/theme.css": "@theme {\n  --text-heading: 1.25rem;\n  --text-heading--font-weight: 500;\n}\n",
            "styles/reset.css": "body {\n  margin: 0;\n}\n",
            ".gitattributes": f"{APP_GLOBALS} linguist-generated=true\n",
        },
    )
    message = refused(root)
    assert "fontWeight 700" in message
    assert "from outside" not in message


def test_an_unchanged_outside_import_starts_no_generated_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-UI-SOURCE: a valid class beside an old outside import starts no Git process for the import."""
    looked: list[list[str]] = []

    def lookup(_root: Path, names: list[str]) -> set[str]:
        looked.append(names)
        return set()

    monkeypatch.setattr(ui_css_imports, "generated_sources", lookup)
    root = theme_repo(
        tmp_path,
        "",
        "apps/web/src/Card.tsx",
        "// base\n",
        '// base\n<p className="bg-local" />\n',
        extra={
            "apps/web/package.json": '{"name":"web"}\n',
            APP_GLOBALS: '@import "../../../../styles/reset.css";\n@theme {\n  --color-local: #111;\n}\n',
            "styles/reset.css": "body {\n  margin: 0;\n}\n",
        },
    )
    validate_suppressions(root, "HEAD")
    assert looked == []


def test_a_token_script_change_lists_no_stylesheets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-UI-SOURCE: an exempt token file that adds no import starts no stylesheet listing."""
    listed: list[Path] = []

    def listing(root: Path) -> list[str]:
        listed.append(root)
        return []

    monkeypatch.setattr(ui_rules, "_all_css_entries", listing)
    root = theme_repo(
        tmp_path,
        "",
        "src/tokens.ts",
        "// base\n",
        "// base\nexport const a = 'bg-[#FAFAFA]';\n",
    )
    validate_suppressions(root, "HEAD")
    assert listed == []


def test_the_same_tokens_inside_the_app_pass(tmp_path: Path) -> None:
    """HE-UI-SOURCE: tokens in the app's own folder, and package imports, give no finding."""
    root = outside_repo(
        tmp_path,
        '@import "tailwindcss";\n@import "./tokens.css";\n@import "@fontsource/inter/index.css";\n',
        {"apps/web/src/app/tokens.css": OUTSIDE_TOKENS},
    )
    validate_suppressions(root, "HEAD")


def test_the_outside_import_finding_is_one_per_app_and_keeps_its_line(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: two changed files in one app give one finding, and a comment above the import does not move its line."""
    root = outside_repo(
        tmp_path,
        '/* shared\n   tokens */\n/* @import "../../../../styles/tokens.css"; */\n@import "../../../../styles/tokens.css";\n@theme {\n  --color-local: #111;\n}\n',
        {"styles/tokens.css": OUTSIDE_TOKENS},
    )
    (root / "apps/web/src/Other.tsx").write_text('<p className="text-brand" />\n')
    (root / "apps/web/src/app/globals.css").write_text(
        (root / APP_GLOBALS).read_text() + ".extra { color: red; }\n"
    )
    message = refused(root)
    assert message.count("from outside this app") == 1
    assert f"{APP_GLOBALS}:4: imports" in message
