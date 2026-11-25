"""look decides each Usability rule by its own proof kind: the reviewer sees only the rules with the judgement kind."""

import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from conftest import commit, git
from plans import usability_rules
from test_look import (
    PNG,
    full_plan,
    good_answer,
    install_agent,
    look_project,
    make_images,
    next_head,
    run_look,
)
from test_look_carry import findings_answer

project = pytest.fixture(look_project)
MEASURED_ONLY = ("Accessibility", "Widths")
TEST_ONLY = ("States", "Time", "Audit", "Performance")
BOTH = ("No clutter", "Hierarchy", "Alignment")
OWNER_LINE = re.compile(r"(\S[^:]*): (Pass|Fail|N/A) — (measured|test): (\S.*)")


def kinds() -> Mapping[str, Sequence[str]]:
    from ui_measure import PROOF_KINDS

    return PROOF_KINDS


def prompt_of(log: Path) -> str:
    argv = json.loads(log.read_text())["argv"]
    return next(part for part in argv if "\n\nRules:\n" in part)


def prompt_rule_names(prompt: str) -> list[str]:
    rules = prompt.partition("\n\nRules:\n")[2].partition("\n\n")[0]
    return [
        line[2:].partition(":")[0].partition(" (count")[0]
        for line in rules.splitlines()
        if line.startswith("- ")
    ]


def captures(project: Path) -> list[Path]:
    """One page captured at the three standard widths, with a measure record for each."""
    import ui_measure

    folder = project / ".hard-eng/browser"
    folder.mkdir(parents=True, exist_ok=True)
    images = []
    for number, width in enumerate((390, 768, 1280)):
        image = folder / f"home-{width}.png"
        image.write_bytes(PNG + bytes([number + 1]) * 20)
        ui_measure.write_record(project, image, width, [], "/home")
        images.append(image)
    return images


def stored(record: dict[str, object]) -> dict[str, str]:
    rules = record["rules"]
    assert isinstance(rules, list)
    return {line.partition(":")[0].partition(" (")[0]: line for line in rules}


def test_the_prompt_holds_only_the_rules_with_a_judgement_kind(
    tmp_path: Path, project: Path
) -> None:
    images = captures(project)
    log = install_agent(tmp_path, "claude", 3, good_answer(3))
    run_look(project, "codex", images)
    sent = prompt_rule_names(prompt_of(log))
    assert sent == [name for name, k in kinds().items() if "judgement" in k]
    assert not set(sent) & {*MEASURED_ONLY, *TEST_ONLY}
    assert set(BOTH) <= set(sent)


def test_an_image_with_no_measure_record_leaves_the_measured_rules_to_the_reviewer(
    tmp_path: Path, project: Path
) -> None:
    images = make_images(project, 1)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    sent = prompt_rule_names(prompt_of(log))
    assert set(MEASURED_ONLY) <= set(sent)
    assert not set(sent) & set(TEST_ONLY)
    next_head(project)
    answer = good_answer(1).replace(
        "- Widths: Pass — looked at it",
        "- Widths: Fail — image-1.png: too narrow Fix: widen it",
    )
    install_agent(tmp_path, "claude", 1, answer)
    record = run_look(project, "codex", images, extra=["--all"])
    assert record["outcome"] == "findings"
    assert stored(record)["Widths"].startswith("Widths: Fail — image-1.png: too narrow")


def test_a_reviewer_line_for_a_rule_without_judgement_is_ignored(
    tmp_path: Path, project: Path
) -> None:
    images = captures(project)
    answer = good_answer(3).replace(
        "- Widths: Pass — looked at it",
        "- Widths: Fail — image-1.png: too narrow Fix: widen it",
    )
    answer = answer.replace(
        "- States: Pass — looked at it", "- States: Fail — empty Fix: say what next"
    )
    install_agent(tmp_path, "claude", 3, answer)
    record = run_look(project, "codex", images)
    assert record["outcome"] == "clean"
    assert "Fail" not in stored(record)["Widths"]
    assert "Fail" not in stored(record)["States"]

    judged = "\n".join(
        line
        for line in good_answer(3).splitlines()
        if line.partition(":")[0].removeprefix("- ") not in {*MEASURED_ONLY, *TEST_ONLY}
    )
    install_agent(tmp_path, "claude", 3, judged)
    assert run_look(project, "codex", images)["outcome"] == "clean"


def test_the_block_gives_each_rule_a_line_and_names_the_owner(
    tmp_path: Path, project: Path
) -> None:
    import look

    images = captures(project)
    install_agent(tmp_path, "claude", 3, good_answer(3))
    record = run_look(project, "codex", images)
    assert record["outcome"] == "clean"
    assert list(stored(record)) == [name for name, _ in usability_rules()]
    block = look.block_text(record)
    assert look.block_problem(block, 3) is None
    for name in MEASURED_ONLY:
        found = OWNER_LINE.fullmatch(stored(record)[name])
        assert found
        assert (found[2], found[3]) == ("Pass", "measured")
        assert re.fullmatch(
            r"0 findings at 390, 768 and 1280 \(record [0-9a-f]{12}\)", found[4]
        )
        assert f"- {stored(record)[name]}" in block
    for name in TEST_ONLY:
        found = OWNER_LINE.fullmatch(stored(record)[name])
        assert found
        assert (found[2], found[3]) == ("N/A", "test")
        assert "no plan given; the plan check decides" in found[4]
    for name in (n for n, k in kinds().items() if "judgement" in k):
        assert "looked at it" in stored(record)[name]


def test_a_measure_finding_fails_the_measured_rules_and_the_run(
    tmp_path: Path, project: Path
) -> None:
    import look
    import ui_measure

    images = captures(project)
    ui_measure.write_record(
        project, images[0], 390, [{"rule": "overflow", "at": "page"}], "/home"
    )
    install_agent(tmp_path, "claude", 3, good_answer(3))
    record = run_look(project, "codex", images)
    assert record["outcome"] == "findings"
    for name in MEASURED_ONLY:
        found = OWNER_LINE.fullmatch(stored(record)[name])
        assert found
        assert (found[2], found[3]) == ("Fail", "measured")
        assert "overflow" in found[4]
    for name in (n for n, k in kinds().items() if list(k) != ["measured"]):
        assert "Fail" not in stored(record)[name]
    assert look.block_problem(look.block_text(record), 3) is not None


def test_a_test_rule_takes_its_line_from_the_plan(
    tmp_path: Path, project: Path
) -> None:
    plan = project / "features/kpi-board/PLAN.md"
    plan.parent.mkdir(parents=True)
    ux = (
        "Surface: Existing — /kpi, rendered by app\nRules:\n"
        "- States: Pass — tests/test_kpi.py::test_empty_board_says_what_next\n"
        "- Time: N/A — no times on this screen"
    )
    plan.write_text(full_plan("A KPI board with one card.", ux))
    commit(project, "plan")
    images = make_images(project, 1)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    extra = ["--plan", "features/kpi-board/PLAN.md"]
    record = run_look(project, "codex", images, extra=extra)
    assert record["outcome"] == "clean"
    assert stored(record)["States"] == (
        "States: Pass — test: tests/test_kpi.py::test_empty_board_says_what_next"
    )
    assert stored(record)["Time"] == "Time: N/A — test: no times on this screen"
    assert stored(record)["Audit"].startswith("Audit: N/A — test: ")

    plan.write_text(
        full_plan(
            "A KPI board with one card.",
            ux.replace("States: Pass", "States: Fail"),
        )
    )
    commit(project, "plan fails a test rule")
    failed = run_look(project, "codex", images, extra=extra)
    assert failed["outcome"] == "findings"
    assert stored(failed)["States"].startswith("States: Fail — test: ")


def test_a_rule_with_measured_and_judgement_still_goes_to_the_reviewer(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    images = make_images(project, 1)
    values: dict[str, object] = {"radii": [{"at": "Go", "px": 6}]}
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=values)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "codex", images)
    prompt = prompt_of(log)
    assert set(BOTH) <= set(prompt_rule_names(prompt))
    assert "- Go: 6 px" in prompt
    for name in BOTH:
        assert "looked at it" in stored(record)[name]


def test_an_owner_fail_line_is_not_sent_back_as_an_earlier_fix(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    (project / ".gitignore").write_text(".hard-eng/\n")
    commit(project, "inputs")
    images = make_images(project, 1)
    ui_measure.write_record(
        project, images[0], 390, [{"rule": "overflow", "at": "page"}], "/kpi"
    )
    install_agent(
        tmp_path, "claude", 1, findings_answer(1, "Alignment", "badge and meta apart")
    )
    first = run_look(project, "codex", images)
    assert first["outcome"] == "findings"
    assert stored(first)["Widths"].startswith("Widths: Fail — measured: ")

    images[0].write_bytes(PNG + b"fixed")
    (project / "notes.txt").write_text("the page is fixed\n")
    commit(project, "fix the page")
    ui_measure.write_record(project, images[0], 390, [], "/kpi")
    assert git(project, "rev-parse", "HEAD").strip()
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    prompt = prompt_of(log)
    assert "Alignment: Fail — image-1.png: badge and meta apart" in prompt
    assert "Widths: Fail" not in prompt


def test_a_reviewer_fail_on_a_measured_rule_is_sent_back_as_an_earlier_fix(
    tmp_path: Path, project: Path
) -> None:
    (project / ".gitignore").write_text(".hard-eng/\n")
    commit(project, "inputs")
    images = make_images(project, 1)
    install_agent(
        tmp_path, "claude", 1, findings_answer(1, "Widths", "label too narrow")
    )
    assert run_look(project, "codex", images)["outcome"] == "findings"
    images[0].write_bytes(PNG + b"fixed")
    (project / "notes.txt").write_text("the label is wider\n")
    commit(project, "widen the label")
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    assert "Widths: Fail — image-1.png: label too narrow" in prompt_of(log)


def test_an_older_capture_with_findings_does_not_fail_a_page_fixed_since(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    (project / ".gitignore").write_text(".hard-eng/\n")
    commit(project, "inputs")
    folder = project / ".hard-eng/browser"
    folder.mkdir(parents=True)
    old = folder / "old-390.png"
    old.write_bytes(PNG + bytes([1]) * 20)
    ui_measure.write_record(
        project, old, 390, [{"rule": "overflow", "at": "page"}], "/home"
    )
    (project / "notes.txt").write_text("the page is fixed\n")
    commit(project, "fix the page")
    images = captures(project)
    install_agent(tmp_path, "claude", 3, good_answer(3))
    record = run_look(project, "codex", images)
    assert record["outcome"] == "clean"
    assert stored(record)["Widths"].startswith("Widths: Pass — measured: ")


JUDGED_BY_CODE = [
    ("competing-buttons", "Hierarchy"),
    ("accent-colours", "Hierarchy"),
    ("heading-hierarchy", "Hierarchy"),
    ("duplicate-buttons", "No clutter"),
    ("extra-text", "No clutter"),
    ("field-control", "No clutter"),
    ("shared-edge", "Alignment"),
]


@pytest.mark.parametrize(("finding", "rule"), JUDGED_BY_CODE)
def test_a_measure_finding_fails_its_judged_rule_in_code(
    tmp_path: Path, project: Path, finding: str, rule: str
) -> None:
    import ui_measure

    images = make_images(project, 1)
    ui_measure.write_record(
        project, images[0], 1280, [{"rule": finding, "at": "Save"}], "/kpi"
    )
    install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "codex", images)
    assert record["outcome"] == "findings"
    found = OWNER_LINE.fullmatch(stored(record)[rule])
    assert found
    assert (found[2], found[3]) == ("Fail", "measured")
    assert finding in found[4]
    for other in (name for name in BOTH if name != rule):
        assert "looked at it" in stored(record)[other]


def test_a_finding_that_no_judged_rule_owns_leaves_those_rules_to_the_reviewer(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    images = make_images(project, 1)
    ui_measure.write_record(
        project, images[0], 1280, [{"rule": "wrapped-label", "at": "Save"}], "/kpi"
    )
    install_agent(tmp_path, "claude", 1, good_answer(1))
    record = run_look(project, "codex", images)
    for name in BOTH:
        assert "looked at it" in stored(record)[name]


def test_a_code_pass_never_erases_a_reviewer_fail(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    images = make_images(project, 1)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi")
    answer = good_answer(1).replace(
        "- Hierarchy: Pass — looked at it",
        "- Hierarchy: Fail — image-1.png: two loud buttons. Fix: quiet one.",
    )
    install_agent(tmp_path, "claude", 1, answer)
    record = run_look(project, "codex", images)
    assert record["outcome"] == "findings"
    assert stored(record)["Hierarchy"].startswith("Hierarchy: Fail — image-1.png: two")


TOKENS = (
    "---\nrounded:\n  sm: 4px\n  md: 0.5rem\n"
    "typography:\n  body:\n    fontSize: 14px\n---\n"
    "# Design\n\n## Overview\nPlain.\n"
)
SIZES = {"controls": [], "text_px": [14, 20, 13]}
RADII = [
    {"at": "card", "px": 8, "clamped": False},
    {"at": "badge", "px": 7, "clamped": False},
    {"at": "pill", "px": 11, "clamped": True},
    {"at": "old", "px": 5},
]


def look_against_tokens(
    tmp_path: Path, project: Path, design: str, values: dict[str, object]
) -> dict[str, object]:
    import ui_measure

    (project / "DESIGN.md").write_text(design)
    commit(project, "design")
    images = make_images(project, 1)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=values)
    install_agent(tmp_path, "claude", 1, good_answer(1))
    return run_look(project, "codex", images)


def test_a_radius_outside_the_tokens_fails_design_system_in_code(
    tmp_path: Path, project: Path
) -> None:
    values: dict[str, object] = {"sizes": SIZES, "radii": RADII, "root_px": 16}
    record = look_against_tokens(tmp_path, project, TOKENS, values)
    assert record["outcome"] == "findings"
    found = OWNER_LINE.fullmatch(stored(record)["Design system"])
    assert found
    assert (found[2], found[3]) == ("Fail", "measured")
    assert "corner radius 7 px" in found[4]
    assert "text size" not in found[4]
    for held in ("radius 8", "radius 11", "radius 5"):
        assert held not in found[4]


@pytest.mark.parametrize(
    "case",
    [
        "all held",
        "no token group",
        "no measured values",
        "old record only",
        "no PyYAML",
        "text size outside the tokens",
        "root size changed",
        "no root size",
        "token that is not a length",
        "em token",
    ],
)
def test_values_that_the_tokens_hold_or_cannot_judge_leave_design_system_to_the_reviewer(
    tmp_path: Path, project: Path, case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    design = TOKENS
    values: dict[str, object] = {
        "sizes": {"controls": [], "text_px": [14, 20]},
        "radii": [{"at": "card", "px": 8, "clamped": False}],
        "root_px": 16,
    }
    if case == "no token group":
        design = (
            "---\ncolors:\n  ink: '#111111'\n---\n# Design\n\n## Overview\nPlain.\n"
        )
        values = {"sizes": SIZES, "radii": RADII, "root_px": 16}
    if case == "no measured values":
        values = {"contrast": []}
    if case == "old record only":
        values = {"radii": [{"at": "x", "px": 7}], "root_px": 16}
    if case == "no PyYAML":
        monkeypatch.setitem(sys.modules, "yaml", None)
        values = {"sizes": SIZES, "radii": RADII, "root_px": 16}
    if case == "text size outside the tokens":
        values["sizes"] = SIZES
    if case == "root size changed":
        values = {"radii": [{"at": "card", "px": 5, "clamped": False}], "root_px": 10}
    if case == "no root size":
        values = {"radii": [{"at": "card", "px": 7, "clamped": False}]}
    if case == "token that is not a length":
        design = design.replace("sm: 4px", "sm: clamp(1px, 1vw, 8px)")
        values = {"radii": [{"at": "x", "px": 7, "clamped": False}], "root_px": 16}
    if case == "em token":
        design = design.replace("sm: 4px", "sm: 0.5em")
        values = {"radii": [{"at": "x", "px": 7, "clamped": False}], "root_px": 16}
    record = look_against_tokens(tmp_path, project, design, values)
    assert record["outcome"] == "clean"
    assert "looked at it" in stored(record)["Design system"]


def test_the_prompt_says_that_code_decides_the_measured_rules(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    images = make_images(project, 1)
    ui_measure.write_record(
        project,
        images[0],
        1280,
        [],
        "/kpi",
        measured={"radii": [{"at": "Go", "px": 6}]},
    )
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    assert "Code already decides the measure findings" in prompt_of(log)


def test_a_reviewer_fail_that_a_code_fail_replaces_is_still_rechecked_next_run(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    (project / ".gitignore").write_text(".hard-eng/\n")
    (project / "DESIGN.md").write_text(TOKENS)
    commit(project, "inputs")
    images = make_images(project, 1)
    values: dict[str, object] = {
        "radii": [{"at": "badge", "px": 7, "clamped": False}],
        "root_px": 16,
    }
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=values)
    answer = good_answer(1).replace(
        "- Design system: Pass — looked at it",
        "- Design system: Fail — image-1.png: a #ffffff label is no token. Fix: use paper.",
    )
    install_agent(tmp_path, "claude", 1, answer)
    first = run_look(project, "codex", images)
    assert stored(first)["Design system"].startswith("Design system: Fail — measured:")
    next_head(project)
    ui_measure.write_record(project, images[0], 1280, [], "/kpi", measured=values)
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    prompt = prompt_of(log)
    assert "a #ffffff label is no token" in prompt
    assert "measured:" not in prompt.partition("Earlier look findings")[2]
