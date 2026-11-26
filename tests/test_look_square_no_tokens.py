"""A square element is no decided radius fact when DESIGN.md holds no rounded token, as a 0 px gap is none with no spacing token."""

import look_facts
import look_records
from look_facts import Tokens
from test_look_facts import values

SQUARE_BUTTON = {"at": "Save", "px": 0, "corners": [0, 0, 0, 0], "clamped": False}


def test_a_square_element_has_no_radius_key_when_no_rounded_token_exists() -> None:
    measured = values(radii=[SQUARE_BUTTON])
    none = Tokens({}, [], [])
    assert "Save" not in look_facts.item_keys(measured, none)["radius"]
    assert "(no key: judgement)" in look_facts.measured_text(measured, none)
    line = "Design system: Fail — image-1.png: Save [radius] unrounded corners break the style Fix: round Save."
    refused = look_records.decide_line(line, {"image-1.png": measured}, none)
    assert refused.startswith("Design system: Fail")


def test_a_square_element_keeps_its_key_when_a_rounded_token_exists() -> None:
    measured = values(radii=[SQUARE_BUTTON])
    tokens = Tokens({}, [], ["6px"])
    assert "Save" in look_facts.item_keys(measured, tokens)["radius"]
