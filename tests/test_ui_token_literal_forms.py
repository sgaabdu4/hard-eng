"""A literal in an email or standalone file that equals a token is allowed in each form."""

import pytest
from ui_whole import file_findings, token_values


def react_email(classes: str) -> str:
    return (
        "import { Html } from '@react-email/components';\n"
        f'export const A = () => <Html className="{classes}" />;\n'
    )


TOKENS = token_values(
    {
        "src/theme/t.css": (
            ":root {\n  --a: rgb(18, 52, 86);\n  --b: rgba(0, 0, 0, 0.5);\n"
            "  --c: hsl(210 50% 50%);\n  --d: 16px;\n  --e: oklch(0.6 0.1 200);\n}\n"
        )
    },
    ["src/**"],
)


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("emails/w.html", '<td style="color: rgb(18, 52, 86)">x</td>\n'),
        ("emails/w.html", '<td style="color: rgba(0, 0, 0, 0.5)">x</td>\n'),
        ("emails/w.html", '<td style="color: hsl(210 50% 50%)">x</td>\n'),
        ("emails/w.html", '<td style="color: oklch(0.6 0.1 200)">x</td>\n'),
        (
            "src/page.ts",
            'export const p = `<!doctype html><p style="color: rgb(18, 52, 86)">x</p>`;\n',
        ),
        (
            "emails/w.tsx",
            react_email("p-[16px]"),
        ),
        (
            "emails/w.tsx",
            react_email("bg-[rgb(18_52_86)]"),
        ),
    ],
)
def test_an_email_or_standalone_literal_that_equals_a_token_is_allowed_whatever_its_form(
    name: str, text: str
) -> None:
    """HE-UI-SOURCE: a functional colour or an arbitrary length that equals a token value is judged by value, like a hex colour."""
    assert file_findings(name, text, [], set(), TOKENS) == []


def test_an_email_literal_that_equals_no_token_is_still_one_finding() -> None:
    mail = (
        '<td style="color: rgba(0, 0, 1, 0.5)">x</td>\n'
        '<td style="color: rgb(18, 52, 86); padding: 17px">x</td>\n'
    )
    found = file_findings("emails/w.html", mail, [], set(), TOKENS)
    assert [line.split(": a ")[0] for line in found] == [
        "emails/w.html:1",
        "emails/w.html:2",
    ]
    assert "(rgba(0, 0, 1, 0.5))" in found[0]
    assert "(padding: 17px)" in found[1]
    tsx = react_email("p-[17px]")
    assert len(file_findings("emails/w.tsx", tsx, [], set(), TOKENS)) == 1
    for other in ("hsl(210 50% 51%)", "oklch(0.7 0.1 200)"):
        line = f'<td style="color: {other}">x</td>\n'
        assert len(file_findings("emails/w.html", line, [], set(), TOKENS)) == 1


def test_a_functional_colour_in_an_app_file_is_one_finding_with_the_whole_call() -> (
    None
):
    css = ".a { color: rgb(18, 52, 86); }\n"
    found = file_findings("src/a.css", css, [], set(), TOKENS)
    assert len(found) == 1
    assert "(rgb(18, 52, 86))" in found[0]
    arbitrary = 'export const A = () => <i className="bg-[rgb(1_2_3)]" />;\n'
    assert len(file_findings("src/a.tsx", arbitrary, [], set(), TOKENS)) == 1


@pytest.mark.parametrize(
    "classes",
    [
        "shadow-[0_4px_12px_rgba(255,0,0,0.5)]",
        "border-[1px_solid_rgb(255,0,0)]",
        "outline-[2px_solid_hsl(0,100%,50%)]",
        "shadow-[0_4px_12px_oklch(0.6_0.2_20)]",
    ],
)
def test_an_arbitrary_class_with_a_colour_call_after_an_underscore_is_one_finding(
    classes: str,
) -> None:
    tsx = f'export const A = () => <i className="{classes}" />;\n'
    assert len(file_findings("src/a.tsx", tsx, [], set(), TOKENS)) == 1


@pytest.mark.parametrize(
    "classes",
    [
        "bg-[color:rgb(18_52_86)]",
        "bg-[linear-gradient(to_right,rgb(18_52_86),hsl(210_50%_50%))]",
    ],
)
def test_an_email_class_whose_colour_calls_equal_tokens_is_allowed_after_an_underscore(
    classes: str,
) -> None:
    assert file_findings("emails/w.tsx", react_email(classes), [], set(), TOKENS) == []
