"""The reviewer's answer: the rule line forms it may write, and the Fail lines that cannot stand."""

from pathlib import Path

import look_answer
import pytest
from plans import usability_rules
from test_look import (
    FIXTURES,
    install_agent,
    judged_rule_names,
    listed,
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
    outcome, rules, details = look_answer.judge(framed, ["image-1.png"], read)
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
        (
            "No clutter: Fail (kept 13, removed 6). image-1.png: a repeated status. Fix: drop it",
            "findings",
            "",
        ),
        (
            "No clutter: Fail (kept 13, removed 0). image-1.png: a repeated status. Fix: drop it",
            "not done",
            ZERO,
        ),
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
    rule = line.partition(":")[0].partition(" (")[0]
    return look_with_lines(tmp_path, project, {rule: line}, outcome)


def look_with_lines(
    tmp_path: Path, project: Path, given: dict[str, str], outcome: str
) -> dict[str, object]:
    """A run whose reviewer gives each text of `given` for its rule, which may span lines, and Pass for every other rule."""
    images = make_images(project, 1)
    rules = [
        given.get(name, f"- {name}: Pass — looked at it")
        for name, _ in usability_rules()
    ]
    verdict = "VERDICT: clean" if outcome == "clean" else "VERDICT: findings"
    answer = "\n".join([*rules, "Image image-1.png: a card with a title", verdict])
    install_agent(tmp_path, "claude", 1, answer)
    return run_look(project, "codex", images)


BADGE = "- No clutter: Fail — image-1.png: the badge repeats the title."


@pytest.mark.parametrize(
    ("block", "outcome"),
    [
        (f"{BADGE}\n  Fix: merge the badge into the title", "findings"),
        (f"{BADGE}\n  - the card shows it twice\n  - Fix: merge the badge", "findings"),
        (f"{BADGE}\n  - the card shows it twice\n\n  Fix: merge the badge", "findings"),
        (f"{BADGE}\n  - the card shows it twice\n\n  Check it again.", "not done"),
        (f"{BADGE}\n  - a sub-bullet without any change", "not done"),
    ],
)
def test_a_fail_with_its_fix_on_a_continuation_line_is_read_whole(
    tmp_path: Path, project: Path, block: str, outcome: str
) -> None:
    record = look_with_lines(tmp_path, project, {"No clutter": block}, outcome)
    assert str(record["outcome"]).startswith(outcome)
    if outcome == "findings":
        text = " ".join(str(line) for line in listed(record, "rules"))
        assert "Fix: merge the badge" in text


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


def test_the_fix_of_the_next_rule_does_not_belong_to_a_fail_without_one(
    tmp_path: Path, project: Path
) -> None:
    given = {
        "No clutter": f"{BADGE}\n  - the card shows it twice",
        "Hierarchy": "- Hierarchy: Fail — image-1.png: two filled buttons. Fix: outline one.",
    }
    record = look_with_lines(tmp_path, project, given, "findings")
    assert str(record["outcome"]).startswith("not done: a Fail line names no `Fix:")
    assert "No clutter" in str(record["outcome"])
