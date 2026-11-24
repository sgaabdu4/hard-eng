"""A look Fail line that gives a text size or a corner radius in px that the measured values of the image do not hold is refused."""

from pathlib import Path

import pytest
import ui_measure
from conftest import git
from test_look import (
    PNG,
    good_answer,
    install_agent,
    look_project,
    make_images,
    run_look,
)
from test_look_carry import findings_answer

project = pytest.fixture(look_project)

MEASURED: dict[str, object] = {
    "sizes": {"text_px": [12, 16]},
    "radii": [{"at": "badge", "px": 6}],
}


def look_with(
    tmp_path: Path, project: Path, text: str, *, measured: bool = True
) -> dict[str, object]:
    images = make_images(project, 1)
    if measured:
        ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=MEASURED)
    install_agent(tmp_path, "claude", 1, findings_answer(1, "Hierarchy", text))
    return run_look(project, "codex", images)


@pytest.mark.parametrize(
    ("text", "claimed", "held"),
    [
        ("the badge text is about 11 px", "text size 11 px", "12, 16"),
        ("the badge has corners about 4 px", "corner radius 4 px", "6"),
        ("an 11 px font on the badge", "text size 11 px", "12, 16"),
    ],
)
def test_a_fail_line_with_a_px_size_that_the_measured_values_do_not_hold_is_refused(
    tmp_path: Path, project: Path, text: str, claimed: str, held: str
) -> None:
    outcome = str(look_with(tmp_path, project, text)["outcome"])
    assert outcome.startswith("not done")
    assert claimed in outcome and held in outcome


@pytest.mark.parametrize(
    "text",
    [
        "text 12 px is too small for a label",
        "the badge has corners 6 px, too sharp for the card",
        "the badge text is about 12 px and the button is 44 px high",
        "the caption text is 12 px, under the 14 px text minimum",
        "the badge has 6 px corners but DESIGN.md sets an 8 px radius",
        "the card corners are 12 px, too round for a table row",
        "the badge corners are 6 px, not the 8 px radius in DESIGN.md",
        "the card has 12 px corners while the buttons have 6 px corners",
        "the badge has 6 px corners but the DESIGN.md radius is 8 px",
        "the button has 6 px corners instead of 8 px corners",
        "the Cancel button has 0 px corners while Save has 6 px corners",
    ],
)
def test_a_fail_line_with_a_px_size_that_the_measured_values_hold_passes_the_guard(
    tmp_path: Path, project: Path, text: str
) -> None:
    assert look_with(tmp_path, project, text)["outcome"] == "findings"


def test_a_px_guess_is_not_refused_for_an_image_with_no_measured_values(
    tmp_path: Path, project: Path
) -> None:
    record = look_with(
        tmp_path, project, "the badge text is about 11 px", measured=False
    )
    assert record["outcome"] == "findings"


def test_the_prompt_lists_an_earlier_fixed_finding_of_another_rule_and_asks_to_keep_it_true(
    tmp_path: Path, project: Path
) -> None:
    import json

    (project / ".gitignore").write_text(".hard-eng/\n")
    from conftest import commit

    commit(project, "inputs")
    images = make_images(project, 1)
    install_agent(
        tmp_path,
        "claude",
        1,
        findings_answer(1, "Design system", "use the badge token"),
    )
    run_look(project, "claude", images)
    images[0].write_bytes(PNG + b"badge uses the token")
    (project / "notes.txt").write_text("the badge is fixed\n")
    commit(project, "fix the badge")
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "claude", images)
    prompt = " ".join(json.loads(log.read_text())["argv"])
    assert "image-1.png: Design system: Fail — use the badge token" in prompt
    assert "must keep every earlier fixed finding true" in prompt
    assert git(project, "rev-parse", "HEAD").strip()[:7] in prompt
