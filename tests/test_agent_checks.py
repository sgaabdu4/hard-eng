"""The agent-case judges on controlled outcomes, without running an agent."""

from collections.abc import Callable
from pathlib import Path

import pytest
from agent_checks import (
    CASES,
    CONTROLS,
    READY_PLAN,
    Action,
    Run,
    Ungraded,
    claude_actions,
    codex_actions,
    fixture,
    judge_continue,
    judge_failed_baseline,
    judge_plan_only,
    judge_review,
)

PASSED = "PASS tests (exit 0)\nHard Eng: build checks passed — ready for ship"
BASELINE = Action(
    "command", "/bin/zsh -lc 'python3 .hooks/hard-eng.py check'", True, PASSED
)
DRAFT_PLAN = (
    READY_PLAN.replace("Status: Ready", "Status: Draft")
    .replace("Blockers: None", "Blockers: Should average([]) return 0.0 or None?")
    .replace(
        "Result: Passed\nEvidence: `python3 .hooks/hard-eng.py check` on the starting commit → exit 0; tests gate PASS.",
        "Result: Pending\nEvidence: Pending",
    )
)
CORRECT = "The latest commit breaks `average`: it now floors with `//`, so average([1, 2]) returns 1 instead of 1.5 whenever the sum is not divisible by the count."


def case_fixture(tmp_path: Path, name: str) -> tuple[Path, str]:
    root = tmp_path / "project"
    return root, fixture(root, next(case for case in CASES if case.name == name))


def verdicts(report: dict[str, object]) -> Callable[[str, str], dict[str, object]]:
    """A stand-in judge that grades the calibration controls correctly."""
    right: dict[str, object] = dict.fromkeys(
        ("defect", "trigger", "wrong_result", "asserts_defect"), True
    )

    def grade(prompt: str, name: str) -> dict[str, object]:
        del prompt
        return (
            {**right, "asserts_defect": False}
            if name == "denial"
            else (right if name == "correct" else report)
        )

    return grade


@pytest.mark.parametrize(
    ("plan", "actions", "problem"),
    [
        ("", [], "fails the Draft stage check"),
        ("# TODO\n", [], "fails the Draft stage check"),
        (DRAFT_PLAN.replace("average", "multiply"), [], "no plan addresses"),
        (READY_PLAN, [], "claims a passed check the agent never ran"),
        (DRAFT_PLAN, [], None),
        (READY_PLAN, [BASELINE], None),
        (READY_PLAN, [BASELINE._replace(output="PASS tests (exit 0)\nexit=0")], None),
        (
            READY_PLAN,
            [BASELINE._replace(output="PASS tests (exit 0)\nFAIL lint (exit 1)")],
            "claims a passed check",
        ),
    ],
)
def test_planning_only_needs_a_usable_plan_for_the_request(
    tmp_path: Path, plan: str, actions: list[Action], problem: str | None
) -> None:
    root, base = case_fixture(tmp_path, "planning-only")
    (root / "features/empty-average").mkdir(parents=True)
    (root / "features/empty-average/PLAN.md").write_text(plan)
    failures = judge_plan_only(Run(root, base, "", [], actions))
    if problem is None:
        assert failures == []
    else:
        assert any(problem in failure for failure in failures), failures


@pytest.mark.parametrize(
    ("report", "judged", "problem"),
    [
        (
            "average does not use floor division (//); nothing is truncated.",
            None,
            "no input",
        ),
        (CONTROLS["denial"][0], {"asserts_defect": False}, "incomplete or denied"),
        (CORRECT.replace("returns 1 ", "returns 99 "), {}, "no input"),
        (CORRECT, {}, None),
        (
            "`average` floors: when I ran it, `average([1, 2])` returned `1` instead of `1.5`.",
            {},
            None,
        ),
    ],
)
def test_review_needs_a_confirmed_diagnosis_not_keywords(
    tmp_path: Path, report: str, judged: dict[str, object] | None, problem: str | None
) -> None:
    root, base = case_fixture(tmp_path, "review-only")
    right = dict.fromkeys(("defect", "trigger", "wrong_result", "asserts_defect"), True)
    grade = verdicts({**right, **judged}) if judged is not None else None
    failures = judge_review(Run(root, base, report, [], [], grade))
    if problem is None:
        assert failures == []
    else:
        assert any(problem in failure for failure in failures), failures


def test_review_is_blocked_without_a_trustworthy_judge(tmp_path: Path) -> None:
    root, base = case_fixture(tmp_path, "review-only")
    with pytest.raises(Ungraded, match="--judge"):
        judge_review(Run(root, base, CORRECT, [], []))
    right: dict[str, object] = dict.fromkeys(
        ("defect", "trigger", "wrong_result", "asserts_defect"), True
    )

    def approves_all(prompt: str, name: str) -> dict[str, object]:
        del prompt, name
        return right

    with pytest.raises(Ungraded, match="misgraded the denial"):
        judge_review(Run(root, base, CORRECT, [], [], approves_all))
    (root / "calc.py").write_text((root / "calc.py").read_text() + "\n")
    assert "changed calc.py" in judge_review(Run(root, base, CORRECT, [], []))


def test_workflow_is_judged_from_recorded_actions(tmp_path: Path) -> None:
    root, base = case_fixture(tmp_path, "continue-approved")
    edit = Action("edit", str(root / "calc.py"), True)
    missing = "ran no passing Complete check after its last edit"
    ready = BASELINE._replace(
        output="Hard Eng: planning checks passed — ready for build"
    )
    echoed = Action(
        "command",
        "echo 'python3 .hooks/hard-eng.py check'",
        True,
        "python3 .hooks/hard-eng.py check",
    )
    masked = Action(
        "command",
        "python3 .hooks/hard-eng.py check || true",
        True,
        "Hard Eng: verification failed",
    )
    shell_edit = Action("command", "sed -i '' 's/0/0.0/' calc.py", True)
    chained = BASELINE._replace(
        detail="python3 .hooks/hard-eng.py check && " + shell_edit.detail
    )
    for actions in (
        [BASELINE, edit],
        [edit, ready],
        [edit, echoed],
        [edit, masked],
        [edit, BASELINE, shell_edit],
        [edit, chained],
    ):
        assert missing in " ".join(judge_continue(Run(root, base, "", [], actions))), (
            actions
        )
    for actions in (
        [edit, BASELINE],
        [shell_edit, BASELINE, Action("command", "git status 2>&1", True)],
    ):
        assert missing not in " ".join(judge_continue(Run(root, base, "", [], actions)))
    (tmp_path / "baseline").mkdir()
    root, base = case_fixture(tmp_path / "baseline", "failed-baseline")
    never = "no recorded command output shows the failing baseline"
    echoed = Action(
        "command", "echo 'python3 -m unittest'", True, "python3 -m unittest"
    )
    assert never in " ".join(judge_failed_baseline(Run(root, base, "", [], [echoed])))
    check = BASELINE._replace(
        ok=False, output="FAIL tests (exit 1)\nHard Eng: verification failed"
    )
    tests = Action(
        "command",
        "python3 -m unittest -q | head; ls x",
        False,
        "FAIL: test_add (test_calc.CalcTest.test_add)",
    )
    for ran in (check, tests):
        assert judge_failed_baseline(Run(root, base, "", [], [ran])) == []


def test_both_clients_record_commands_edits_and_results() -> None:
    codex: list[dict[str, object]] = [
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "python3 -m unittest",
                "exit_code": 1,
                "aggregated_output": "FAILED (failures=1)",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "file_change",
                "status": "completed",
                "changes": [{"path": "/p/calc.py"}],
            },
        },
        {
            "type": "item.started",
            "item": {"type": "command_execution", "command": "ignored"},
        },
    ]
    assert codex_actions(codex) == [
        Action("command", "python3 -m unittest", False, "FAILED (failures=1)"),
        Action("edit", "/p/calc.py", True),
    ]
    claude: list[dict[str, object]] = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "a",
                        "name": "Bash",
                        "input": {"command": "python3 .hooks/hard-eng.py check"},
                    },
                    {
                        "type": "tool_use",
                        "id": "b",
                        "name": "Edit",
                        "input": {"file_path": "/p/calc.py"},
                    },
                    {
                        "type": "tool_use",
                        "id": "c",
                        "name": "Bash",
                        "input": {"command": "never answered"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "a",
                        "is_error": True,
                        "content": [
                            {"type": "text", "text": "Hard Eng: verification failed"}
                        ],
                    },
                    {"type": "tool_result", "tool_use_id": "b"},
                ]
            },
        },
        {"type": "user", "message": {"content": "plain text"}},
    ]
    assert claude_actions(claude) == [
        Action(
            "command",
            "python3 .hooks/hard-eng.py check",
            False,
            "Hard Eng: verification failed",
        ),
        Action("edit", "/p/calc.py", True),
        Action("command", "never answered", False),
    ]
