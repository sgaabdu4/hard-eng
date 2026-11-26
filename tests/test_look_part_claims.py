"""Each part of a Fail line holds its own claim text once the answer is read: `same` takes the claim of the nearest earlier part, an empty judgement note takes the claim of the next judgement part, and a part with no claim to take is refused."""

from typing import cast

import look_answer
import look_dispute
import look_records
import pytest
from test_look_facts import answer_with, values

CLAIM = "the fill is not a token colour"
CHIPS: dict[str, object] = values(
    radii=[
        {"at": "Chip B", "px": 6, "corners": [6, 6, 6, 6], "clamped": False},
    ]
)


def line_of(*parts: str) -> str:
    return "Design system: Fail — " + "; ".join(parts) + " Fix: use a token."


def notes_of(line: str) -> list[str]:
    parts, _ = look_answer.fail_parts(line)
    return [item.note for part in parts if (item := look_answer.part_item(part)[1])]


def filled(*parts: str) -> tuple[str, str]:
    return look_answer.claimed_line(line_of(*parts))


def test_a_part_with_its_own_claim_stays_as_written() -> None:
    parts = (
        f"image-1.png: Cancel flow [judgement] {CLAIM}",
        "image-2.png: Cancel flow [judgement] same missing required asterisk",
    )
    assert filled(*parts) == (line_of(*parts), "")


@pytest.mark.parametrize("same", ["same", "Same ", "  SAME", "same.", "SAME ."])
def test_a_same_part_takes_the_note_of_the_nearest_earlier_claim(same: str) -> None:
    line, missing = filled(
        "image-1.png: Other flow [judgement] an older claim",
        f"image-4.png: Cancel flow [judgement] {CLAIM}",
        f"image-16.png: Third flow [judgement] {same}",
    )
    assert missing == ""
    assert notes_of(line) == ["an older claim", CLAIM, CLAIM]
    assert "image-16.png: Third flow [judgement] " + CLAIM in line


def test_a_filled_part_keeps_its_own_image_tag_and_element() -> None:
    line, _ = filled(
        f"image-4.png: Cancel flow [judgement] {CLAIM}",
        "image-5.png: Cancel flow [radius] same",
    )
    parts, _ = look_answer.fail_parts(line)
    item = look_answer.part_item(parts[1])[1]
    assert item is not None
    assert (item.frame, item.element, item.kind, item.note) == (
        "image-5.png",
        "Cancel flow",
        "radius",
        CLAIM,
    )


def test_empty_judgement_notes_take_the_next_judgement_claim() -> None:
    line, missing = filled(
        "image-1.png: Decline [judgement]",
        "image-2.png: Decline [judgement]",
        f"image-3.png: Decline [judgement] — {CLAIM}",
    )
    assert missing == ""
    assert notes_of(line) == [CLAIM, CLAIM, CLAIM]


def test_a_measured_item_with_an_empty_note_keeps_its_kind_default() -> None:
    parts = (
        "image-1.png: Hint [size]",
        f"image-2.png: Cancel flow [judgement] {CLAIM}",
    )
    assert filled(*parts) == (line_of(*parts), "")


def test_a_same_part_with_no_earlier_claim_is_named() -> None:
    first = "image-1.png: Cancel flow [judgement] same"
    assert filled(first)[1] == first
    measured = "image-1.png: Chip B [radius] same"
    assert filled(f"image-2.png: Other [judgement] {CLAIM}", measured)[1] == ""
    assert filled(measured)[1] == measured


def test_an_empty_note_with_no_matching_claim_keeps_its_element_text_as_the_claim() -> (
    None
):
    parts = (
        "image-1.png: the Email label lacks the required asterisk [judgement]",
        "image-2.png: Decline [judgement]",
        f"image-3.png: Other [judgement] {CLAIM}",
    )
    assert filled(*parts) == (line_of(*parts), "")


def test_an_answer_with_a_same_part_that_has_no_claim_to_take_is_refused_by_form() -> (
    None
):
    answer = answer_with("image-1.png: Cancel flow [judgement] same Fix: change it.")
    outcome, rules, _ = look_answer.judge(
        answer, ["image-1.png"], {"image-1.png": True}
    )
    assert outcome.startswith("not done: `image-1.png: Cancel flow [judgement] same`")
    assert rules == []


def test_an_answer_is_read_with_each_part_holding_its_claim() -> None:
    answer = answer_with(
        f"image-1.png: Cancel flow [judgement] {CLAIM}; "
        "image-1.png: Other flow [judgement] same. Fix: change it."
    )
    outcome, rules, _ = look_answer.judge(
        answer, ["image-1.png"], {"image-1.png": True}
    )
    assert outcome == "findings"
    line = next(rule for rule in rules if rule.startswith("Design system:"))
    assert notes_of(line) == [CLAIM, CLAIM]


def test_a_code_pass_of_the_claim_part_gives_the_same_part_the_same_verdict() -> None:
    line, _ = filled(
        "image-1.png: Chip B [radius] square corners",
        "image-2.png: Chip B [radius] same",
    )
    frames: dict[str, dict[str, object] | None] = {
        "image-1.png": CHIPS,
        "image-2.png": CHIPS,
    }
    assert look_records.decide_line(line, frames).startswith(
        "Design system: Pass — code checked: "
    )


def test_a_dispute_of_one_part_clears_no_other_image_or_element() -> None:
    line, _ = filled(
        f"image-4.png: Cancel flow [judgement] {CLAIM}",
        "image-5.png: Cancel flow [judgement] same",
        "image-16.png: Other flow [judgement] same",
        "image-2.png: Cancel flow [judgement] same",
    )
    record: dict[str, object] = {
        "rules": [line],
        "disputes": [],
        "outcome": "findings",
    }
    item = f"image-4.png: Cancel flow [judgement] {CLAIM}"
    found = look_dispute.locate(record, item)
    look_dispute.decided(record, item, found, "disproved", "measured")
    left = cast(list[str], record["rules"])[0]
    assert left.startswith("Design system: Fail — ")
    for kept in ("image-5.png", "image-16.png", "image-2.png"):
        assert kept in left
    assert "image-4.png" not in left
    assert record["outcome"] == "findings"
