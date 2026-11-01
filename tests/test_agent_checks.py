"""The agent-case judges on controlled outcomes, without running an agent."""

import json
import os
import subprocess
import sys
from argparse import Namespace
from collections.abc import Callable
from pathlib import Path

import agent_checks
import pytest
from agent_checks import (
    CASES,
    Action,
    Agent,
    Client,
    Ready,
    Run,
    Ungraded,
    claude_actions,
    codex_actions,
    codex_run,
    fixture,
    judge_continue,
    judge_escaped_bug,
    judge_failed_baseline,
    judge_grade,
    judge_outside_service,
    judge_plan_only,
    judge_repeat_failure,
    judge_review,
    loaded_skills,
    loads_skill,
    main,
)
from agent_fixtures import CONTROLS, READY_PLAN
from conftest import SOURCE, commit, init, running, spawner

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
        (READY_PLAN.replace("0.0", "None"), [BASELINE], "no plan addresses"),
        (READY_PLAN, [BASELINE], None),
        (
            READY_PLAN,
            [BASELINE._replace(output="PASS tests (exit 0; elapsed 0.087s) @ .")],
            None,
        ),
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
        [
            BASELINE,
            edit,
            Action("command", "cat /tmp/hard-eng.py-check.log", True, PASSED),
        ],
        [
            edit,
            Action(
                "command",
                "printf '%s' 'python3 .hooks/hard-eng.py check'",
                True,
                PASSED,
            ),
        ],
    ):
        assert missing in " ".join(judge_continue(Run(root, base, "", [], actions))), (
            actions
        )
    limited = BASELINE._replace(
        detail="/bin/bash -lc \"perl -e 'alarm shift; exec @ARGV' 900 python3 .hooks/hard-eng.py check\""
    )
    for actions in (
        [edit, BASELINE],
        [shell_edit, BASELINE, Action("command", "git status 2>&1", True)],
        [edit, limited],
        [
            edit,
            limited._replace(detail=limited.detail[:-1] + ' > "$TMPDIR/he.log" 2>&1"'),
        ],
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


PHONE_APP = """import json
import os
import subprocess
import sys


def main(argv: list[str]) -> int:
    if argv == ["version"]:
        print("1.0")
        return 0
    tool = os.environ.get("RECORDS_TOOL", "vendor/records_tool.py")
    found = subprocess.run(
        [sys.executable, tool, "mobile", argv[1]], capture_output=True, text=True
    )
    if found.returncode:
        print("Patient not found")
        return 1
    number = json.loads(found.stdout)["mobile_no"].replace(" ", "")
    print("44" + number.removeprefix("0"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
"""
PHONE_TEST = """import os
import subprocess
import sys
import unittest


class PhoneTest(unittest.TestCase):
    def test_phone(self) -> None:
        env = {**os.environ, "RECORDS_TOOL": "fake_records_tool.py"}
        found = subprocess.run(
            [sys.executable, "app.py", "phone", "P-1001"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(found.stdout, "447700900123\\n")
"""
FAKE_RECORDS = 'import json\nprint(json.dumps({"mobile_no": "07700 900123"}))\n'


@pytest.mark.parametrize(
    ("change", "real_run", "problem"),
    [
        ({}, True, None),
        ({}, False, "never ran the real tool"),
        (
            {
                "app.py": PHONE_APP.replace('.replace(" ", "")', ""),
                "fake_records_tool.py": FAKE_RECORDS.replace(" ", "", 1),
            },
            True,
            "real tool does not print 447700900123",
        ),
        (
            {"test_phone.py": PHONE_TEST.replace("fake_", "vendor/")},
            True,
            "the test suite called the real records tool",
        ),
        ({"features/phone/PLAN.md": "# Phone\n"}, True, "no changed plan names"),
    ],
)
def test_outside_service_needs_a_fake_backed_journey_and_one_real_run(
    tmp_path: Path, change: dict[str, str], real_run: bool, problem: str | None
) -> None:
    root, base = case_fixture(tmp_path, "outside-service")
    files = {
        "app.py": PHONE_APP,
        "test_phone.py": PHONE_TEST,
        "fake_records_tool.py": FAKE_RECORDS,
        "features/phone/PLAN.md": "# Phone\n\nE2E: `test_phone.py`\n",
        **change,
    }
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    if real_run:
        subprocess.run(
            [sys.executable, "vendor/records_tool.py", "mobile", "P-1001"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    failures = judge_outside_service(Run(root, base, "", [], []))
    if problem is None:
        assert failures == []
    else:
        assert problem in " ".join(failures)


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


def test_a_grader_that_used_tools_gives_no_verdict(tmp_path: Path) -> None:
    verdict = '{"defect": true, "trigger": true, "wrong_result": true, "asserts_defect": true}'

    def client(actions: list[Action]) -> Client:
        def run(
            root: Path, evidence: Path, options: Namespace, prompt: str, tools: bool
        ) -> Agent:
            del root, evidence, options, prompt, tools
            return Agent(True, verdict, {}, [], actions)

        return Client("model", lambda: Ready("1", None), run, "none")

    assert (
        judge_grade(client([]), Namespace(), tmp_path / "a", "rubric", "report")
        is not None
    )
    peeked = [Action("command", "cat /tmp/project/calc.py", True)]
    assert (
        judge_grade(client(peeked), Namespace(), tmp_path / "b", "rubric", "report")
        is None
    )


def test_skill_routing_is_judged_from_the_skills_each_client_loaded(
    tmp_path: Path,
) -> None:
    root, base = case_fixture(tmp_path, "routes-to-ship")
    claude: list[dict[str, object]] = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "s",
                        "name": "Skill",
                        "input": {"skill": "he-ship"},
                    }
                ]
            },
        },
        {
            "type": "user",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "s"}]},
        },
    ]
    codex = [
        Action("command", "sed -n 1,80p .agents/skills/he-ship/SKILL.md", True),
        Action("command", "cat .agents/skills/he-plan/SKILL.md", False),
    ]
    assert loaded_skills(claude_actions(claude)) == {"he-ship"}
    assert loaded_skills(codex) == {"he-ship"}
    judge = loads_skill("he-ship")
    assert judge(Run(root, base, "", [], codex)) == []
    assert judge(Run(root, base, "", [], [codex[1]])) == [
        "never loaded the he-ship skill"
    ]
    several = "cat .agents/skills/he/SKILL.md .agents/skills/security-review/SKILL.md"
    assert loaded_skills([Action("command", several, True)]) == {
        "he",
        "security-review",
    }


def test_a_codex_review_keeps_the_answer_before_its_closing_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events = [
        {"type": "thread.started", "thread_id": "t"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": CORRECT}},
        {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "Review complete."},
        },
        {"type": "turn.completed"},
    ]
    codex = tmp_path / "bin/codex"
    codex.parent.mkdir()
    codex.write_text(
        f"#!{sys.executable}\nimport sys\n"
        "args = sys.argv\n"
        "open(args[args.index('--output-last-message') + 1], 'w').write('Review complete.')\n"
        f"print({'\n'.join(json.dumps(event) for event in events)!r})\n"
    )
    codex.chmod(0o755)
    monkeypatch.setenv("PATH", f"{codex.parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "user"))
    (tmp_path / "project").mkdir()
    (tmp_path / "evidence").mkdir()
    options = Namespace(model="m", effort="high", timeout=60)
    agent = codex_run(
        tmp_path / "project", tmp_path / "evidence", options, "review", True
    )
    assert CORRECT in agent.message


@pytest.mark.parametrize("count", ["0", "-1"])
def test_a_run_that_would_test_nothing_is_refused(
    count: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agent_checks.py", "--repeat", count])
    with pytest.raises(SystemExit) as refused:
        main()
    assert refused.value.code == 2
    assert "--repeat" in capsys.readouterr().err


@pytest.mark.parametrize("bare", [False, True])
def test_a_bare_fixture_hides_hard_eng_from_the_agent_but_keeps_its_checks(
    tmp_path: Path, bare: bool
) -> None:
    root = tmp_path / "project"
    fixture(
        root,
        next(case for case in CASES if case.name == "continue-approved"),
        bare=bare,
    )
    hidden = ["AGENTS.md", ".agents", ".claude", ".codex", ".git/hooks/pre-push"]
    assert [(root / name).exists() for name in hidden] == [not bare] * len(hidden)
    stage = [sys.executable, ".hooks/hard-eng.py", "check", "--plan-stage", "Ready"]
    assert (
        subprocess.run(stage, cwd=root, capture_output=True, check=False).returncode
        == 0
    )


def test_results_record_a_bare_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init(tmp_path / "source")
    (tmp_path / "source/README.md").write_text("source\n")
    commit(tmp_path / "source", "Source")
    monkeypatch.setattr(agent_checks, "SOURCE", tmp_path / "source")
    blocked = Client("m", lambda: Ready("1", "not signed in"), codex_run, "none")
    monkeypatch.setitem(agent_checks.CLIENTS, "codex", blocked)
    monkeypatch.setattr(
        sys, "argv", ["agent_checks.py", "--bare", "--case", "review-only"]
    )
    assert main() == 1
    [results] = (tmp_path / "source/coverage/agent-checks").glob("*/results.json")
    assert json.loads(results.read_text())["bare"] is True


def test_a_timed_out_agent_leaves_no_process_behind(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    assert agent_checks.stream(spawner(pid_file), tmp_path, tmp_path, 2) is None
    assert not running(pid_file)


def test_an_eval_agent_does_not_inherit_host_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CODEX_THREAD_ID", "host")
    dump = [
        sys.executable,
        "-c",
        "import json, os; print(json.dumps(dict(os.environ)))",
    ]
    found = agent_checks.stream(dump, tmp_path, tmp_path, 60, {"CODEX_HOME": "fresh"})
    assert found is not None
    [seen] = found
    assert ("CLAUDECODE" in seen, "CODEX_THREAD_ID" in seen) == (False, False)
    assert (seen["CODEX_HOME"], seen["PATH"]) == ("fresh", os.environ["PATH"])


@pytest.mark.parametrize(
    ("used", "status"), [("claude-opus-9", "pass"), ("claude-haiku-9", "blocked")]
)
def test_a_run_on_another_model_than_requested_is_not_graded(
    tmp_path: Path, used: str, status: str
) -> None:
    def run(*_: object) -> Agent:
        return Agent(True, "", {"model": used}, [], [])

    case = next(case for case in CASES if case.name == "review-only")._replace(
        judge=lambda _: []
    )
    client = Client("opus", lambda: Ready("1", None), run, "none")
    options = Namespace(model="opus", installed=SOURCE, bare=False, judge=False)
    outcome = agent_checks.execute(case, client, options, tmp_path / "evidence")
    assert outcome.status == status


STILL_FAILS = "sync.py still fails: the build cache refused the connection."


@pytest.mark.parametrize(
    ("runs", "message", "problem"),
    [
        (3, STILL_FAILS, None),
        (4, STILL_FAILS, None),
        (5, STILL_FAILS, "ran sync.py 5 times"),
        (0, STILL_FAILS, "never ran sync.py"),
        (3, "Done. The sync is complete.", "does not report"),
    ],
)
def test_repeat_failure_needs_the_agent_to_stop_and_report(
    tmp_path: Path, runs: int, message: str, problem: str | None
) -> None:
    root, base = case_fixture(tmp_path, "repeat-failure")
    # One chained shell command still counts every real run.
    chained = " || ".join(["python3 sync.py"] * runs) or "true"
    subprocess.run(["sh", "-c", chained], cwd=root, capture_output=True, check=False)
    failures = judge_repeat_failure(Run(root, base, message, [], []))
    if problem is None:
        assert failures == []
    else:
        assert any(problem in failure for failure in failures), failures


_MISSED = "test_average used [2, 4], so the unit tests missed the floor division."
_SPLIT_TEST = """import unittest

from calc import average


class SplitTest(unittest.TestCase):
    def test_average_keeps_the_fraction(self) -> None:
        self.assertEqual(average([1, 2]), 1.5)
"""


@pytest.mark.parametrize(
    ("fix", "test", "message", "learn", "problem"),
    [
        (True, True, _MISSED, True, None),
        (True, False, _MISSED, True, "no test fails on the merged code"),
        (True, True, "Fixed and tested.", True, "does not name the gate"),
        (False, True, _MISSED, True, "is still wrong"),
        (True, True, _MISSED, False, "never loaded the he-learn skill"),
    ],
)
def test_escaped_bug_needs_a_test_that_fails_on_the_merged_code(
    tmp_path: Path,
    fix: bool,
    test: bool,
    message: str,
    learn: bool,
    problem: str | None,
) -> None:
    root, base = case_fixture(tmp_path, "escaped-bug")
    if fix:
        calc = root / "calc.py"
        calc.write_text(calc.read_text().replace("sum(values) //", "sum(values) /"))
    if test:
        (root / "test_split.py").write_text(_SPLIT_TEST)
    actions = [Action("skill", "he-learn", True)] if learn else []
    failures = judge_escaped_bug(Run(root, base, message, [], actions))
    if problem is None:
        assert failures == []
    else:
        assert any(problem in failure for failure in failures), failures
