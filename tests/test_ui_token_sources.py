"""The whole-project UI pass reads tokens only from the files a person writes, and names the stylesheet that mixes tokens with other rules."""

from pathlib import Path

from test_ui_single_source import build, refusal, reindex
from ui_tokens import token_facts
from whole_project import validate_whole_project


def test_a_font_property_that_is_not_a_family_adds_no_family() -> None:
    """HE-UI-SOURCE: --font-size, --font-weight, --font-style and --font-tracking values are no font family, so DESIGN.md need not list `.875rem` or `bold`; a family property still is one."""
    css = (
        "@theme {\n  --font-size-sm: .875rem;\n  --font-size-body: clamp(1rem, 2vw, 1.25rem);\n"
        "  --font-weight-bold: bold;\n  --font-style-italic: italic;\n"
        "  --font-tracking-tight: -0.02em;\n"
        '  --font-sans: "Inter", sans-serif;\n  --type-family: Georgia, serif;\n}\n'
    )
    assert token_facts([css]).families == {"Inter", "Georgia"}
    assert token_facts(["--font-display: Lora;\n"]).families == {"Lora"}


def test_a_comment_a_test_file_and_a_generated_file_define_no_token(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a colour that only a comment, a test file or a generated file defines is no project token, so a default palette class and an email literal that use it stay refused."""
    root = build(
        tmp_path, "web-fixed", ui_paths=["src/**", "emails/**"], ui_library=["src/ui/*"]
    )
    (root / "src/screens/Card.tsx").write_text(
        'export const Card = () => <p className="text-blue-500">x</p>;\n'
    )
    (root / "emails").mkdir()
    (root / "emails/welcome.html").write_text('<p style="color: #3b82f6">x</p>\n')
    reindex(root)
    assert "(text-blue-500)" in refusal(root)
    with (root / "src/theme/tokens.css").open("a") as tokens:
        tokens.write("/* @theme { --color-blue-500: #3b82f6; } */\n")
    message = refusal(root)
    assert "(text-blue-500)" in message
    assert "emails/welcome.html:1: a colour typed in the file (#3b82f6)" in message
    (root / "tests/fixtures").mkdir(parents=True)
    (root / "tests/fixtures/theme.css").write_text(
        "@theme {\n  --color-blue-500: #3b82f6;\n}\n"
    )
    (root / "src/generated.css").write_text(
        "@theme {\n  --color-blue-500: #3b82f6;\n}\n"
    )
    (root / ".gitattributes").write_text("src/generated.css linguist-generated\n")
    message = refusal(root)
    assert "(text-blue-500)" in message
    assert "emails/welcome.html:1: a colour typed in the file (#3b82f6)" in message


def test_the_library_index_and_the_token_compare_skip_tests_and_generated_files(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: a test file or a generated file in the library folder needs no row in UI-LIBRARY.md, and a test fixture's tailwind config is not compared with DESIGN.md."""
    root = build(tmp_path, "web-fixed")
    (root / "src/ui/Button.test.tsx").write_text(
        "export const FakeButton = () => null;\n"
    )
    (root / "src/ui/Wrapper.tsx").write_text("export const Wrapper = () => null;\n")
    (root / ".gitattributes").write_text("src/ui/Wrapper.tsx linguist-generated\n")
    (root / "tests/fixtures").mkdir(parents=True)
    (root / "tests/fixtures/tailwind.config.js").write_text(
        "module.exports = { theme: { colors: { brand: '#abcdef' } } };\n"
    )
    validate_whole_project(root)
    for name in ("src/ui/Button.test.tsx", "src/ui/Wrapper.tsx"):
        (root / name).write_text(
            (root / name).read_text() + "export const Extra = () => null;\n"
        )
    validate_whole_project(root)


def test_a_mixed_stylesheet_gets_a_token_gap_line_that_says_why(tmp_path: Path) -> None:
    """HE-UI-SOURCE: a stylesheet that holds @theme tokens and other rules is no token file; the finding says why and what passes, and moving the tokens to a stylesheet of custom properties only passes."""
    root = build(tmp_path, "web-fixed")
    (root / "src/theme/tokens.css").unlink()
    (root / "src/styles").mkdir()
    (root / "src/styles/globals.css").write_text(
        "@theme {\n  --color-brand: #123456;\n  --spacing-3: 12px;\n}\n"
        ".card {\n  margin: var(--spacing-3);\n}\n"
    )
    (root / "DESIGN.md").write_text(
        "---\ncolors:\n  brand: '#123456'\nspacing:\n  s3: 12px\n---\n# Fixture\n"
    )
    message = refusal(root)
    assert "the DESIGN.md colour #123456 is missing from the token files" in message
    assert (
        "src/styles/globals.css holds @theme tokens and other rules, so it is not a token file"
        in message
    )
    assert "move the tokens to a stylesheet of custom properties only" in message
    (root / "src/styles/globals.css").write_text(
        ".card {\n  margin: var(--spacing-3);\n}\n"
    )
    (root / "src/theme/tokens.css").write_text(
        "@theme {\n  --color-brand: #123456;\n  --spacing-3: 12px;\n}\n"
    )
    reindex(root)
    validate_whole_project(root)
