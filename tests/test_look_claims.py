"""A claim about a keyed element must be a measured item that states its claim, and code checks the claim against the fact in the claim's own direction."""

from pathlib import Path

import look_records
from test_look_facts import text_fact, values
from test_look_keys import judged_with_keys

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


def decided(line: str, measured: dict[str, object] | None = None) -> str:
    return look_records.decide_line(line, {"image-1.png": measured or page()})


def test_a_claim_about_a_keyed_element_must_be_a_measured_item(tmp_path: Path) -> None:
    refused = [
        "image-1.png: the Header line is centred [judgement] Fix: left-align it",
        "image-1.png: Header line is not centred [judgement] Fix: centre it",
        "image-1.png: Header line sits off-centre [judgement] Fix: centre it",
        "image-1.png: Chip A has square corners [judgement] Fix: round them",
        "image-1.png: Chip B looks sharp Fix: round it",
        "image-1.png: Chip A squared off [judgement] Fix: round it",
    ]
    for item in refused:
        outcome, rules = judged_with_keys(item, page())
        assert outcome.startswith("not done: "), item
        assert "states a claim about a measured element" in outcome, item
        assert rules == [], item
    named = judged_with_keys(refused[0], page())[0]
    assert "image-1.png: Header line [align] <note>" in named
    assert "Start the note with the claim, such as `centred`" in named
    named = judged_with_keys(refused[3], page())[0]
    assert "image-1.png: Chip A [radius] <note>" in named
    assert "Start the note with the claim, such as `square corners`" in named
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
        outcome, rules = judged_with_keys(item, page())
        assert outcome == "findings", item
        assert any(line.startswith("Design system: Fail") for line in rules), item


def test_a_centred_claim_is_checked_in_its_own_direction(tmp_path: Path) -> None:
    disproved = decided(
        "Alignment: Fail — image-1.png: Header line [align] centred Fix: left-align it.",
    )
    assert disproved.startswith("Alignment: Pass — code checked: ")
    assert "text-align start, not centred in its parent" in disproved
    stands = "Alignment: Fail — image-1.png: Section title [align] centred Fix: left-align it."
    assert decided(stands) == stands
    old_claim = decided(
        "Alignment: Fail — image-1.png: Header line [align] not centred Fix: centre it.",
    )
    assert old_claim.startswith("Alignment: Fail — image-1.png: Header line [align]")
    assert " — code: text-align start, not centred in its parent" in old_claim
    plain = decided(
        "Alignment: Fail — image-1.png: Header line [align] Fix: centre it."
    )
    assert " — code: text-align start, not centred in its parent" in plain
    held = decided(
        "Alignment: Fail — image-1.png: Section title [align] not centred Fix: centre it.",
    )
    assert held.startswith("Alignment: Pass — code checked: ")
    phrase = decided(
        "Alignment: Fail — image-1.png: Header line [align] the header line is centred Fix: left-align it.",
    )
    assert phrase.startswith("Alignment: Pass — code checked: ")
    for note in (
        "should be centred",
        "isn't centred",
        "is not centred",
        "but not centred",
    ):
        sentence = decided(
            f"Alignment: Fail — image-1.png: Header line [align] {note} Fix: centre it.",
        )
        assert " — code: text-align start, not centred in its parent" in sentence, note
        assert "Pass" not in sentence, note


GAPS = values(
    gaps=[
        {"at": "Week", "to": "Month", "px": 0, "axis": "x"},
        {"at": "Month", "to": "Year", "px": 8, "axis": "x"},
        {"at": "Year", "to": "Spare", "px": 11, "axis": "x"},
    ]
)


def test_a_touch_claim_is_checked_against_the_gap_of_its_pair(tmp_path: Path) -> None:
    stands = (
        "Spacing: Fail — image-1.png: Week to Month [gap] chips touch Fix: space them."
    )
    assert decided(stands, GAPS) == stands
    apart = decided(
        "Spacing: Fail — image-1.png: Month to Year [gap] chips touch Fix: join them.",
        GAPS,
    )
    assert apart.startswith("Spacing: Pass — code checked: ")
    assert "gap 8 px, the neighbours do not touch" in apart
    for note in ("the chips touch", "touching"):
        found = decided(
            f"Spacing: Fail — image-1.png: Month to Year [gap] {note} Fix: join them.",
            GAPS,
        )
        assert found.startswith("Spacing: Pass — code checked: "), note
    for note in ("should touch", "don't touch", "not touching", ""):
        kept = decided(
            f"Spacing: Fail — image-1.png: Year to Spare [gap] {note} Fix: use a token.",
            GAPS,
        )
        assert " — code:" not in kept, note
        assert "Pass" not in kept, note
    refused = judged_with_keys(
        "image-1.png: the chips of Week to Month touch [judgement] Fix: space them",
        GAPS,
    )
    assert refused[0].startswith("not done: "), refused
    assert "Start the note with the claim" in refused[0]


def test_two_elements_with_one_name_get_their_own_keys_and_verdicts(
    tmp_path: Path,
) -> None:
    import look_facts

    measured = values(
        radii=[
            {"at": "Chip", "px": 0, "corners": [0, 0, 0, 0], "clamped": False},
            {"at": "Chip", "px": 6, "corners": [6, 6, 6, 6], "clamped": False},
            {"at": "Solo", "px": 6, "corners": [6, 6, 6, 6], "clamped": False},
        ],
        texts=[text_fact("Save", 10.5, under=True), text_fact("Save", 14)],
    )
    keys = look_facts.item_keys(measured)
    assert {"Chip #1", "Chip #2", "Solo"} <= keys["radius"]
    assert "Chip" not in keys["radius"]
    assert {"Save #1", "Save #2"} <= keys["size"]
    square = look_facts.verdict("radius", "Chip #1", measured, "square")
    round_ = look_facts.verdict("radius", "Chip #2", measured, "square")
    assert square is None
    assert round_ is not None
    assert round_[0] is True
    small = look_facts.verdict("size", "Save #1", measured)
    big = look_facts.verdict("size", "Save #2", measured)
    assert small is not None
    assert big is not None
    assert (small[0], big[0]) == (False, True)
    assert look_facts.verdict("size", "Save", measured) is None
    listed = look_facts.measured_text(measured)
    assert "- Save #1: 10.5 px" in listed
    assert "Chip #1" in next(
        line for line in listed.splitlines() if line.startswith("radius keys:")
    )


def test_a_square_claim_is_checked_against_the_corners_of_its_element(
    tmp_path: Path,
) -> None:
    line = (
        "Design system: Fail — image-1.png: Chip A [radius] square; "
        "image-1.png: Chip B [radius] square corners; "
        "image-1.png: Chip C [radius] square Fix: round them."
    )
    found = decided(line)
    assert found == (
        "Design system: Fail — image-1.png: Chip A [radius] square Fix: round them."
    )
    only_b = decided(
        "Design system: Fail — image-1.png: Chip B [radius] square Fix: round them.",
    )
    assert only_b.startswith("Design system: Pass — code checked: ")
    assert "corner radii 6, 6, 6, 6 px, not square" in only_b
    stays = "Design system: Fail — image-1.png: Chip A [radius] Fix: use a token."
    assert decided(stays) == stays
    for note in ("should be square", "is not square", "no longer square"):
        sentence = decided(
            f"Design system: Fail — image-1.png: Odd [radius] {note} Fix: use a token.",
        )
        assert " — code:" not in sentence, note
        assert "Pass" not in sentence, note


def test_a_square_row_has_a_key_and_no_value_row_is_listed(
    tmp_path: Path,
) -> None:
    import look_facts

    listed = look_facts.measured_text(page()).splitlines()
    coverage = next(line for line in listed if line.startswith("radius: "))
    assert coverage.startswith(
        "radius: code checks only a claim that corners are square, for "
    )
    assert not any(line.startswith("- Chip A") for line in listed)
    keys = look_facts.item_keys(page())["radius"]
    assert "Chip A" in keys
    assert "no name" not in keys
    assert look_facts.verdict("radius", "Chip A", page()) is None


def test_a_curly_apostrophe_or_off_centred_never_flips_a_claim(tmp_path: Path) -> None:
    measured = values(
        texts=[text_fact("Header line", 14, align="start", centred=False)],
        gaps=[{"at": "Year", "to": "Spare", "px": 11, "axis": "x"}],
        radii=[{"at": "Odd", "px": 7, "corners": [7, 7, 7, 7], "clamped": False}],
    )
    for rule, item in (
        ("Alignment", "Header line [align] isn’t centred"),
        ("Alignment", "Header line [align] sits off centred"),
        ("Alignment", "Header line [align] is off centered"),
        ("Spacing", "Year to Spare [gap] don’t touch"),
        ("Design system", "Odd [radius] isn’t square"),
    ):
        found = decided(f"{rule}: Fail — image-1.png: {item} Fix: change it.", measured)
        assert "Pass" not in found, item
        assert (" — code:" in found) == (rule == "Alignment"), item
