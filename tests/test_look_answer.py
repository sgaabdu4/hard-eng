"""The reviewer's answer: the rule line forms it may write, and the Fail lines that cannot stand."""

import re
from pathlib import Path

import look_answer
import pytest
from plans import usability_rules
from test_look import (
    FIXTURES,
    first_prompt,
    install_agent,
    judged_rule_names,
    look_project,
    make_images,
    run_look,
)

project = pytest.fixture(look_project)


@pytest.mark.parametrize("separator", [". ", " - ", " — "])
def test_look_reads_each_rule_line_form_and_refuses_a_line_with_no_verdict(
    separator: str,
) -> None:
    names = judged_rule_names()
    image = ["Image image-1.png: a card with a title", "VERDICT: clean"]
    read = {"image-1.png": True}

    def rule_lines(answer: list[str]) -> tuple[str, list[str]]:
        outcome, rules, _ = look_answer.judge("\n".join(answer), ["image-1.png"], read)
        return outcome, rules

    given = [f"- {name}: Pass{separator}looked at it" for name in names]
    assert rule_lines([*given, *image]) == (
        "clean",
        [f"{name}: Pass — looked at it" for name in names],
    )
    for broken in (f"- {names[0]}: looked at it", f"- {names[0]}: Pass."):
        outcome, rules = rule_lines([broken, *given[1:], *image])
        assert outcome.startswith("not done"), broken
        assert rules == []


def test_look_reads_a_real_claude_answer() -> None:
    answer = (FIXTURES / "claude-answer.txt").read_text()
    read = {"image-1.png": True}
    assert look_answer.judge(answer, ["image-1.png"], read)[0].startswith(
        "not done: a Fail line names no frame"
    )
    framed = answer.replace("Fail — ", "Fail — image-1.png: ")
    assert look_answer.judge(framed, ["image-1.png"], read)[0].startswith(
        "not done: a Fail line states 25 px outside an item"
    )
    outcome, rules, details = look_answer.judge(
        framed.replace("about 25 px lower", "lower"), ["image-1.png"], read
    )
    assert outcome == "findings"
    assert len(rules) == len(judged_rule_names())
    assert "image-1.png" in details


ZERO = "its own count says 0 removed"


@pytest.mark.parametrize(
    ("line", "outcome", "reason"),
    [
        ("No clutter: Fail — kept 34, removed 0. Fix: merge", "not done", ZERO),
        (
            "No clutter (kept 34, removed 0): Fail — too many labels. Fix: merge",
            "not done",
            ZERO,
        ),
        (
            "No clutter: Fail — image-1.png: kept 34, removed 2. Fix: merge the badges",
            "findings",
            "",
        ),
        ("No clutter: Pass — kept 34, removed 0", "clean", ""),
        ("No clutter: Fail — kept 34, removed: 0. Fix: merge", "not done", ZERO),
        ("No clutter: Fail — too many labels, 0 removed. Fix: merge", "not done", ZERO),
        ("No clutter: Fail — kept 34 removed 0. Fix: merge", "not done", ZERO),
        (
            "No clutter: Fail — too many labels. Fix: merge (kept 15 / 19 / 74, removed 0 / 0 / 0)",
            "not done",
            ZERO,
        ),
        (
            "No clutter: Fail — too many labels. Fix: merge (kept 15 / 19 / 74 removed 0 / 0 / 0)",
            "not done",
            ZERO,
        ),
        ("No clutter: Fail — kept 34, 0 removed. Fix: merge", "not done", ZERO),
        (
            "No clutter: Fail — kept 34, removed 0, 3 badges repeat the title. Fix: merge",
            "not done",
            ZERO,
        ),
        (
            "No clutter: Fail — image-1.png: too many labels. Fix: merge the badges (kept 15 / 19 / 74, removed 0 / 0 / 5)",
            "findings",
            "",
        ),
        (
            "No clutter (kept 15 / 19 / 74, removed 0 / 0 / 5): Fail — image-1.png: too many labels. Fix: merge the badges",
            "findings",
            "",
        ),
        (
            "No clutter: Fail — image-1.png: too many labels. Fix: merge the badges (kept 15 / 19, removed 0 / 3)",
            "findings",
            "",
        ),
        ("Design system: Fail — There are three problems.", "not done", "Fix:"),
        ("Design system: Fail — A new colour. Fix:", "not done", "Fix:"),
        (
            "Design system: Fail — image-1.png: A new colour. Fix: use the token.",
            "findings",
            "",
        ),
    ],
)
def test_a_fail_line_that_cannot_stand_is_refused(
    tmp_path: Path, project: Path, line: str, outcome: str, reason: str
) -> None:
    record = look_with_line(tmp_path, project, line, outcome)
    assert str(record["outcome"]).startswith(outcome)
    assert reason in str(record["outcome"])


def look_with_line(
    tmp_path: Path, project: Path, line: str, outcome: str
) -> dict[str, object]:
    """A run whose reviewer gives `line` for its rule and Pass for every other rule."""
    images = make_images(project, 1)
    rule = line.partition(":")[0].partition(" (")[0]
    rules = [
        line if name == rule else f"- {name}: Pass — looked at it"
        for name, _ in usability_rules()
    ]
    verdict = "VERDICT: clean" if outcome == "clean" else "VERDICT: findings"
    answer = "\n".join([*rules, "Image image-1.png: a card with a title", verdict])
    install_agent(tmp_path, "claude", 1, answer)
    return run_look(project, "codex", images)


@pytest.mark.parametrize(
    ("line", "outcome"),
    [
        ("Design system: Fail — a new colour. Fix: use the token.", "not done"),
        ("Design system: Fail — image-9.png: a new colour. Fix: use it.", "not done"),
        ("Design system: Fail — image-1.png: a colour. Fix: use it.", "findings"),
        (
            "Design system: Fail — image-1.png: a colour; image-2.png: a size. Fix: use it.",
            "findings",
        ),
    ],
)
def test_a_fail_line_must_name_the_frame_it_shows(
    tmp_path: Path, project: Path, line: str, outcome: str
) -> None:
    record = look_with_line(tmp_path, project, line, outcome)
    assert str(record["outcome"]).startswith(outcome)
    if outcome == "not done":
        assert "names no frame" in str(record["outcome"])


def judge_blocks(blocks: dict[str, list[str]]) -> tuple[str, list[str]]:
    lines = [
        line
        for name in judged_rule_names()
        for line in blocks.get(name, [f"- {name}: Pass. looked at it"])
    ]
    answer = "\n".join(
        [*lines, "Image image-1.png: a card with a title", "VERDICT: findings"]
    )
    outcome, rules, _ = look_answer.judge(
        answer, ["image-1.png"], {"image-1.png": True}
    )
    return outcome, rules


def test_a_fix_after_a_list_belongs_to_its_rule_block() -> None:
    outcome, rules = judge_blocks(
        {
            "Design system": [
                "- Design system: Fail. image-1.png: Two things break DESIGN.md:",
                "  1. The chips have square corners.",
                "  2. The bars use a colour that is not a token.",
                "",
                "  The outline looks right. Fix: round the chips and use a token for the bars.",
            ]
        }
    )
    assert outcome == "findings"
    stored = next(line for line in rules if line.startswith("Design system:"))
    assert stored == (
        "Design system: Fail — image-1.png: Two things break DESIGN.md: 1. The chips "
        "have square corners. 2. The bars use a colour that is not a token. The outline "
        "looks right. Fix: round the chips and use a token for the bars."
    )


def test_a_fail_block_with_no_fix_is_still_refused() -> None:
    nofix = [
        "- Hierarchy: Fail. image-1.png: Two filled elements compete:",
        "  1. A chip.",
        "  2. A tab.",
    ]
    outcome, rules = judge_blocks({"Hierarchy": nofix})
    assert outcome.startswith("not done: a Fail line names no `Fix: <the change>`")
    assert rules == []
    outcome, _ = judge_blocks(
        {
            "Hierarchy": nofix,
            "Spacing": ["- Spacing: Pass. even gaps. Fix: nothing, this is a Pass"],
        }
    )
    assert outcome.startswith("not done: a Fail line names no")


def test_a_count_note_after_the_verdict_is_stored_like_one_before_the_colon() -> None:
    expected = (
        "No clutter: Fail — image-1.png: The note stays. Fix: remove it. "
        "(kept: 40, removed: 3)"
    )
    for form in (
        "- No clutter: Fail (kept: 40, removed: 3). image-1.png: The note stays. Fix: remove it.",
        "- No clutter: Fail (kept: 40, removed: 3) - image-1.png: The note stays. Fix: remove it.",
        "- No clutter (kept: 40, removed: 3): Fail. image-1.png: The note stays. Fix: remove it.",
    ):
        outcome, rules = judge_blocks({"No clutter": [form]})
        assert outcome == "findings", form
        stored = next(line for line in rules if line.startswith("No clutter:"))
        assert stored == expected, form


@pytest.mark.parametrize(
    "note", ["(kept 13, removed 6)", "(13 kept, 6 removed)", "(kept: 13, removed: 6)"]
)
def test_a_count_note_after_the_verdict_may_leave_out_the_colon(note: str) -> None:
    form = f"- No clutter: Fail {note}. image-1.png: The note stays. Fix: remove it."
    outcome, rules = judge_blocks({"No clutter": [form]})
    assert outcome == "findings", form
    stored = next(line for line in rules if line.startswith("No clutter:"))
    assert stored == (
        f"No clutter: Fail — image-1.png: The note stays. Fix: remove it. {note}"
    )


def test_a_recheck_line_after_a_rule_block_is_not_part_of_the_block() -> None:
    lines = [
        f"- {name}: Pass. looked at it"
        if name != "Hierarchy"
        else "- Hierarchy: Fail. image-1.png: two compete. Fix: tone one down."
        for name in judged_rule_names()
    ]
    answer = "\n".join(
        [
            *lines,
            "Recheck R1: still shown. image-1.png: two compete.",
            "Image image-1.png: a card with a title",
            "VERDICT: findings",
        ]
    )
    outcome, rules, _ = look_answer.judge(
        answer, ["image-1.png"], {"image-1.png": True}, rechecks=["Hierarchy"]
    )
    assert outcome == "findings"
    assert next(line for line in rules if line.startswith("Hierarchy:")) == (
        "Hierarchy: Fail — image-1.png: two compete. Fix: tone one down."
    )


def test_a_count_note_with_no_number_after_the_verdict_is_still_refused() -> None:
    outcome, rules = judge_blocks(
        {
            "No clutter": [
                "- No clutter: Fail (kept: , removed: ). image-1.png: The note stays. Fix: remove it."
            ]
        }
    )
    assert outcome.startswith("not done: a rule line or an image detail")
    assert rules == []


def test_the_prompt_shows_the_count_note_before_the_colon(
    tmp_path: Path, project: Path
) -> None:
    _, _, prompt = first_prompt(tmp_path, project)
    form = prompt.partition("\n\nRules:")[0]
    assert "`- No clutter (kept: 40, removed: 3): Fail. <what you saw>`" in form
    assert "—" not in form


ANSWERS = sorted((FIXTURES / "answers").glob("*.txt"))


@pytest.mark.parametrize("path", ANSWERS, ids=[path.stem for path in ANSWERS])
def test_a_real_reviewer_answer_shape_is_read_as_its_file_name_says(path: Path) -> None:
    text = path.read_text()
    frames = sorted(
        set(re.findall(r"^Image (image-\d+\.png)", text, re.MULTILINE))
    ) or ["image-1.png"]
    outcome, rules, _ = look_answer.judge(text, frames, dict.fromkeys(frames, True))
    expected = path.stem.partition("__")[0].replace("-", " ")
    if expected == "not done":
        assert outcome.startswith("not done"), outcome
        assert rules == []
    else:
        assert outcome == expected, outcome
        assert len(rules) == len(judged_rule_names())
