"""A stylesheet of custom properties stays a token file with a Tailwind reset or a SCSS comment."""

import pytest
from ui_tokens import token_facts
from ui_whole import (
    compared_token_file,
    file_findings,
    mixed_token_note,
    only_custom_properties,
    token_file,
)

RESET = "@theme {\n  --color-*: initial;\n  --color-brand: #123456;\n}\n"
SCSS_TOKENS = ":root {\n  // the brand\n  --brand: #123456;\n}\n"


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("src/styles/vars.css", RESET),
        ("src/styles/vars.css", "@theme {\n  --*: initial;\n  --spacing-2: 8px;\n}\n"),
        ("src/styles/vars.scss", SCSS_TOKENS),
    ],
)
def test_a_stylesheet_of_custom_properties_with_a_tailwind_reset_or_a_scss_comment_is_a_token_file(
    name: str, text: str
) -> None:
    """HE-UI-SOURCE: `--color-*: initial;` and a `//` line are part of a token stylesheet, so its values are compared with DESIGN.md and judged by no raw-value rule."""
    assert only_custom_properties(name, text)
    assert token_file(name, text)
    assert compared_token_file(name, text, ["src/**"])
    assert file_findings(name, text, [], set(), set()) == []
    facts = token_facts([text])
    assert facts.colours or facts.lengths
    assert (
        mixed_token_note(
            {name: text}, ["src/**"], ["x is missing from the token files"]
        )
        == []
    )


def test_a_reset_or_a_scss_comment_beside_a_real_rule_is_still_no_token_file() -> None:
    rule = ".card { color: #123456; }\n"
    assert not only_custom_properties("src/styles/app.css", RESET + rule)
    assert not only_custom_properties("src/styles/app.scss", SCSS_TOKENS + rule)
    assert not only_custom_properties(
        "src/styles/app.css", "@theme {\n  --color-*: other;\n}\n"
    )
    assert not only_custom_properties(
        "src/styles/app.css", "@theme {\n  --color-*: initial; color: red;\n}\n"
    )
    assert file_findings("src/styles/app.css", RESET + rule, [], set(), set())
