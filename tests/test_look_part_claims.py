"""Each part of a Fail line holds its own claim text once the answer is read: `same` takes the claim of the nearest earlier part, an empty judgement note takes the claim of the next judgement part, and a part with no claim to take is refused."""

from pathlib import Path
from typing import cast

import look_answer
import look_dispute
import look_records
import pytest
from conftest import commit
from look_facts import Tokens
from test_look import good_answer, install_agent, look_project, make_images, run_look
from test_look_facts import DESIGN, answer_with, text_fact, values

project = pytest.fixture(look_project)

NO_TOKENS = Tokens({}, [], [])
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
    assert look_records.decide_line(line, frames, NO_TOKENS).startswith(
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


def test_a_same_chain_takes_the_claim_through_each_neighbour_with_any_element() -> None:
    line, missing = filled(
        f"image-4.png: Cancel flow [judgement] {CLAIM}",
        "image-5.png: Cancel flow [judgement] same",
        "image-6.png: Cancel flow [judgement] same",
        "image-16.png: Cancel 2 sessions and take lea [judgement] same",
    )
    assert missing == ""
    assert notes_of(line) == [CLAIM, CLAIM, CLAIM, CLAIM]


def test_a_note_that_is_only_a_closing_period_is_empty() -> None:
    parts = (
        "image-1.png: banner text [judgement]",
        "image-2.png: banner text [judgement].",
    )
    line = line_of(*parts)
    assert look_answer.claimed_line(line) == (line, "")
    both, missing = look_answer.claimed_line(
        f"Design system: Fail — image-1.png: Decline [judgement].; "
        f"image-2.png: Decline [judgement] — {CLAIM}. Fix: use a token."
    )
    assert missing == ""
    assert notes_of(both)[0] == CLAIM


def test_a_same_part_after_an_empty_part_that_ends_in_a_period_has_no_claim() -> None:
    line = (
        "Design system: Fail — image-1.png: Cancel flow [judgement].; "
        "image-2.png: Cancel flow [judgement] same. Fix: change it."
    )
    assert look_answer.claimed_line(line)[1] == (
        "image-2.png: Cancel flow [judgement] same."
    )


def test_a_same_part_does_not_skip_an_empty_part_before_it() -> None:
    skipped = filled(
        "image-1.png: Header [align] centred",
        "image-1.png: Subtitle [align]",
        "image-2.png: Subtitle [align] same",
    )
    assert skipped[1] == "image-2.png: Subtitle [align] same"
    other = filled(
        "image-1.png: Order card [radius] square corners",
        "image-1.png: filled Reject buttons [judgement]",
        "image-2.png: filled Reject buttons [judgement] same",
    )
    assert other[1] == "image-2.png: filled Reject buttons [judgement] same"


def read(fail: str, keys: dict[str, frozenset[str]]) -> str:
    outcome, _, _ = look_answer.judge(
        answer_with(f"{fail} Fix: change it."),
        ["image-1.png"],
        {"image-1.png": True},
        keys={"image-1.png": keys},
    )
    return outcome


def test_a_copied_number_in_a_judgement_part_is_refused_after_the_fill() -> None:
    outcome = read(
        "image-1.png: Chip B [radius] 2 px; image-1.png: Other chip [judgement] same",
        {"radius": frozenset({"Chip B"})},
    )
    assert outcome.startswith("not done: ")


def test_a_copied_claim_word_on_a_keyed_element_is_refused_after_the_fill() -> None:
    keys = {"radius": frozenset({"Chip B"})}
    same = read(
        "image-1.png: Chip B [radius] square corners; "
        "image-1.png: Chip B [judgement] same",
        keys,
    )
    assert same.startswith("not done: ")
    forward = read(
        "image-1.png: Chip B [judgement]; image-1.png: Chip B [judgement] — square corners",
        keys,
    )
    assert forward.startswith("not done: ")


def test_a_measured_part_after_an_empty_judgement_part_gives_it_no_claim() -> None:
    parts = (
        "image-1.png: Cancel [judgement]",
        "image-1.png: Cancel [radius] square corners",
    )
    assert filled(*parts) == (line_of(*parts), "")


MANY = ["image-1.png", "image-2.png", "image-3.png"]
ONE_PER_IMAGE = "write one item per image, with its image name first"


def read_many(fail: str) -> str:
    answer = answer_with(f"{fail} Fix: change it.").replace(
        "VERDICT", "Image image-2.png: a card\nImage image-3.png: a card\nVERDICT"
    )
    outcome, _, _ = look_answer.judge(answer, MANY, dict.fromkeys(MANY, True))
    return outcome


@pytest.mark.parametrize(
    "fail",
    [
        "image-1.png, image-2.png: Save [size] too small",
        "The fill is off. image-1.png, image-2.png: Cancel flow [judgement] off palette",
        "image-1.png, image-2.png, and image-3.png: Save [size] too small",
        "1. image-1.png, image-2.png: Cancel flow [judgement] off palette",
        "see image-1.png, then image-2.png: Save [size] x",
        "image-1.png: Cancel flow [judgement] the same as on image-2.png",
        "Compare image-1.png. image-2.png: Save [size] x",
        "image-1.png: Chip A [radius] square corners. image-2.png, image-3.png: Chip B [radius] square corners",
    ],
)
def test_an_item_that_names_more_than_one_image_is_refused(fail: str) -> None:
    outcome = read_many(fail)
    assert outcome.startswith("not done: `")
    assert ONE_PER_IMAGE in outcome or "join items with `;`" in outcome


def test_one_item_for_each_image_is_accepted() -> None:
    outcome = read_many(
        "image-1.png: Save [size] too small; image-2.png: Save [size] too small; "
        "image-3.png: Cancel flow [judgement] off palette"
    )
    assert ONE_PER_IMAGE not in outcome


def test_a_refused_run_is_not_kept_and_a_rerun_can_pass(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "design")
    images = make_images(project, 1)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=values())
    bad = "image-1.png, image-2.png: Cancel flow [judgement] x Fix: change it."
    install_agent(tmp_path, "claude", 1, answer_with(bad))
    assert str(run_look(project, "codex", images)["outcome"]).startswith("not done")
    install_agent(tmp_path, "claude", 1, good_answer(1))
    assert run_look(project, "codex", images)["outcome"] == "clean"


def read_one(fail: str, keys: dict[str, frozenset[str]] | None = None) -> str:
    outcome, _, _ = look_answer.judge(
        answer_with(f"{fail} Fix: change it."),
        ["image-1.png"],
        {"image-1.png": True},
        keys={"image-1.png": keys} if keys is not None else None,
    )
    return outcome


@pytest.mark.parametrize(
    "fail",
    [
        "image-1.png: Cancel flow [judgement] off palette. image-1.png: Other [judgement] x",
        "1. image-1.png: Cancel flow [judgement] off palette 2. image-1.png: Other [judgement] x",
        "image-1.png: Chip B [radius] square corners image-1.png: Chip B [radius] same",
    ],
)
def test_a_piece_that_holds_more_than_one_item_is_refused(fail: str) -> None:
    outcome = read_one(fail)
    assert outcome.startswith("not done: `")
    assert "join items with `;`" in outcome


def test_a_trailing_number_in_a_note_stays_in_the_part() -> None:
    line = (
        "Spacing: Fail — image-1.png: Round [weight] bolder than 5; "
        "image-2.png: Round [weight] bolder than 5 Fix: match the weights."
    )
    assert notes_of(line) == ["bolder than 5", "bolder than 5"]
    page = values(
        texts=[
            text_fact("Round", 12, weight=600),
            text_fact("5", 12, weight=600),
        ]
    )
    frames: dict[str, dict[str, object] | None] = {
        "image-1.png": page,
        "image-2.png": page,
    }
    assert look_records.decide_line(line, frames, NO_TOKENS).startswith(
        "Spacing: Pass — code checked: "
    )


def test_a_dispute_matches_the_stored_text_of_an_item_that_ends_in_a_number() -> None:
    line = (
        "Design system: Fail — image-1.png: Cancel flow [judgement] wrong in step 2.; "
        "image-2.png: Other flow [judgement] off palette Fix: fix both."
    )
    assert notes_of(line) == ["wrong in step 2.", "off palette"]
    record: dict[str, object] = {"rules": [line], "disputes": [], "outcome": "findings"}
    item = "image-1.png: Cancel flow [judgement] wrong in step 2."
    look_dispute.decided(
        record, item, look_dispute.locate(record, item), "disproved", "measured"
    )
    assert cast(list[str], record["rules"])[0] == (
        "Design system: Fail — image-2.png: Other flow [judgement] off palette Fix: fix both."
    )


def test_an_image_name_in_the_measured_key_of_its_own_item_is_not_refused() -> None:
    keys = {"size": frozenset({"image-2.png Next"})}
    assert read_one("image-1.png: image-2.png Next [size]", keys) == "findings"


def test_the_same_image_name_in_the_note_or_in_an_unmeasured_key_is_refused() -> None:
    keys = {"size": frozenset({"image-2.png Next"})}
    in_note = read_one("image-1.png: image-2.png Next [size] as in image-2.png", keys)
    assert ONE_PER_IMAGE in in_note
    unkeyed = read_one("image-1.png: image-3.png Next [size]", keys)
    assert ONE_PER_IMAGE in unkeyed
