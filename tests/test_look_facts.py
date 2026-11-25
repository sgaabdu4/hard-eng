"""look sends each element's measured facts by name, tags each Fail item with a kind, and lets code decide the measured items it finds."""

from pathlib import Path

import pytest
from conftest import commit
from test_look import good_answer, install_agent, look_project, make_images, run_look
from test_look_proof_kinds import prompt_of

project = pytest.fixture(look_project)

DESIGN = (
    "---\ncolors:\n  ink: '#1a1a1a'\n  mint: '#e6efe9'\n  glass: rgba(0, 0, 0, 0.5)\n"
    "spacing:\n  sm: 8px\n  md: 14px\nrounded:\n  sm: 4px\n  md: 6px\n---\n"
    "# Design\n\n## Overview\nPlain.\n"
)


def text_fact(name: str, px: float = 14, **extra: object) -> dict[str, object]:
    fact: dict[str, object] = {
        "at": name,
        "px": px,
        "weight": 400,
        "colour": "1a1a1aff",
        "fill": "e6efe9ff",
        "under": px < 11,
        "ratio": 11.2,
        "fg": "#1a1a1a",
        "bg": "#e6efe9",
    }
    return {**fact, **extra}


def control(name: str, w: int = 120, h: int = 44, **extra: object) -> dict[str, object]:
    floor = 44
    fact: dict[str, object] = {
        "at": name,
        "w": w,
        "h": h,
        "floor": floor,
        "under": w < floor or h < floor,
        "exempt": False,
    }
    return {**fact, **extra}


def values(**parts: object) -> dict[str, object]:
    base: dict[str, object] = {
        "texts": [],
        "gaps": [],
        "sizes": {"controls": []},
        "radii": [],
        "root_px": 16,
    }
    return {**base, **parts}


MEASURED = values(
    texts=[
        text_fact("Save", 14, weight=600),
        text_fact(
            "Hint",
            10.5,
            colour="767676ff",
            fill="",
            fg="#767676",
            bg="#ffffff",
            ratio=4.54,
        ),
    ],
    gaps=[{"at": "Save", "to": "Cancel", "px": 14, "axis": "y"}],
    sizes={"controls": [control("Save"), control("Cancel", 60, 30)]},
    radii=[{"at": "Save", "px": 6, "clamped": False}],
)


def look_with(
    tmp_path: Path,
    project: Path,
    measured: dict[str, object],
    answer: str | None = None,
) -> tuple[dict[str, object], Path]:
    import ui_measure

    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "design")
    images = make_images(project, 1)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=measured)
    log = install_agent(tmp_path, "claude", 1, answer or good_answer(1))
    return run_look(project, "codex", images), log


def test_the_prompt_names_each_element_with_its_measured_facts(
    tmp_path: Path, project: Path
) -> None:
    _, log = look_with(tmp_path, project, MEASURED)
    prompt = prompt_of(log)
    assert (
        "- Save: 14 px, weight 600, colour #1a1a1a (token ink) on #e6efe9 (token mint), contrast 11.2:1"
        in prompt
    )
    assert (
        "- Hint: 10.5 px, weight 400, colour #767676 (no token) on #ffffff (no token), contrast 4.54:1, under the 11 px floor"
        in prompt
    )
    assert "- Save: 120x44 px" in prompt
    assert "- Cancel: 60x30 px, under 44 px" in prompt
    assert "- Save to Cancel: 14 px (y)" in prompt
    assert "- Save: 6 px" in prompt
    assert "contrast 11.2:1" not in prompt.partition("Measured values")[0]


def test_the_prompt_says_what_each_check_covered(tmp_path: Path, project: Path) -> None:
    _, log = look_with(tmp_path, project, MEASURED)
    prompt = prompt_of(log)
    assert (
        "text size: checked for all 2 text elements: 1 under the 11 px floor" in prompt
    )
    assert (
        "colour: checked for all 2 text elements against 3 colour tokens: 1 outside them"
        in prompt
    )
    assert (
        "tap size: checked for all 2 controls: 1 under their floor "
        "(44 px; 24 px for a link at 1280 px and wider)" in prompt
    )
    assert (
        "gap: checked for all 1 gaps against 2 spacing tokens: 0 outside them" in prompt
    )
    assert (
        "radius: checked for all 1 corner radii against 2 rounded tokens: 0 outside them"
        in prompt
    )


def test_a_check_with_no_tokens_says_that_code_does_not_decide_it(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    images = make_images(project, 1)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=MEASURED)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    prompt = prompt_of(log)
    assert (
        "colour: no colour tokens in DESIGN.md, so code does not decide colour"
        in prompt
    )
    assert "gap: no spacing tokens in DESIGN.md, so code does not decide gaps" in prompt
    assert "text size: checked for all 2 text elements" in prompt


def test_a_long_fact_list_is_cut_by_the_stated_rule_and_counts_what_it_left_out() -> (
    None
):
    import look_facts

    many = [text_fact(f"Row {number:03d}", 14 + number % 5) for number in range(300)]
    many.append(text_fact("Tiny", 9))
    measured = values(texts=many)
    tokens = look_facts.design_tokens(None)
    first = look_facts.measured_text(measured, tokens)
    assert first == look_facts.measured_text(measured, tokens)
    listed = [line for line in first.splitlines() if line.startswith("- ")]
    assert listed[0].startswith("- Tiny: 9 px")
    assert len(listed) < 301
    assert len(first.encode()) < 4 * look_facts.FACT_BYTES
    omitted = 301 - len(listed)
    assert f"{omitted} more not listed, each at or over the 11 px floor" in first
    assert "checked for all 301 text elements: 1 under the 11 px floor" in first
