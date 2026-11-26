"""Code checks a weight claim only against the two measured weights; a weight that differs from a neighbour is no fault by itself."""

import look_facts
import look_records
from test_look_facts import text_fact, values

PAGE = values(
    texts=[
        text_fact("Label", 14, weight=600),
        text_fact("Helper", 12, weight=400),
        text_fact("Twin", 12, weight=600),
    ]
)
FRAMES: dict[str, dict[str, object] | None] = {"image-1.png": PAGE}


def line(item: str) -> str:
    return f"Hierarchy: Fail — image-1.png: {item} Fix: change it."


def test_a_bolder_claim_passes_or_fails_on_the_two_measured_weights() -> None:
    held = look_facts.verdict("weight", "Label", PAGE, "bolder than Helper")
    assert held is None
    disproved = look_facts.verdict("weight", "Helper", PAGE, "bolder than Label")
    assert disproved is not None
    assert disproved[0] is True
    assert "400" in disproved[1] and "600" in disproved[1]
    equal = look_facts.verdict("weight", "Twin", PAGE, "bolder than Label")
    assert equal is not None and equal[0] is True


def test_a_lighter_claim_passes_or_fails_on_the_two_measured_weights() -> None:
    assert look_facts.verdict("weight", "Helper", PAGE, "lighter than Label") is None
    disproved = look_facts.verdict("weight", "Label", PAGE, "lighter than Helper")
    assert disproved is not None and disproved[0] is True


def test_a_weight_that_differs_from_the_neighbours_decides_nothing() -> None:
    for note in ("", "differs from its neighbours", "is heavier on the page"):
        assert look_facts.verdict("weight", "Helper", PAGE, note) is None
        assert look_facts.verdict("weight", "Label", PAGE, note) is None


def test_a_claim_that_names_no_measured_element_decides_nothing() -> None:
    assert look_facts.verdict("weight", "Helper", PAGE, "bolder than Nothing") is None
    assert look_facts.verdict("weight", "Helper", PAGE, "bolder than") is None


def test_a_plain_weight_item_stays_and_a_disproved_bolder_claim_passes() -> None:
    plain = line("Helper [weight] differs from its neighbours")
    assert look_records.decide_line(plain, FRAMES) == plain
    decided = look_records.decide_line(
        line("Helper [weight] bolder than Label"), FRAMES
    )
    assert decided.startswith("Hierarchy: Pass — code checked: ")


def test_the_facts_list_holds_no_weight_difference_to_copy() -> None:
    text = look_facts.measured_text(PAGE)
    assert "differs from" not in text
    assert "weight keys: " in text


def test_a_claim_names_only_the_elements_that_open_its_note() -> None:
    for note in (
        "bolder than Helper, matching Twin",
        "bolder than Helper under Twin",
        "bolder than Helper across all cards",
        "bolder than Helper label",
        "bolder than Helper twin",
    ):
        assert look_facts.verdict("weight", "Label", PAGE, note) is None, note
    for note in ("bolder than Helper and Twin", "bolder than Helper, Twin"):
        held = look_facts.verdict("weight", "Label", PAGE, note)
        assert held is not None and held[0] is True, note
