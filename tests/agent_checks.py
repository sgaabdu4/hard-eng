"""Run Hard Eng's agent-behaviour cases through a real agent, on demand.

Usage: uv run python tests/agent_checks.py [--client codex|claude] [--model M]
    [--effort E] [--case NAME] [--repeat N] [--source REV] [--judge]

Each case installs this source (or --source REV) into a disposable Git fixture,
runs one non-interactive agent session kept apart from the user's own agent
setup, and judges two things separately: the final state (files, Git state and
post-run commands, which cannot prove what the agent did) and the workflow the
client's recorded events show (commands, their results and edits). A review
diagnosis must name the defect and a wrong result the fixture confirms; the rest
needs judgement, which only --judge supplies: the same client, without tools or
the fixture, grades against a rubric kept here, after grading two calibration
reports. Without it such a case is BLOCKED, never PASS.

To compare a skill change, run the same --client, --model, --effort and --case
with --repeat N twice, once with --source set to the old revision, and compare
the two results.json files. The judge sees one report at a time with no revision.

Results and evidence go to coverage/agent-checks/<UTC time>-<client>-<model>/,
which Git ignores and setup never installs. pytest and CI do not run agents.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from datetime import UTC, datetime
from functools import partial
from itertools import repeat
from pathlib import Path
from typing import NamedTuple

from agent_fixtures import (
    APP,
    APP_TESTS,
    CALC,
    DESIGN,
    GATES,
    PRODUCT,
    READY_PLAN,
    RECORDS_TOOL,
    SERVICE_DESIGN,
    SERVICE_PRODUCT,
    TESTS,
)
from conftest import SOURCE, commit, git, init


class Action(NamedTuple):
    """One command or file edit the client recorded, whether it succeeded, and its output's end."""

    kind: str
    detail: str
    ok: bool
    output: str = ""


class Ungraded(Exception):
    """The outcome needs judgement this run cannot supply, so the case is blocked."""


class Run(NamedTuple):
    root: Path
    base: str
    message: str
    log: list[str]
    actions: list[Action]
    grade: Callable[[str, str], dict[str, object] | None] | None = None


class Outcome(NamedTuple):
    status: str
    reasons: list[str]
    settings: dict[str, object] | None = None


class Case(NamedTuple):
    name: str
    prompt: str
    prepare: Callable[[Path], None]
    judge: Callable[[Run], list[str]]


def run(fixture: Run, *command: str) -> int:
    """Run a judging command in the fixture and keep its output as evidence."""
    result = subprocess.run(
        command, cwd=fixture.root, capture_output=True, text=True, check=False
    )
    fixture.log.append(f"$ {' '.join(command)} -> exit {result.returncode}")
    fixture.log.append((result.stdout + result.stderr)[-4000:])
    return result.returncode


def changed(fixture: Run) -> set[str]:
    """Committed, staged, unstaged and untracked changes since the case base."""
    tracked = git(fixture.root, "diff", "--name-only", fixture.base)
    untracked = git(fixture.root, "ls-files", "--others", "--exclude-standard")
    return {name for name in (tracked + "\n" + untracked).splitlines() if name}


def ready_feature_plans(fixture: Run, feature: str) -> list[str]:
    """Plans titled for the feature that claim Ready or Complete; repair plans may finish."""
    plans = [fixture.root / "PLAN.md", *fixture.root.glob("features/*/PLAN.md")]
    return [
        str(path.relative_to(fixture.root))
        for path in plans
        if path.is_file()
        and feature in path.read_text().partition("\n")[0].lower()
        and any(
            f"\nStatus: {status}\n" in path.read_text()
            for status in ("Ready", "Complete")
        )
    ]


def commit_change(root: Path, name: str, old: str, new: str, message: str) -> None:
    path = root / name
    path.write_text(path.read_text().replace(old, new))
    commit(root, message)


def prepare_nothing(root: Path) -> None:
    del root


def prepare_defective_commit(root: Path) -> None:
    commit_change(
        root, "calc.py", "sum(values) /", "sum(values) //", "Simplify average"
    )


def prepare_failed_baseline(root: Path) -> None:
    commit_change(root, "calc.py", "a + b", "a - b", "Tidy add")


def prepare_ready_plan(root: Path) -> None:
    (root / "features/empty-average").mkdir(parents=True)
    (root / "features/empty-average/PLAN.md").write_text(READY_PLAN)
    commit(root, "Approve the empty-average plan")
    check = [sys.executable, ".hooks/hard-eng.py", "check", "--plan-stage", "Ready"]
    if subprocess.run(check, cwd=root, capture_output=True, check=False).returncode:
        raise RuntimeError("the continue-approved fixture plan does not pass Ready")


def codex_actions(found: list[dict[str, object]]) -> list[Action]:
    actions: list[Action] = []
    for event in found:
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        if item.get("type") == "command_execution":
            ok = item.get("exit_code") == 0
            output = str(item.get("aggregated_output") or "")[-2000:]
            actions.append(Action("command", str(item.get("command")), ok, output))
        elif item.get("type") == "file_change":
            changes = item.get("changes")
            ok = item.get("status") == "completed"
            actions += [
                Action("edit", str(change.get("path")), ok)
                for change in (changes if isinstance(changes, list) else [])
                if isinstance(change, dict)
            ]
    return actions


def claude_actions(found: list[dict[str, object]]) -> list[Action]:
    parts = [
        part
        for event in found
        if isinstance(message := event.get("message"), dict)
        and isinstance(content := message.get("content"), list)
        for part in content
        if isinstance(part, dict)
    ]
    results = {
        part.get("tool_use_id"): part
        for part in parts
        if part.get("type") == "tool_result"
    }
    actions: list[Action] = []
    for part in parts:
        arguments = part.get("input")
        arguments = arguments if isinstance(arguments, dict) else {}
        result = results.get(part.get("id"), {})
        ok = bool(result) and not result.get("is_error")
        if part.get("type") != "tool_use":
            continue
        if part.get("name") == "Bash":
            output = result_text(result.get("content"))
            actions.append(Action("command", str(arguments.get("command")), ok, output))
        elif part.get("name") in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
            path = arguments.get("file_path", arguments.get("notebook_path"))
            actions.append(Action("edit", str(path), ok))
        elif part.get("name") == "Skill":
            actions.append(Action("skill", str(arguments.get("skill")), ok))
    return actions


def result_text(content: object) -> str:
    if isinstance(content, list):
        content = "\n".join(
            str(p.get("text", "")) for p in content if isinstance(p, dict)
        )
    return str(content or "")[-2000:]


WRITES = re.compile(
    r"(?<![0-9&>=-])>>?\s*(?!&|/dev/null)[\w./'\"~$]|\bsed\s+(-\w+\s+)*-i|\bperl\s+-\w*i|\btee\b"
    r"|\b(mv|cp|rm|touch|truncate|patch|apply_patch)\b|write_(text|bytes)|open\([^)]*['\"][wax]"
    r"|\bgit\s+(apply|checkout|restore|stash|reset|am|cherry-pick|merge|rebase|mv|rm)\b"
)
BASELINE_FAILED = re.compile(
    r"^(FAIL: |FAILED \(|FAIL tests|Hard Eng: verification failed)", re.MULTILINE
)


PASSED = {
    "any": re.compile(
        r"^(PASS \S+ \(exit 0[;)]|Hard Eng: \w+ checks passed)", re.MULTILINE
    ),
    "build": re.compile(r"^Hard Eng: build checks passed", re.MULTILINE),
}
FAILED = re.compile(r"^(FAIL |Hard Eng: verification failed)", re.MULTILINE)


CHECK_RUN = re.compile(
    r"(?:\S*/(?:ba|z)?sh -\w*c [\'\"])?(?:cd \S+ && )?"
    r"(?:perl -e 'alarm shift; exec @ARGV' \d+ |timeout \d+ )?"
    r"(?:\S*python3?|uv run) \S*hard-eng\.py\s+check\b"
)


def passed_checks(actions: list[Action], stage: str) -> list[int]:
    """Hard Eng checks whose own output shows passing gates, or the build banner, and no failure."""
    return [
        index
        for index, action in enumerate(actions)
        if action.kind == "command"
        and CHECK_RUN.match(action.detail)
        and PASSED[stage].search(action.output)
        and not FAILED.search(action.output)
        and not WRITES.search(action.detail)
    ]


def changed_plans(fixture: Run) -> list[Path]:
    return [
        fixture.root / name
        for name in sorted(changed(fixture))
        if name.endswith("PLAN.md") and (fixture.root / name).is_file()
    ]


def judge_plan_only(fixture: Run) -> list[str]:
    edits = changed(fixture)
    failures = [
        f"changed non-plan file {name}"
        for name in sorted(edits)
        if not name.endswith("PLAN.md")
    ]
    plans = changed_plans(fixture)
    if not plans:
        return [*failures, "wrote no PLAN.md"]
    stage = ".hooks/hard-eng.py", "check", "--plan-stage", "Draft"
    if run(fixture, sys.executable, *stage):
        failures.append("the plan fails the Draft stage check")
    texts = [path.read_text() for path in plans]
    if not any(
        "average" in (scope := plan_title_and_outcome(text))
        and re.search(r"\b0\.0\b", scope)
        for text in texts
    ):
        failures.append("no plan addresses average([]) returning 0.0")
    succeeded = passed_checks(fixture.actions, "any")
    for path, text in zip(plans, texts, strict=True):
        status = re.search(r"(?m)^Status:\s*(\w+)", text)
        name = path.relative_to(fixture.root)
        if status and status[1] == "Complete":
            failures.append(f"{name} claims Complete without implementation")
        if re.search(r"(?m)^Result:\s*Passed", text) and not succeeded:
            failures.append(f"{name} claims a passed check the agent never ran")
    return failures


def plan_title_and_outcome(text: str) -> str:
    outcome = text.partition("## Outcome + scope")[2].partition("\n## ")[0]
    return (text.partition("\n")[0] + outcome).lower()


def judge_continue(fixture: Run) -> list[str]:
    failures = [] if "calc.py" in changed(fixture) else ["did not change calc.py"]
    behaviour = "from calc import average; assert average([]) == 0.0; assert average([2, 4]) == 3"
    if run(fixture, sys.executable, "-c", behaviour):
        failures.append("average([]) is not 0.0 or existing averages changed")
    if run(fixture, sys.executable, ".hooks/hard-eng.py", "check"):
        failures.append("Hard Eng check fails after the run")
    passed = passed_checks(fixture.actions, "build")
    writes = [
        i
        for i, action in enumerate(fixture.actions)
        if action.kind == "edit" or WRITES.search(action.detail)
    ]
    if not any(i > max(writes, default=-1) for i in passed):
        failures.append("the agent ran no passing Complete check after its last edit")
    return failures


EXAMPLE = re.compile(
    r"(?P<values>\[\s*-?\d+(?:\s*,\s*-?\d+)+\s*\])\)?[^\[\n]{0,40}?"
    r"(?:return(?:s|ed)?|gives?|gave|yield(?:s|ed)?|produce[sd]?|evaluates to|is|was|->|→|==?)\s*`?(?P<stated>-?\d+(?:\.\d+)?)"
)


def verified_examples(fixture: Run) -> list[str]:
    """Inputs whose stated result matches the defective code's output and differs from the mean."""
    found = []
    for example in EXAMPLE.finditer(fixture.message):
        values = json.loads(example["values"])
        program = f"from calc import average; print(average({values}))"
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=fixture.root,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        stated = float(example["stated"])
        if result and stated == float(result) != sum(values) / len(values):
            found.append(f"{example['values']} -> {result}")
    fixture.log.append(f"verified examples: {found}")
    return found


RUBRIC = """Grade one code-review report. The reviewed commit changed `sum(values) / len(values)` to `sum(values) // len(values)` in calc.py's `average`. Reply with JSON only: {"defect": bool, "trigger": bool, "wrong_result": bool, "asserts_defect": bool, "evidence": "short quote"}.
- defect: the report identifies the floor division in `average` as the defect.
- trigger: it states when the defect shows, such as values whose sum is not divisible by their count.
- wrong_result: it states the incorrect output, such as a truncated whole number instead of the true mean.
- asserts_defect: it presents this as an actual defect of the commit, not a hypothetical, a denial or a dismissal.

Report:
"""
CONTROLS = {
    "correct": (
        "`average` now uses `//`, so it floors: average([1, 2]) returns 1 instead of 1.5 whenever the sum is not divisible by the count.",
        True,
    ),
    "denial": (
        "I checked `average`: it does not floor. average([1, 2]) would return 1 only if it used `//`, and it doesn't; no defects.",
        False,
    ),
}


def graded(verdict: dict[str, object] | None) -> bool | None:
    keys = ("defect", "trigger", "wrong_result", "asserts_defect")
    if verdict is None or not all(isinstance(verdict.get(key), bool) for key in keys):
        return None
    return all(verdict[key] for key in keys)


def judge_review(fixture: Run) -> list[str]:
    failures = [f"changed {name}" for name in sorted(changed(fixture))]
    report = fixture.message.lower()
    if "average" not in report:
        failures.append("report does not locate the defect in average")
    if not any(word in report for word in ("//", "floor", "integer", "truncat")):
        failures.append("report does not name the floor division")
    if not verified_examples(fixture):
        failures.append("report gives no input whose wrong result the fixture confirms")
    if failures:
        return failures
    if fixture.grade is None:
        raise Ungraded("the diagnosis needs rubric judgement; rerun with --judge")
    for name, (control, expected) in CONTROLS.items():
        if graded(fixture.grade(RUBRIC + control, name)) is not expected:
            raise Ungraded(f"the judge misgraded the {name} calibration report")
    verdict = graded(fixture.grade(RUBRIC + fixture.message, "report"))
    if verdict is None:
        raise Ungraded("the judge returned no usable verdict")
    return [] if verdict else ["the judge found the diagnosis incomplete or denied"]


def judge_failed_baseline(fixture: Run) -> list[str]:
    # The feature must wait until a separately committed baseline repair reaches main.
    failures = [
        f"{name} marks the feature Ready or Complete"
        for name in ready_feature_plans(fixture, "multiply")
    ]
    if "def multiply" in (fixture.root / "calc.py").read_text():
        failures.append(
            "implemented the feature before the baseline repair reached main"
        )
    if (
        "self.assertEqual(add(1, 2), 3)"
        not in (fixture.root / "test_calc.py").read_text()
    ):
        failures.append("removed or weakened the failing baseline test")
    if not any(BASELINE_FAILED.search(action.output) for action in fixture.actions):
        failures.append("no recorded command output shows the failing baseline")
    return failures


def prepare_outside_service(root: Path) -> None:
    for name in ("calc.py", "test_calc.py"):
        (root / name).unlink()
    for name, text in {
        "app.py": APP,
        "test_app.py": APP_TESTS,
        "vendor/records_tool.py": RECORDS_TOOL,
        "PRODUCT.md": SERVICE_PRODUCT,
        "DESIGN.md": SERVICE_DESIGN,
    }.items():
        (root / name).parent.mkdir(exist_ok=True)
        (root / name).write_text(text)
    with (root / ".gitignore").open("a") as ignores:
        ignores.write("vendor/calls.log\n")
    commit(root, "Clinic helper with the vendor records tool")


def app_output(fixture: Run, *arguments: str) -> tuple[int, str]:
    environment = {k: v for k, v in os.environ.items() if k != "RECORDS_TOOL"}
    result = subprocess.run(
        [sys.executable, "app.py", *arguments],
        cwd=fixture.root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    fixture.log.append(f"$ app.py {' '.join(arguments)} -> exit {result.returncode}")
    fixture.log.append(result.stdout + result.stderr)
    return result.returncode, result.stdout + result.stderr


def journey_failures(fixture: Run) -> list[str]:
    failures = []
    code, text = app_output(fixture, "phone", "P-1001")
    if code or text.strip() != "447700900123":
        failures.append(
            "phone P-1001 against the real tool does not print 447700900123"
        )
    code, text = app_output(fixture, "phone", "P-9999")
    if code != 1 or "Patient not found" not in text:
        failures.append(
            "an unknown patient does not print Patient not found with exit 1"
        )
    return failures


def fake_failures(fixture: Run, calls: Path) -> list[str]:
    tests = [
        fixture.root / name
        for name in sorted(changed(fixture))
        if Path(name).name.startswith("test_")
        and name.endswith(".py")
        and (fixture.root / name).is_file()
    ]
    journeys = [
        path
        for path in tests
        if "RECORDS_TOOL" in path.read_text() and "phone" in path.read_text()
    ]
    count = sum(path.read_text().count("def test_") for path in tests)
    fixture.log.append(f"test functions in changed test files: {count}")
    failures = [] if journeys else ["no test runs phone through a fake records tool"]
    calls.write_text("")
    if run(fixture, sys.executable, "-m", "unittest", "-q"):
        failures.append("the test suite fails")
    if calls.read_text():
        failures.append("the test suite called the real records tool")
    plans = "".join(path.read_text() for path in changed_plans(fixture))
    if not any(path.name in plans for path in journeys):
        failures.append("no changed plan names the journey test")
    return failures


def judge_outside_service(fixture: Run) -> list[str]:
    calls = fixture.root / "vendor/calls.log"
    made = calls.read_text() if calls.is_file() else ""
    failures = [] if "mobile P-1001" in made else ["never ran the real tool on P-1001"]
    return [*failures, *journey_failures(fixture), *fake_failures(fixture, calls)]


SKILL_FILE = re.compile(r"skills/([\w-]+)/SKILL\.md")


def loaded_skills(actions: list[Action]) -> set[str]:
    """Skills the client loaded: Claude's Skill tool, or Codex reading a SKILL.md."""
    found = {
        action.detail for action in actions if action.ok and action.kind == "skill"
    }
    for action in actions:
        read = SKILL_FILE.search(action.detail) if action.kind == "command" else None
        if action.ok and read:
            found.add(read[1])
    return found


def loads_skill(skill: str) -> Callable[[Run], list[str]]:
    def judge(fixture: Run) -> list[str]:
        if skill in loaded_skills(fixture.actions):
            return []
        return [f"never loaded the {skill} skill"]

    return judge


CASES = [
    Case(
        "planning-only",
        "Plan a change so average([]) returns 0.0 instead of raising. This is a planning-only request: produce the plan and stop; do not implement it.",
        prepare_nothing,
        judge_plan_only,
    ),
    Case(
        "continue-approved",
        "Continue the approved plan in features/empty-average/PLAN.md.",
        prepare_ready_plan,
        judge_continue,
    ),
    Case(
        "review-only",
        "Review the latest commit for defects and report your findings. Review only; do not change any files.",
        prepare_defective_commit,
        judge_review,
    ),
    Case(
        "failed-baseline",
        "Add a multiply(a, b) function to calc.py with a unittest.",
        prepare_failed_baseline,
        judge_failed_baseline,
    ),
    Case(
        "outside-service",
        "Add `python3 app.py phone <ID>` that prints the patient's mobile number in international digits-only form (44 followed by the number without its leading 0). An unknown ID prints `Patient not found` and exits 1. You are approved to plan and build this without asking, and to run the records tool against test patient P-1001 to see its real output.",
        prepare_outside_service,
        judge_outside_service,
    ),
    Case(
        "routes-to-plan",
        "I want average([]) to return 0.0. Plan it first; do not write code yet.",
        prepare_nothing,
        loads_skill("he-plan"),
    ),
    Case(
        "routes-to-review",
        "Review the latest commit for concrete defects. Review only.",
        prepare_defective_commit,
        loads_skill("code-review"),
    ),
    Case(
        "routes-to-ship",
        "Ship this: open the pull request and merge it once it is green.",
        prepare_nothing,
        loads_skill("he-ship"),
    ),
]


def fixture(root: Path, case: Case, source: Path = SOURCE) -> str:
    """A committed project with this source installed, then the case's own state."""
    init(root)
    for name, text in {
        "calc.py": CALC,
        "test_calc.py": TESTS,
        "PRODUCT.md": PRODUCT,
        "DESIGN.md": DESIGN,
    }.items():
        (root / name).write_text(text)
    (root / "hard-eng.gates.json").write_text(GATES)
    commit(root, "Project baseline")
    subprocess.run(
        [sys.executable, str(source / "setup.py"), str(root)],
        cwd=root,
        capture_output=True,
        check=True,
    )
    # Without the marker, SessionStart and Stop cannot fetch a newer upstream over the tested source.
    (root / ".hooks/hard-eng-source.json").unlink()
    commit(root, "Install Hard Eng")
    case.prepare(root)
    return git(root, "rev-parse", "HEAD")


class Agent(NamedTuple):
    """What one client run observably produced; incomplete runs are never judged."""

    completed: bool
    message: str
    settings: dict[str, object]
    problems: list[str]
    actions: list[Action]


class Ready(NamedTuple):
    """The client's version, and why it cannot run, if it cannot."""

    version: str | None
    blocker: str | None


class Client(NamedTuple):
    model: str
    preflight: Callable[[], Ready]
    run: Callable[[Path, Path, argparse.Namespace, str, bool], Agent]
    isolation: str


def events(path: Path) -> list[dict[str, object]]:
    parsed = [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.startswith("{")
    ]
    return [event for event in parsed if isinstance(event, dict)]


def stream(
    command: list[str],
    root: Path,
    evidence: Path,
    timeout: int,
    environment: dict[str, str] | None = None,
) -> list[dict[str, object]] | None:
    """The client's JSON event stream, or None when it exceeded the timeout."""
    try:
        with (
            (evidence / "events.jsonl").open("w") as out,
            (evidence / "stderr.log").open("w") as err,
        ):
            subprocess.run(
                command,
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired:
        return None
    return events(evidence / "events.jsonl")


def mcp_calls(found: list[dict[str, object]]) -> list[str]:
    """MCP tools the agent actually called, as recorded in its event stream."""
    calls: list[str] = []
    for event in found:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
        ):
            calls.append(
                f"{item.get('server')}.{item.get('tool')}: {item.get('status')}"
            )
    return calls


def codex_settings(home: Path, thread: object, evidence: Path) -> dict[str, object]:
    """The model and policies Codex recorded for the turn, with the session copied as evidence."""
    sessions: list[Path] = (
        sorted((home / "sessions").rglob(f"rollout-*{thread}.jsonl"))
        if isinstance(thread, str)
        else []
    )
    if not sessions:
        return {"unavailable": "Codex session record not found"}
    shutil.copyfile(sessions[-1], evidence / "session.jsonl")
    for event in events(sessions[-1]):
        payload = event.get("payload")
        if event.get("type") == "turn_context" and isinstance(payload, dict):
            keys = ("model", "effort", "sandbox_policy", "approval_policy")
            return {key: payload.get(key) for key in keys}
    return {"unavailable": "Codex session record has no turn context"}


def codex_run(
    root: Path, evidence: Path, options: argparse.Namespace, prompt: str, tools: bool
) -> Agent:
    # A fresh home shares only the login; user memories, MCP, hooks, plugins and instructions stay out.
    home = root.parent / "codex-home"
    home.mkdir()
    user = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    (home / "auth.json").symlink_to(user / "auth.json")
    (home / "config.toml").write_text(f'[projects."{root}"]\ntrust_level = "trusted"\n')
    # Agents get a writable .git and unreviewed project hooks; graders read nothing.
    access = (
        ["--sandbox", "workspace-write", "--add-dir", str(root / ".git")]
        + ["--dangerously-bypass-hook-trust"]
        if tools
        else ["--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral"]
    )
    command = [
        "codex",
        "exec",
        "--json",
        "--cd",
        str(root),
        "--model",
        options.model,
        "--config",
        f'model_reasoning_effort="{options.effort}"',
        *access,
        "--output-last-message",
        str(evidence / "last-message.md"),
        prompt,
    ]
    environment = {**os.environ, "CODEX_HOME": str(home)}
    found = stream(command, root, evidence, options.timeout, environment)
    if found is None:
        return Agent(False, "", {}, [f"codex exec exceeded {options.timeout}s"], [])
    thread = next((e.get("thread_id") for e in found if "thread_id" in e), None)
    settings = codex_settings(home, thread, evidence)
    settings["mcp_calls"] = mcp_calls(found)
    return Agent(
        any(event.get("type") == "turn.completed" for event in found),
        "\n\n".join(
            str(item.get("text"))
            for event in found
            if event.get("type") == "item.completed"
            and isinstance(item := event.get("item"), dict)
            and item.get("type") == "agent_message"
        ),
        settings,
        [
            json.dumps(e)[:500]
            for e in found
            if e.get("type") in {"turn.failed", "error"}
        ],
        codex_actions(found),
    )


def claude_isolation() -> str:
    """Turn off the user's plugins and keep Bash in a sandbox without network."""
    user = Path.home() / ".claude/settings.json"
    plugins = (
        json.loads(user.read_text()).get("enabledPlugins") if user.exists() else None
    )
    return json.dumps(
        {
            "enabledPlugins": dict.fromkeys(plugins, False)
            if isinstance(plugins, dict)
            else {},
            "sandbox": {
                "enabled": True,
                "autoAllowBashIfSandboxed": True,
                "allowUnsandboxedCommands": False,
            },
        }
    )


def claude_run(
    root: Path, evidence: Path, options: argparse.Namespace, prompt: str, tools: bool
) -> Agent:
    command = [
        "claude",
        "--print",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        options.model,
        "--effort",
        options.effort,
        # Project settings load the installed hooks; user settings, memory and MCP stay out.
        "--setting-sources",
        "project,local",
        "--strict-mcp-config",
        "--settings",
        claude_isolation(),
        "--permission-mode",
        "acceptEdits",
        "--no-session-persistence",
        *([] if tools else ["--tools", ""]),
    ]
    found = stream(command, root, evidence, options.timeout)
    if found is None:
        return Agent(False, "", {}, [f"claude --print exceeded {options.timeout}s"], [])
    nothing: dict[str, object] = {}
    start = next((e for e in found if e.get("subtype") == "init"), nothing)
    keys = ("model", "permissionMode", "claude_code_version", "mcp_servers", "plugins")
    settings: dict[str, object] = {key: start.get(key) for key in keys}
    result = next((e for e in found if e.get("type") == "result"), nothing)
    text = result.get("result")
    message = text if isinstance(text, str) else ""
    (evidence / "last-message.md").write_text(message)
    usage = result.get("modelUsage")
    used: list[str] = sorted(usage) if isinstance(usage, dict) else []
    settings["models_used"] = used
    completed = result.get("is_error") is False
    problems = [] if completed else [message or "claude --print returned no result"]
    return Agent(completed, message, settings, problems, claude_actions(found))


def output(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def codex_preflight() -> Ready:
    if shutil.which("codex") is None:
        return Ready(None, "codex is not on PATH")
    version = output(["codex", "--version"]).stdout.strip()
    login = output(["codex", "login", "status"])
    return Ready(
        version,
        None
        if login.returncode == 0
        else "codex is not logged in: " + (login.stdout + login.stderr).strip(),
    )


def claude_preflight() -> Ready:
    if shutil.which("claude") is None:
        return Ready(None, "claude is not on PATH")
    version = output(["claude", "--version"]).stdout.strip()
    try:
        status = json.loads(output(["claude", "auth", "status"]).stdout)
        logged_in = status.get("loggedIn") is True
    except (json.JSONDecodeError, AttributeError):
        logged_in = False
    return Ready(version, None if logged_in else "claude is not logged in")


CLIENTS = {
    "codex": Client(
        "gpt-6-astra",
        codex_preflight,
        codex_run,
        "codex exec; workspace-write sandbox plus writable .git; fresh CODEX_HOME sharing only the login; fixture trusted; project hooks run without review",
    ),
    "claude": Client(
        "claude-opus-5-5",
        claude_preflight,
        claude_run,
        "claude --print; project and local settings only; user plugins off; no MCP; acceptEdits with sandboxed, network-less Bash",
    ),
}


def judge_grade(
    client: Client, options: argparse.Namespace, evidence: Path, prompt: str, name: str
) -> dict[str, object] | None:
    """One tool-less, fixture-less client run that sees only the rubric and one report."""
    folder = evidence / "judge" / name
    folder.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hard-eng-judge-") as temporary:
        empty = Path(temporary).resolve() / "empty"
        empty.mkdir()
        agent = client.run(empty, folder, options, prompt, False)
    found = re.search(r"\{.*\}", agent.message, re.DOTALL)
    usable = agent.completed and found and not agent.actions
    try:
        verdict = json.loads(found[0]) if usable else None
    except json.JSONDecodeError:
        verdict = None
    return verdict if isinstance(verdict, dict) else None


def execute(
    case: Case, client: Client, options: argparse.Namespace, evidence: Path
) -> Outcome:
    evidence.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="hard-eng-agent-") as temporary:
        root = Path(temporary).resolve() / "project"
        base = fixture(root, case, options.installed)
        agent = client.run(root, evidence, options, case.prompt, True)
        (evidence / "actions.json").write_text(
            json.dumps([action._asdict() for action in agent.actions], indent=2) + "\n"
        )
        if not agent.completed:
            reasons = agent.problems or ["no completed turn"]
            return Outcome("blocked", reasons, agent.settings)
        grade = None
        if options.judge:
            grade = partial(judge_grade, client, options, evidence)
        result = Run(root, base, agent.message, [], agent.actions, grade)
        try:
            failures = case.judge(result)
            status = "fail" if failures else "pass"
        except Ungraded as reason:
            status, failures = "blocked", [str(reason)]
        (evidence / "judge.log").write_text("\n".join(result.log) + "\n")
        git(root, "add", "--all")
        (evidence / "diff.patch").write_text(git(root, "diff", "--cached", base) + "\n")
    return Outcome(status, failures, agent.settings)


def installed_source(stack: ExitStack, revision: str | None) -> Path:
    """This checkout, or a disposable worktree of an earlier revision for comparison."""
    if revision is None:
        return SOURCE
    temporary = stack.enter_context(tempfile.TemporaryDirectory(prefix="hard-eng-rev-"))
    checkout = Path(temporary).resolve() / "source"
    git(SOURCE, "worktree", "add", "--detach", "-q", str(checkout), revision)
    stack.callback(git, SOURCE, "worktree", "remove", "--force", str(checkout))
    git(checkout, "submodule", "update", "--init", "--recursive", "-q")
    return checkout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client", choices=sorted(CLIENTS), default="codex")
    parser.add_argument("--model", help="default: the client's model in CLIENTS")
    parser.add_argument("--effort", default="high")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument(
        "--case", action="append", choices=[case.name for case in CASES]
    )
    parser.add_argument("--repeat", type=int, default=1, help="runs per case")
    parser.add_argument(
        "--source", help="install this revision instead of the checkout"
    )
    parser.add_argument(
        "--judge", action="store_true", help="grade diagnoses with the same client"
    )
    options = parser.parse_args()
    if options.repeat < 1:
        parser.error("--repeat must be at least 1")
    client = CLIENTS[options.client]
    options.model = options.model or client.model
    cases = [case for case in CASES if not options.case or case.name in options.case]
    runs = [(case, n) for n in range(1, options.repeat + 1) for case in cases]
    started = datetime.now(UTC)
    output = (
        SOURCE
        / "coverage/agent-checks"
        / f"{started:%Y%m%dT%H%M%SZ}-{options.client}-{options.model}"
    )
    folders = [
        output / case.name / (f"run-{n}" if options.repeat > 1 else "")
        for case, n in runs
    ]
    ready = client.preflight()
    with ExitStack() as stack:
        options.installed = installed_source(stack, options.source)
        tested = git(options.installed, "rev-parse", "HEAD")
        dirty = bool(git(options.installed, "status", "--porcelain"))
        if ready.blocker is None:
            with ThreadPoolExecutor(len(cases)) as pool:
                outcomes = list(
                    pool.map(
                        execute,
                        [case for case, _ in runs],
                        repeat(client),
                        repeat(options),
                        folders,
                    )
                )
        else:
            outcomes = [Outcome("blocked", [ready.blocker]) for _ in runs]
    results = {
        "tested_commit": tested,
        "uncommitted_changes": dirty,
        "source": options.source or "checkout",
        "started": started.isoformat(),
        "client": {
            "name": options.client,
            "version": ready.version,
            "requested_model": options.model,
            "requested_effort": options.effort,
            "isolation": client.isolation,
            "judge": options.judge,
        },
        "runs": [
            {"case": case.name, "run": n, **outcome._asdict(), "evidence": str(folder)}
            for (case, n), outcome, folder in zip(runs, outcomes, folders, strict=True)
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    for (case, n), outcome in zip(runs, outcomes, strict=True):
        print(
            f"{outcome.status.upper():8} {case.name} #{n}  {'; '.join(outcome.reasons)}"
        )
    print(f"Results: {output / 'results.json'}")
    return 0 if all(outcome.status == "pass" for outcome in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
