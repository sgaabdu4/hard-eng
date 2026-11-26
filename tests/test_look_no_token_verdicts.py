"""Code decides only whether the stated observation is true; a value that a DESIGN.md token list lacks never fails an item."""

from pathlib import Path

import look_facts
import look_records
import pytest
from look_facts import Tokens
from test_look import look_project
from test_look_facts import (
    answer_with,
    look_with,
    stored_rule,
    text_fact,
    values,
)

project = pytest.fixture(look_project)

TOKENS = Tokens({"1a1a1aff": "ink"}, ["8px"], ["4px"])
PAGE = values(
    texts=[
        text_fact("Body", 14, colour="ffffffff", fill="", fg="#ffffff", bg="#ffffff")
    ],
    gaps=[
        {"at": "Week", "to": "Month", "px": 0, "axis": "x"},
        {"at": "Month", "to": "Year", "px": 4, "axis": "x"},
        {"at": "Row", "to": "Next", "px": 12, "axis": "y"},
    ],
    radii=[{"at": "Chip", "px": 7, "corners": [7, 7, 7, 7], "clamped": False}],
)


def decided(line: str) -> str:
    return look_records.decide_line(line, {"image-1.png": PAGE}, TOKENS)


def test_a_colour_a_gap_and_a_radius_outside_the_token_lists_stay_with_the_reviewer() -> (
    None
):
    for rule, item in (
        ("Design system", "Body [colour] white is not a colour token"),
        ("Spacing", "Row to Next [gap] 12 px is not a spacing token"),
        ("Design system", "Chip [radius] 7 px is not a rounded token"),
    ):
        line = f"{rule}: Fail — image-1.png: {item} Fix: use a token."
        assert decided(line) == line, item


def test_a_chips_touch_claim_stands_at_0_px_and_falls_at_4_px() -> None:
    stands = (
        "Spacing: Fail — image-1.png: Week to Month [gap] chips touch Fix: space them."
    )
    assert decided(stands) == stands
    apart = decided(
        "Spacing: Fail — image-1.png: Month to Year [gap] chips touch Fix: join them."
    )
    assert apart.startswith("Spacing: Pass — code checked: ")


def test_the_facts_list_no_value_that_invites_a_token_item() -> None:
    text = look_facts.measured_text(PAGE, TOKENS)
    assert "no token" not in text
    assert "12 px" not in text
    assert "7 px" not in text
    assert "ffffff" not in text.lower()
    assert "Week to Month" in text


def test_a_full_answer_keeps_judgement_items_with_no_number_as_reviewer_fails(
    tmp_path: Path, project: Path
) -> None:
    measured = values(
        texts=[text_fact("Body", 14, colour="ffffffff", fill="", fg="#ffffff")],
        gaps=[{"at": "Row", "to": "Next", "px": 12, "axis": "y"}],
    )
    answer = answer_with(
        "image-1.png: the body text colour is not in the colour tokens [judgement]; "
        "image-1.png: the title to close icon spacing is no spacing token [judgement] "
        "Fix: use a token"
    )
    record, _ = look_with(tmp_path, project, measured, answer)
    line = stored_rule(record, "Design system")
    assert line.startswith("Design system: Fail — ")
    assert "code" not in line.partition("Fix:")[0]
    for item in ("body text colour", "title to close icon spacing"):
        assert item in line
    assert record["outcome"] == "findings"


def test_a_colour_tag_is_refused_with_the_judgement_tag_named(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import ui_measure
    from test_look import install_agent, make_images, run_look

    (project / "DESIGN.md").write_text("# Design\n")
    images = make_images(project, 1)
    ui_measure.write_record(
        project, images[0], 1280, [], "/kpi", measured=values(texts=[text_fact("Body")])
    )
    install_agent(
        tmp_path,
        "claude",
        1,
        answer_with(
            "image-1.png: Body [colour] #ffffff is not a token Fix: use a token"
        ),
    )
    record = run_look(project, "codex", images)
    assert record["outcome"] != "clean"
    assert "or tag the item [judgement]" in capsys.readouterr().out
