"""Code decides only whether the stated observation is true; a value that a DESIGN.md token list lacks never fails an item."""

from pathlib import Path

import look_records
import pytest
from test_look import look_project
from test_look_facts import (
    answer_with,
    look_with,
    stored_rule,
    text_fact,
    values,
)

project = pytest.fixture(look_project)

PAGE = values(
    gaps=[
        {"at": "Week", "to": "Month", "px": 0, "axis": "x"},
        {"at": "Month", "to": "Year", "px": 4, "axis": "x"},
    ],
)
OUTSIDE_THE_LISTS = values(
    texts=[
        text_fact("Body", 14, colour="ffffffff", fill="", fg="#ffffff", bg="#ffffff")
    ],
    gaps=[
        {"at": "Week", "to": "Month", "px": 0, "axis": "x"},
        {"at": "Row", "to": "Next", "px": 12, "axis": "y"},
    ],
    radii=[{"at": "Chip", "px": 7, "corners": [7, 7, 7, 7], "clamped": False}],
)


def decided(line: str) -> str:
    return look_records.decide_line(line, {"image-1.png": PAGE})


def test_a_chips_touch_claim_stands_at_0_px_and_falls_at_4_px() -> None:
    stands = (
        "Spacing: Fail — image-1.png: Week to Month [gap] chips touch Fix: space them."
    )
    assert decided(stands) == stands
    apart = decided(
        "Spacing: Fail — image-1.png: Month to Year [gap] chips touch Fix: join them."
    )
    assert apart.startswith("Spacing: Pass — code checked: ")


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


def test_a_gap_and_a_radius_outside_the_token_lists_stay_with_the_reviewer(
    tmp_path: Path, project: Path
) -> None:
    answer = answer_with(
        "image-1.png: Row to Next [gap] 12 px is not a spacing token; "
        "image-1.png: Chip [radius] 7 px is not a rounded token Fix: use a token."
    )
    record, _ = look_with(tmp_path, project, OUTSIDE_THE_LISTS, answer)
    line = stored_rule(record, "Design system")
    assert line.startswith("Design system: Fail — ")
    assert "code" not in line.partition("Fix:")[0]
    for item in ("Row to Next [gap]", "Chip [radius]"):
        assert item in line
    assert record["outcome"] == "findings"


def test_a_colour_item_outside_the_token_list_is_refused_not_decided(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    answer = answer_with(
        "image-1.png: Body [colour] white is not a colour token Fix: use a token."
    )
    look_with(tmp_path, project, OUTSIDE_THE_LISTS, answer)
    assert "or tag the item [judgement]" in capsys.readouterr().out


def test_the_facts_list_no_value_that_invites_a_token_item(
    tmp_path: Path, project: Path
) -> None:
    from test_look_proof_kinds import prompt_of

    _, log = look_with(tmp_path, project, OUTSIDE_THE_LISTS)
    facts = prompt_of(log).partition("Measured values for each image")[2]
    assert "Week to Month" in facts
    assert "no token" not in facts
    assert "12 px" not in facts
    assert "7 px" not in facts
    assert "ffffff" not in facts.lower()


def test_the_prompt_describes_no_check_against_the_token_lists(
    tmp_path: Path, project: Path
) -> None:
    from test_look_proof_kinds import prompt_of

    _, log = look_with(tmp_path, project, values(texts=[text_fact("Body")]))
    prompt = prompt_of(log)
    for stale in ("against the DESIGN.md", "against the tokens", "spacing tokens"):
        assert stale not in prompt, stale
