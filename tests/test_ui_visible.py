"""Which changes count as visible, with the whole file (ship) and with a patch only (CI)."""

import pytest
from ui_proof import Change, is_visible

GENERICS = [
    "+const byAmount = <T extends { paise: number }>(",
    "+async <TSuccess extends string | undefined>({",
    '+export const rows = "<VOUCHER code=\\"x\\">"',
    "-const a: Map<string, number> = new Map()",
]
MARKUP = [
    "-<button @click=${this.no}>Decline</button>",
    "+return html`<p>Hello</p>`",
]


@pytest.mark.parametrize("line", GENERICS)
def test_typescript_generics_and_xml_strings_are_not_screen_markup(line: str) -> None:
    assert not is_visible(Change("src/api.ts", line))


@pytest.mark.parametrize("line", MARKUP)
def test_a_markup_template_in_script_is_screen_markup(line: str) -> None:
    assert is_visible(Change("src/card.ts", line))


@pytest.mark.parametrize(
    ("path", "line"),
    [
        ("app/lib/ui/card.dart", "+    color: Colors.red,"),
        ("Sources/Card.swift", "-  Text(title)\n+  Text(name)"),
    ],
    ids=["dart-addition", "swift-view-body"],
)
def test_a_patch_only_check_counts_a_native_change_as_visible(
    path: str, line: str
) -> None:
    assert is_visible(Change(path, line))
