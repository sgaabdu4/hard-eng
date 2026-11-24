"""look decides each Usability rule by its own proof kind: the reviewer sees only the rules with the judgement kind."""

import json
import re
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
    answer = good_answer(1).replace(
        "- Widths: Pass — looked at it", "- Widths: Fail — too narrow Fix: widen it"
    )
    install_agent(tmp_path, "claude", 1, answer)
    record = run_look(project, "codex", images)
    assert record["outcome"] == "findings"
    assert stored(record)["Widths"].startswith("Widths: Fail — too narrow")


def test_a_reviewer_line_for_a_rule_without_judgement_is_ignored(
    tmp_path: Path, project: Path
) -> None:
    images = captures(project)
    answer = good_answer(3).replace(
        "- Widths: Pass — looked at it", "- Widths: Fail — too narrow Fix: widen it"
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
    assert "corner radius 6 px (Go)" in prompt
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
    ui_measure.write_record(project, images[0], 390, [], "/kpi")
    (project / "notes.txt").write_text("the page is fixed\n")
    commit(project, "fix the page")
    assert git(project, "rev-parse", "HEAD").strip()
    log = install_agent(tmp_path, "claude", 1, good_answer(1))
    run_look(project, "codex", images)
    prompt = prompt_of(log)
    assert "Alignment: Fail — badge and meta apart" in prompt
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
    assert "Widths: Fail — label too narrow" in prompt_of(log)


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
