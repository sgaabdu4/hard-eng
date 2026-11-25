"""A claim about a keyed element must be a measured item that states its claim, and code checks the claim against the fact in the claim's own direction."""

from pathlib import Path

import look_records
import pytest
from look_facts import Tokens, tokens_from_text
from test_look_facts import text_fact, tokens_of, values
from test_look_keys import ZERO_DESIGN, judged_with_keys

CHIPS = [
    {"at": "Chip A", "px": 0, "corners": [0, 0, 0, 0], "clamped": False},
    {"at": "Chip B", "px": 6, "corners": [6, 6, 6, 6], "clamped": False},
    {"at": "Chip C", "px": 6, "corners": [0, 6, 6, 0], "clamped": False},
    {"at": "Other", "px": 6, "corners": [6, 6, 6, 6], "clamped": False},
    {"at": "Odd", "px": 7, "corners": [7, 7, 7, 7], "clamped": False},
    {"at": "", "px": 0, "corners": [0, 0, 0, 0], "clamped": False},
]


def page() -> dict[str, object]:
    return values(
        texts=[
            text_fact("Header line", 14, align="start", centred=False),
            text_fact("Section title", 20, align="center", centred=True),
        ],
        radii=CHIPS,
    )


def decided(
    line: str, tokens: Tokens, measured: dict[str, object] | None = None
) -> str:
    return look_records.decide_line(line, {"image-1.png": measured or page()}, tokens)


def test_a_claim_about_a_keyed_element_must_be_a_measured_item(tmp_path: Path) -> None:
    tokens = tokens_of(tmp_path)
    refused = [
        "image-1.png: the Header line is centred [judgement] Fix: left-align it",
        "image-1.png: Header line is not centred [judgement] Fix: centre it",
        "image-1.png: Header line sits off-centre [judgement] Fix: centre it",
        "image-1.png: Chip A has square corners [judgement] Fix: round them",
        "image-1.png: Chip B looks sharp Fix: round it",
        "image-1.png: Chip A squared off [judgement] Fix: round it",
    ]
    for item in refused:
        outcome, rules = judged_with_keys(item, page(), tokens)
        assert outcome.startswith("not done: "), item
        assert "states a claim about a measured element" in outcome, item
        assert rules == [], item
    named = judged_with_keys(refused[0], page(), tokens)[0]
    assert "image-1.png: Header line [align] <note>" in named
    assert "Start the note with `centred` only when you claim" in named
    named = judged_with_keys(refused[3], page(), tokens)[0]
    assert "image-1.png: Chip A [radius] <note>" in named
    assert "Start the note with `square` only when you claim" in named
    stays = [
        "image-1.png: the page title is centred [judgement] Fix: left-align it",
        "image-1.png: Chip A are filled [judgement] Fix: outline them",
        "image-1.png: Chip B have rounded corners [judgement] Fix: square them",
        "image-1.png: Header line is bold [judgement] Fix: lighten it",
        "image-1.png: Header line [size] Fix: bigger",
        "image-1.png: a button label larger than the buttons beside it [judgement] Fix: match them",
        "image-1.png: a second filled primary button in the row [judgement] Fix: outline it",
        "image-1.png: a warning that says what will happen and no next step [judgement] Fix: add one",
        "image-1.png: unselected chips filled, the selected chip only outlined [judgement] Fix: invert",
        "image-1.png: Chip A [radius] square Fix: round them",
        "image-1.png: Header line [align] centred Fix: left-align it",
        "image-1.png: Header line [align] Fix: centre it",
        "image-1.png: Header line [align] should be centred Fix: centre it",
        "image-1.png: Header line [align] isn't centred Fix: centre it",
        "image-1.png: Odd [radius] should be square Fix: round it",
    ]
    for item in stays:
        outcome, rules = judged_with_keys(item, page(), tokens)
        assert outcome == "findings", item
        assert any(line.startswith("Design system: Fail") for line in rules), item


def test_a_centred_claim_is_checked_in_its_own_direction(tmp_path: Path) -> None:
    tokens = tokens_of(tmp_path)
    disproved = decided(
        "Alignment: Fail — image-1.png: Header line [align] centred Fix: left-align it.",
        tokens,
    )
    assert disproved.startswith("Alignment: Pass — code checked: ")
    assert "text-align start, not centred in its parent" in disproved
    stands = "Alignment: Fail — image-1.png: Section title [align] centred Fix: left-align it."
    assert decided(stands, tokens) == stands
    old_claim = decided(
        "Alignment: Fail — image-1.png: Header line [align] not centred Fix: centre it.",
        tokens,
    )
    assert old_claim.startswith("Alignment: Fail — image-1.png: Header line [align]")
    assert " — code: text-align start, not centred in its parent" in old_claim
    plain = decided(
        "Alignment: Fail — image-1.png: Header line [align] Fix: centre it.", tokens
    )
    assert " — code: text-align start, not centred in its parent" in plain
    held = decided(
        "Alignment: Fail — image-1.png: Section title [align] not centred Fix: centre it.",
        tokens,
    )
    assert held.startswith("Alignment: Pass — code checked: ")
    for note in ("should be centred", "isn't centred", "is wrongly centred"):
        sentence = decided(
            f"Alignment: Fail — image-1.png: Header line [align] {note} Fix: centre it.",
            tokens,
        )
        assert " — code: text-align start, not centred in its parent" in sentence, note
        assert "Pass" not in sentence, note


def test_a_square_claim_is_checked_against_the_corners_of_its_element(
    tmp_path: Path,
) -> None:
    tokens = tokens_of(tmp_path)
    line = (
        "Design system: Fail — image-1.png: Chip A [radius] square; "
        "image-1.png: Chip B [radius] square corners; "
        "image-1.png: Chip C [radius] square Fix: round them."
    )
    found = decided(line, tokens)
    assert (
        "Chip A [radius] — code: corner radius 0 px, square, and 0 is in no rounded token"
        in found
    )
    assert "Chip B" not in found
    assert "Chip C" not in found
    assert "Other" not in found
    allowed = decided(line, tokens_from_text(ZERO_DESIGN))
    assert allowed == (
        "Design system: Fail — image-1.png: Chip A [radius] square Fix: round them."
    )
    only_b = decided(
        "Design system: Fail — image-1.png: Chip B [radius] square Fix: round them.",
        tokens,
    )
    assert only_b.startswith("Design system: Pass — code checked: ")
    assert "corner radii 6, 6, 6, 6 px, not square" in only_b
    plain = decided(
        "Design system: Fail — image-1.png: Chip A [radius] Fix: use a token.", tokens
    )
    assert plain.startswith("Design system: Pass — code checked: ")
    assert "square, is not judged against the rounded tokens" in plain
    for note in ("should be square", "is not square", "no longer square"):
        sentence = decided(
            f"Design system: Fail — image-1.png: Odd [radius] {note} Fix: use a token.",
            tokens,
        )
        assert " — code: corner radius 7 px is not a rounded token" in sentence, note


def test_a_square_row_never_counts_as_off_token_and_is_listed_last(
    tmp_path: Path,
) -> None:
    import look_facts

    tokens = tokens_of(tmp_path)
    listed = look_facts.measured_text(page(), tokens).splitlines()
    coverage = next(line for line in listed if line.startswith("radius: "))
    assert coverage == (
        "radius: checked for all 4 corner radii against 2 rounded tokens: "
        "1 outside them; 1 square, judged only by a claim that the corners are square"
    )
    rows = [line for line in listed if line.startswith("- ") and "px" in line]
    radius_rows = rows[rows.index("- Odd: 7 px") :]
    assert radius_rows[-1] == "- Chip A: 0 px (square)"
    assert not any(line.startswith("- no name: 0 px") for line in listed)
    keys = look_facts.item_keys(page(), tokens)["radius"]
    assert "Chip A" in keys
    assert "no name" not in keys
    off = look_facts.verdict("radius", "Chip A", page(), tokens)
    assert off is not None
    assert off[0] is True


@pytest.mark.parametrize(
    "row",
    [
        {"at": "Go", "px": 0, "corners": [0, 0, 0, 0], "clamped": False},
        {"at": "Go", "px": 0, "clamped": False},
    ],
)
def test_a_square_control_adds_no_token_fault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: dict[str, object]
) -> None:
    import look

    (tmp_path / "DESIGN.md").write_text(
        "---\nrounded:\n  sm: 4px\n  md: 6px\n---\n# Design\n"
    )
    measured = values(radii=[row, {"at": "Card", "px": 6, "clamped": False}])

    def recorded(root: Path | None, digest: str) -> dict[str, object]:
        return measured

    monkeypatch.setattr(look, "recorded_measured", recorded)
    assert look_records.token_fault(tmp_path, ["a" * 64]) == ""
