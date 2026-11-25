"""look sends each element's measured facts by name, tags each Fail item with a kind, and lets code decide the measured items it finds."""

from pathlib import Path

import pytest
from conftest import commit
from look_facts import Tokens
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


def answer_with(fail: str) -> str:
    from test_look import judged_rule_names

    lines = [
        f"- Design system: Fail — {fail}"
        if name == "Design system"
        else f"- {name}: Pass — looked at it"
        for name in judged_rule_names()
    ]
    return "\n".join([*lines, "Image image-1.png: a card", "VERDICT: findings"])


def judged(fail: str) -> tuple[str, list[str]]:
    import look_answer

    outcome, rules, _ = look_answer.judge(
        answer_with(fail), ["image-1.png"], {"image-1.png": True}
    )
    return outcome, rules


@pytest.mark.parametrize(
    "fail",
    [
        "Hint text about 11 px. image-1.png: Hint [judgement] Fix: make it bigger",
        "image-1.png: Hint is 10 px [judgement] Fix: make it bigger",
        "image-1.png: badge #7a5c5c [judgement] Fix: use a token",
        "image-1.png: Save about 13 px Fix: make it bigger",
        "image-1.png: badge #333 [judgement] Fix: use a token",
        "image-1.png: Save at 3:1 [judgement] Fix: more contrast",
        "image-1.png: Hint is 10 px [weight] Fix: make it bolder",
        "the label is 12pt; image-1.png: Hint [size] Fix: make it bigger",
    ],
)
def test_a_fail_item_with_a_number_or_a_colour_and_no_measured_tag_is_refused(
    fail: str,
) -> None:
    outcome, rules = judged(fail)
    assert outcome.startswith("not done: a Fail ")
    assert rules == []


@pytest.mark.parametrize(
    "fail",
    [
        "image-1.png: Hint [size]; image-1.png: Save [colour] Fix: use ink",
        "image-1.png: Hint is 10 px [size] Fix: make it bigger",
        "image-1.png: badge #7a5c5c [colour] Fix: use a token",
        "image-1.png: the card sits left of its title [judgement] Fix: centre it",
        "image-1.png: the card Fix: centre it",
        "image-1.png: Hint [weight] Fix: make it bolder",
        "image-1.png: Save [tap] Fix: 44 px control",
        "image-1.png: Order #1042 Reject button [judgement] Fix: outline Reject",
        "image-1.png: Invoice #12345 error banner [judgement] Fix: name the field",
    ],
)
def test_a_tagged_item_and_an_untagged_item_without_a_number_stand(fail: str) -> None:
    outcome, rules = judged(fail)
    assert outcome == "findings"
    assert any(line.startswith("Design system: Fail") for line in rules)


def test_the_prompt_lists_the_kinds_from_the_one_table(
    tmp_path: Path, project: Path
) -> None:
    import look_facts
    import ui_measure

    images = make_images(project, 1)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    prompt = prompt_of(log)
    assert set(look_facts.FACTS) == ui_measure.MEASURED_KINDS
    for kind, covers in ui_measure.ITEM_KINDS.items():
        assert f"[{kind}] {covers}" in prompt
    assert "image-N.png: <element> [<kind>]" in prompt


FAULT_AND_PASS = {
    "size": (
        "Hint",
        values(texts=[text_fact("Hint", 10.5, under=True)]),
        values(texts=[text_fact("Hint", 12)]),
    ),
    "colour": (
        "Hint",
        values(texts=[text_fact("Hint", colour="767676ff", fg="#767676")]),
        values(texts=[text_fact("Hint")]),
    ),
    "gap": (
        "Save",
        values(gaps=[{"at": "Save", "to": "Cancel", "px": 11, "axis": "y"}]),
        values(gaps=[{"at": "Save", "to": "Cancel", "px": 14, "axis": "y"}]),
    ),
    "radius": (
        "Save",
        values(radii=[{"at": "Save", "px": 7, "clamped": False}]),
        values(radii=[{"at": "Save", "px": 6, "clamped": False}]),
    ),
    "tap": (
        "Save",
        values(sizes={"controls": [control("Save", 60, 30)]}),
        values(sizes={"controls": [control("Save", 120, 44)]}),
    ),
}


def tokens_of(tmp_path: Path) -> Tokens:
    import look_facts

    (tmp_path / "DESIGN.md").write_text(DESIGN)
    return look_facts.design_tokens(tmp_path)


@pytest.mark.parametrize("kind", sorted(FAULT_AND_PASS))
def test_code_decides_each_measured_kind(kind: str, tmp_path: Path) -> None:
    import look_facts

    element, fault, held = FAULT_AND_PASS[kind]
    tokens = tokens_of(tmp_path)
    failed = look_facts.verdict(kind, f"{element} button", fault, tokens)
    passed = look_facts.verdict(kind, element, held, tokens)
    assert failed is not None
    assert failed[0] is False
    assert passed is not None
    assert passed[0] is True
    assert failed[1] != passed[1]


NEAR_MISSES: dict[str, tuple[str, str, dict[str, object]]] = {
    "an element that the record lacks": ("size", "Cancel all", MEASURED),
    "a longer name that holds the element": (
        "size",
        "Save",
        values(texts=[text_fact("Save all", 10.5, under=True)]),
    ),
    "extra words around the name": ("size", "Save button on the right", MEASURED),
    "a name of two letters": (
        "size",
        "Go",
        values(texts=[text_fact("Go", 10.5, under=True)]),
    ),
    "only a role word": ("tap", "button", MEASURED),
    "two elements with one name and two verdicts": (
        "size",
        "Hint",
        values(
            texts=[text_fact("Hint", 14), text_fact("Hint", 10.5, under=True)],
        ),
    ),
    "a clamped radius": (
        "radius",
        "Save",
        values(radii=[{"at": "Save", "px": 99, "clamped": True}]),
    ),
    "an old record with no facts": ("size", "Save", values(texts=[])),
    "an old control with no floor": (
        "tap",
        "Cancel",
        values(sizes={"controls": [{"at": "Cancel", "w": 30, "h": 30}]}),
    ),
    "an old gap with no neighbour": (
        "gap",
        "section#card",
        values(gaps=[{"at": "section#card", "gaps": [11, 11]}]),
    ),
    "an unknown kind": ("judgement", "Save", MEASURED),
}


@pytest.mark.parametrize("case", sorted(NEAR_MISSES))
def test_an_item_that_code_cannot_match_stays_with_the_reviewer(
    case: str, tmp_path: Path
) -> None:
    import look_facts

    kind, element, measured = NEAR_MISSES[case]
    assert look_facts.verdict(kind, element, measured, tokens_of(tmp_path)) is None


def test_an_item_with_no_tokens_to_judge_by_stays_with_the_reviewer(
    tmp_path: Path,
) -> None:
    import look_facts

    tokens = look_facts.design_tokens(tmp_path)
    for kind in ("colour", "gap", "radius"):
        element, fault, _ = FAULT_AND_PASS[kind]
        assert look_facts.verdict(kind, element, fault, tokens) is None
    element, fault, _ = FAULT_AND_PASS["size"]
    assert look_facts.verdict("size", element, fault, tokens) is not None


@pytest.mark.parametrize(("colour", "ok"), [("00000080", True), ("00000081", False)])
def test_a_colour_token_with_alpha_matches_the_raw_colour(
    colour: str, ok: bool, tmp_path: Path
) -> None:
    import look_facts

    measured = values(
        texts=[text_fact("Hint", colour=colour, fill="", fg="#808080", bg="#ffffff")]
    )
    found = look_facts.verdict("colour", "Hint", measured, tokens_of(tmp_path))
    assert found is not None
    assert found[0] is ok


def test_the_other_items_of_a_line_stay_and_all_passed_items_make_a_pass(
    tmp_path: Path, project: Path
) -> None:
    measured = values(
        texts=[text_fact("Save", 14), text_fact("Hint", 10.5, under=True)]
    )
    mixed = (
        "image-1.png: Save [size]; image-1.png: Hint [size]; "
        "image-1.png: the card sits left of its title [judgement] Fix: centre it"
    )
    record, _ = look_with(tmp_path, project, measured, answer_with(mixed))
    line = stored_rule(record, "Design system")
    assert line.startswith("Design system: Fail — ")
    assert "Save [size]" not in line
    assert (
        "image-1.png: Hint [size] — code: text is 10.5 px, under the 11 px floor"
        in line
    )
    assert "the card sits left of its title [judgement]" in line
    assert line.endswith("Fix: centre it")
    assert record["outcome"] == "findings"


def stored_rule(record: dict[str, object], name: str) -> str:
    rules = record["rules"]
    assert isinstance(rules, list)
    return next(line for line in rules if line.startswith(f"{name}:"))


def test_a_line_whose_items_all_pass_in_code_becomes_a_pass(
    tmp_path: Path, project: Path
) -> None:
    measured = values(texts=[text_fact("Save", 14)])
    record, _ = look_with(
        tmp_path, project, measured, answer_with("image-1.png: Save [size] Fix: bigger")
    )
    line = stored_rule(record, "Design system")
    assert line.startswith(
        "Design system: Pass — code checked: image-1.png: Save [size]"
    )
    assert "at or over the 11 px floor" in line
    assert record["outcome"] == "clean"


def two_rounds(
    tmp_path: Path,
    project: Path,
    first_fail: str,
    first: dict[str, object],
    second: dict[str, object],
    second_answer: str | None = None,
) -> tuple[dict[str, object], str]:
    """Round one holds a reviewer Fail line over a record; round two is a new head over another record, with the reviewer saying only what its answer says."""
    import ui_measure
    from test_look import next_head

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "inputs")
    images = make_images(project, 1)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=first)
    install_agent(tmp_path, "claude", 1, answer_with(first_fail))
    assert run_look(project, "codex", images)["outcome"] == "findings"
    next_head(project)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=second)
    log = install_agent(tmp_path, "claude", 1, second_answer or good_answer(1))
    record = run_look(project, "codex", images)
    return record, prompt_of(log)


NO_FACTS = values()
EARLIER = "Earlier look findings"


def test_an_earlier_measured_item_is_decided_by_code_before_the_prompt(
    tmp_path: Path, project: Path
) -> None:
    fail = "image-1.png: Hint [colour] Fix: use ink"
    held = values(texts=[text_fact("Hint")])
    record, prompt = two_rounds(tmp_path, project, fail, NO_FACTS, held)
    assert EARLIER not in prompt
    assert record["outcome"] == "clean"


def test_an_earlier_true_colour_fail_stays_a_fail_when_the_reviewer_says_nothing(
    tmp_path: Path, project: Path
) -> None:
    fail = "image-1.png: Hint [colour] Fix: use ink"
    off = values(texts=[text_fact("Hint", colour="767676ff", fg="#767676")])
    record, prompt = two_rounds(tmp_path, project, fail, NO_FACTS, off)
    assert EARLIER not in prompt
    assert record["outcome"] == "findings"
    line = stored_rule(record, "Design system")
    assert line.startswith("Design system: Fail — image-1.png: Hint [colour] — code: ")
    assert "is not in the colour tokens" in line


def test_an_earlier_item_that_code_cannot_find_is_listed_again(
    tmp_path: Path, project: Path
) -> None:
    fail = (
        "image-1.png: Hint [colour]; image-1.png: the card sits left [judgement] "
        "Fix: use ink"
    )
    answer = good_answer(1).replace(
        "VERDICT: clean",
        "Recheck R1: gone image-1.png: the card\nRecheck R2: gone image-1.png: Hint\nVERDICT: clean",
    )
    record, prompt = two_rounds(tmp_path, project, fail, NO_FACTS, NO_FACTS, answer)
    earlier = prompt.partition(EARLIER)[2]
    assert "image-1.png: the card sits left [judgement]" in earlier
    assert "image-1.png: Hint [colour]" in earlier
    assert "must not bring back another earlier finding" in prompt
    assert record["outcome"] == "clean"


def test_a_judgement_item_stays_on_the_list_when_a_measured_item_leaves_it(
    tmp_path: Path, project: Path
) -> None:
    fail = (
        "image-1.png: Hint [colour]; image-1.png: the card sits left [judgement] "
        "Fix: use ink"
    )
    held = values(texts=[text_fact("Hint")])
    answer = good_answer(1).replace(
        "VERDICT: clean", "Recheck R1: gone image-1.png: the card\nVERDICT: clean"
    )
    record, prompt = two_rounds(tmp_path, project, fail, NO_FACTS, held, answer)
    earlier = prompt.partition(EARLIER)[2]
    assert "image-1.png: the card sits left [judgement]" in earlier
    assert "Hint [colour]" not in earlier
    assert record["outcome"] == "clean"


NOTE = "Hard Eng: look: the rules are intended."


@pytest.mark.parametrize("outcome", ["findings", "clean", "not done"])
def test_a_findings_run_ends_with_the_line_about_the_rules(
    outcome: str, tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import look
    import ui_measure

    images = make_images(project, 1)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=values())
    answers = {
        "findings": answer_with(
            "image-1.png: the card sits left [judgement] Fix: centre it"
        ),
        "clean": good_answer(1),
        "not done": "no verdict line",
    }
    install_agent(tmp_path, "claude", 1, answers[outcome])
    look.look_command(project, ["--host", "codex", *map(str, images)])
    lines = capsys.readouterr().out.splitlines()
    if outcome != "findings":
        assert not any(line.startswith(NOTE) for line in lines)
        return
    assert lines[-1].startswith(NOTE)
    for words in (
        "also on parts this change did not touch",
        "contradicts a measured value, the markup or a quoted DESIGN.md line",
        "send that record line to the maintainer",
        "No declined, answered or skip line exists",
    ):
        assert words in lines[-1]
    assert len([line for line in lines if line.startswith(NOTE)]) == 1


@pytest.mark.parametrize(
    ("change", "named"),
    [
        ("design", "DESIGN.md"),
        ("plan scope", "the plan's Outcome + scope"),
        ("ring boxes", ""),
    ],
)
def test_a_changed_input_is_named_before_all_images_are_reviewed_again(
    change: str,
    named: str,
    tmp_path: Path,
    project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import look
    import ui_measure
    from test_look import full_plan
    from test_look_carry import clean_look_then_new_head

    images, old, _ = clean_look_then_new_head(tmp_path, project, plan=True)
    if change == "design":
        (project / "DESIGN.md").write_text("# Design\n\n## Overview\nBrand navy.\n")
    elif change == "plan scope":
        plan = project / "features/kpi-board/PLAN.md"
        plan.write_text(full_plan("A KPI board with two cards."))
    else:
        box = {"x": 1, "y": 2, "w": 30, "h": 40}
        ui_measure.write_record(project, images[0], 1280, [], "/kpi", ring_boxes=[box])
    (project / "notes.txt").write_text(f"{change}\n")
    commit(project, f"change: {change}")
    install_agent(tmp_path, "claude", 1, good_answer(1))
    capsys.readouterr()
    look.look_command(
        project,
        ["--host", "claude", "--plan", "features/kpi-board/PLAN.md", *map(str, images)],
    )
    out = capsys.readouterr().out
    if not named:
        assert "does not carry" not in out
        return
    assert (
        f"Hard Eng: look: {named} changed since {old[:12]}, so the clean verdict of "
        "that head does not carry. All 1 images are reviewed again." in out
    )
    assert out.index("does not carry") < out.index("Look review by")


LIST = (
    "Two faults: 1. image-1.png: Save [size] 2. image-1.png: the card sits left "
    "[judgement] Fix: fix both."
)


def test_a_list_of_items_with_no_semicolon_is_one_part_for_each_item() -> None:
    import look_answer

    parts, fix = look_answer.fail_parts(f"Design system: Fail — {LIST}")
    assert len(parts) == 2
    assert parts[1].startswith("image-1.png: the card sits left")
    assert fix == "Fix: fix both."
    outcome, _ = judged(LIST.replace("the card sits left", "badge #7a5c5c"))
    assert outcome.startswith("not done: a Fail line states #7a5c5c")


def test_the_second_item_of_a_list_survives_when_the_first_passes_in_code(
    tmp_path: Path, project: Path
) -> None:
    measured = values(texts=[text_fact("Save", 14)])
    record, _ = look_with(tmp_path, project, measured, answer_with(LIST))
    line = stored_rule(record, "Design system")
    assert line.startswith("Design system: Fail — ")
    assert "the card sits left [judgement]" in line
    assert "Save [size]" not in line
    assert record["outcome"] == "findings"


def test_a_gap_that_overlaps_by_a_pixel_is_no_gap_off_the_tokens(
    tmp_path: Path,
) -> None:
    import look_facts

    measured = values(gaps=[{"at": "Save", "to": "Cancel", "px": -1, "axis": "y"}])
    found = look_facts.verdict("gap", "Save", measured, tokens_of(tmp_path))
    assert found is not None
    assert found[0] is True


def test_a_notice_is_for_the_images_to_review_and_the_newest_matching_record_ends_it(
    tmp_path: Path, project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import look
    from test_look import next_head

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text("# Design\n\n## Overview\nBrand navy.\n")
    commit(project, "inputs")
    images = make_images(project, 2)
    install_agent(tmp_path, "claude", 2, good_answer(2))
    run_look(project, "claude", images)
    (project / "DESIGN.md").write_text("# Design\n\n## Overview\nBrand crimson.\n")
    commit(project, "design change")
    install_agent(tmp_path, "claude", 2, good_answer(2))
    run_look(project, "claude", images)
    images[0].write_bytes(images[0].read_bytes() + b"more")
    next_head(project)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    capsys.readouterr()
    look.look_command(project, ["--host", "claude", *map(str, images)])
    assert "does not carry" not in capsys.readouterr().out


def test_an_item_with_leading_frame_names_stays_with_the_reviewer(
    tmp_path: Path,
) -> None:
    import look_records

    measured = {
        "image-1.png": values(texts=[text_fact("Save", 10.5, under=True)]),
        "image-2.png": values(texts=[text_fact("Save", 14)]),
    }
    line = "Design system: Fail — image-1.png, image-2.png: Save [size] Fix: make it bigger."
    assert look_records.decide_line(line, measured, tokens_of(tmp_path)) == line


def test_an_earlier_measured_item_of_an_image_that_is_not_in_this_run_is_not_listed(
    tmp_path: Path, project: Path
) -> None:
    import look_facts
    import look_records
    import ui_measure
    from test_look import judged_rule_names, next_head

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "inputs")
    images = make_images(project, 2)
    off = values(texts=[text_fact("Hint", colour="767676ff", fg="#767676", bg="#fff")])
    for image in images:
        ui_measure.write_record(project, image, 1280, [], "/kpi", measured=off)
    both = "image-1.png: Hint [colour]; image-2.png: Hint [colour] Fix: use ink"
    answer = answer_with(both).replace(
        "VERDICT: findings", "Image image-2.png: a card\nVERDICT: findings"
    )
    install_agent(tmp_path, "claude", 2, answer)
    assert run_look(project, "codex", images)["outcome"] == "findings"
    next_head(project)
    held = values(texts=[text_fact("Hint")])
    ui_measure.write_record(project, images[1], 1280, [], "/kpi", measured=held)
    import hashlib

    digest = hashlib.sha256(images[1].read_bytes()).hexdigest()
    listed, fails = look_records.earlier_findings(
        project,
        git_head(project),
        [("image-1.png", images[1].name, digest)],
        judged_rule_names(),
        {"image-1.png": held},
        look_facts.design_tokens(project),
    )
    assert listed == []
    assert fails == []


def git_head(project: Path) -> str:
    from conftest import git

    return git(project, "rev-parse", "HEAD").strip()


def test_a_carried_image_does_not_hide_the_failing_image_that_shares_its_name(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure
    from test_look import next_head

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "inputs")
    held, failing = make_images(project, 2)
    off = values(texts=[text_fact("Hint", colour="767676ff", fg="#767676", bg="#fff")])
    ui_measure.write_record(project, held, 1280, [], "/kpi", measured=values())
    ui_measure.write_record(project, failing, 1280, [], "/kpi", measured=off)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    assert run_look(project, "codex", [held])["outcome"] == "clean"
    next_head(project)
    install_agent(
        tmp_path, "claude", 1, answer_with("image-1.png: Hint [colour] Fix: use ink")
    )
    assert run_look(project, "codex", [failing, held])["outcome"] == "findings"
    next_head(project)
    failing.write_bytes(failing.read_bytes() + b"x")
    ui_measure.write_record(project, failing, 1280, [], "/kpi", measured=off)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "codex", [failing, held])
    assert record["outcome"] == "findings"
    assert "Hint [colour] — code:" in stored_rule(record, "Design system")


def test_an_earlier_item_of_an_image_that_a_later_clean_record_covers_is_not_listed(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure
    from test_look import next_head

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(DESIGN)
    commit(project, "inputs")
    images = make_images(project, 2)
    for image in images:
        ui_measure.write_record(project, image, 1280, [], "/kpi", measured=values())
    both = (
        "image-1.png: the card sits left [judgement]; "
        "image-2.png: the card sits right [judgement] Fix: centre it"
    )
    answer = answer_with(both).replace(
        "VERDICT: findings", "Image image-2.png: a card\nVERDICT: findings"
    )
    install_agent(tmp_path, "claude", 2, answer)
    assert run_look(project, "codex", images)["outcome"] == "findings"
    next_head(project)
    gone = good_answer(1).replace(
        "VERDICT: clean", "Recheck R1: gone image-1.png: the card\nVERDICT: clean"
    )
    install_agent(tmp_path, "claude", 1, gone)
    assert run_look(project, "codex", images[:1])["outcome"] == "clean"
    next_head(project)
    log = install_agent(tmp_path, "claude", 2, good_answer(2))
    run_look(project, "codex", images, extra=["--all"])
    earlier = prompt_of(log).partition(EARLIER)[2]
    assert "the card sits right" in earlier
    assert "the card sits left" not in earlier


@pytest.mark.parametrize(
    "line",
    [
        "Design system: Fail — image-1.png: Save [size], Cancel [tap] Fix: fix both.",
        "Design system: Fail — image-1.png: Save [size] (also image-2.png) Fix: bigger.",
    ],
)
def test_an_item_that_names_more_than_one_item_or_frame_stays_with_the_reviewer(
    line: str, tmp_path: Path
) -> None:
    import look_records

    ok = values(texts=[text_fact("Save", 14)], sizes={"controls": [control("Cancel")]})
    measured = {"image-1.png": ok, "image-2.png": ok}
    assert look_records.decide_line(line, measured, tokens_of(tmp_path)) == line


def test_a_part_with_a_leading_frame_stays_while_any_of_its_frames_is_in_this_run() -> (
    None
):
    import look_records

    line = "Design system: Fail — image-1.png, image-2.png: Save [size] Fix: bigger."
    then = {"image-1.png": "home-375.png", "image-2.png": "home-1280.png"}
    assert (
        look_records._without_held(line, then, {"home-375.png": "image-1.png"}) == line
    )
    assert look_records._without_held(line, then, {}) == "Design system: Pass"
