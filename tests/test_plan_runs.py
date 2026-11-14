"""The run lines of a plan: how each changed call to an outside service ran against the real service."""

import re
from pathlib import Path

import plans
import pytest
from conftest import init

NO_SERVICE = "Real service: N/A — the fixture command calls no outside service.\n"
PASSED = (
    "Real service: Passed — records backend: one row was created and updated in "
    "one transaction on the test project, and the reply was read back.\n"
)
PLANNED = "Real service: Required — records backend: one create and update on the test project.\n"
AFTER_DEPLOY = (
    "Real service: Delivery — records backend: the deploy check writes one test row.\n"
)
ANCHOR = "E2E: Passed"


@pytest.fixture
def bare(completed_plan: str) -> str:
    assert NO_SERVICE in completed_plan
    return completed_plan.replace(NO_SERVICE, "")


def with_line(plan: str, line: str) -> str:
    return plan.replace(ANCHOR, line + ANCHOR)


def ready(plan: str) -> str:
    return plan.replace("Status: Complete", "Status: Ready").replace("[x]", "[ ]")


def stage(tmp_path: Path, plan: str, *, changed: bool = True) -> str:
    path = tmp_path / "PLAN.md"
    path.write_text(plan)
    return plans.validate_plan(path, changed=changed)


@pytest.mark.parametrize(
    ("line", "status"),
    [
        (PASSED, "Complete"),
        (NO_SERVICE, "Complete"),
        (PLANNED, "Ready"),
        ("Real service: N/A — the change edits a screen mockup only.\n", "Ready"),
        (
            "Real service: N/A — the change edits how a doubled charge is shown; it calls no outside service.\n",
            "Complete",
        ),
        (
            "Real service: Required — records backend: one write, then compare the reply with the fake.\n",
            "Ready",
        ),
        (
            "Real service: N/A — user, chat of 2026-11-14: the bank has no sandbox, so the fake stays the only proof.\n",
            "Complete",
        ),
        (
            "Real service: Passed — payments API: pending payment was created on the test account.\n",
            "Complete",
        ),
        (
            "Real service: Passed — records service: the command ran one time on the test patient; the fake matches the reply.\n",
            "Complete",
        ),
    ],
    ids=[
        "real-run",
        "no-outside-service",
        "planned",
        "mockup-is-not-a-mock",
        "doubled-is-not-a-test-double",
        "planned-run-can-name-the-fake",
        "the-user-skips-the-run",
        "evidence-can-start-with-the-word-pending",
        "evidence-can-say-that-the-fake-matches",
    ],
)
def test_a_plan_passes_with_its_real_service_run_stated(
    tmp_path: Path, bare: str, line: str, status: str
) -> None:
    """HE-REAL-SERVICE-RUN: a real run, a planned run or a reason that the change calls no outside service passes."""
    plan = with_line(bare, line)
    assert stage(tmp_path, plan if status == "Complete" else ready(plan)) == status


@pytest.mark.parametrize(
    ("line", "status", "error"),
    [
        ("", "Complete", "needs one 'Real service:' field"),
        ("", "Ready", "needs one 'Real service:' field"),
        (
            "Real service: done on staging\n",
            "Complete",
            "Real service needs Required, Passed or N/A",
        ),
        (PLANNED, "Complete", "Real service is still Required"),
        (
            "Real service: Passed — pending\n",
            "Complete",
            "Real service Passed needs what ran",
        ),
        (
            "Real service: Passed — records backend: pending\n",
            "Complete",
            "Real service Passed needs what ran",
        ),
        (
            "Real service: N/A — the tests use the project's fake of the backend.\n",
            "Complete",
            "is not the real service",
        ),
        (
            "Real service: N/A — every call is mocked.\n",
            "Ready",
            "is not the real service",
        ),
        (
            "Real service: N/A — user, the tests use a fake of the backend.\n",
            "Complete",
            "is not the real service",
        ),
        (
            "Real service: N/A — a test double covers the backend.\n",
            "Complete",
            "is not the real service",
        ),
        (AFTER_DEPLOY, "Complete", "Real service needs Required, Passed or N/A"),
        (
            "Real service: Passed — all tests passed.\n",
            "Complete",
            "Passed needs the name of the service first",
        ),
        (
            "Real service: Required — a run before the release.\n",
            "Ready",
            "Required needs the name of the service first",
        ),
    ],
    ids=[
        "proof-on-a-fake-and-no-line",
        "no-line-at-ready",
        "no-status",
        "planned-run-at-complete",
        "passed-with-no-evidence",
        "passed-with-a-service-and-no-evidence",
        "fake-as-the-reason",
        "mock-as-the-reason",
        "a-skip-with-no-place-of-the-decision",
        "test-double-as-the-reason",
        "a-run-after-the-deploy-is-too-late",
        "passed-with-no-service-named",
        "planned-with-no-service-named",
    ],
)
def test_a_plan_fails_when_its_real_service_run_is_missing_or_a_fake_is_the_reason(
    tmp_path: Path, bare: str, line: str, status: str, error: str
) -> None:
    plan = with_line(bare, line) + "\nDelivery target: Deploy\nDelivery: Pending\n"
    with pytest.raises(ValueError, match=re.escape(error)) as refusal:
        stage(tmp_path, plan if status == "Complete" else ready(plan))
    assert "With no approved test account, keep Required" in str(refusal.value)


def last_edited_before_the_update(_: Path) -> bool:
    return False


def test_a_complete_plan_from_before_the_real_service_rule_stays_valid(
    tmp_path: Path, bare: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert stage(tmp_path, bare, changed=False) == "Complete"
    with pytest.raises(ValueError, match="Real service"):
        stage(tmp_path, bare + "\nReopened for new work.\n")
    monkeypatch.setattr(plans, "touched_since_update", last_edited_before_the_update)
    assert stage(tmp_path, bare) == "Complete"


def test_an_unchanged_complete_plan_with_no_e2e_line_is_refused(
    tmp_path: Path, completed_plan: str
) -> None:
    plan = re.sub(r"(?m)^E2E:.*\n", "", completed_plan)
    with pytest.raises(ValueError, match="needs one 'E2E:' field"):
        stage(tmp_path, plan, changed=False)


@pytest.mark.parametrize(
    ("handoff", "blockers", "line", "unfinished"),
    [
        ("Approval", "None", "", True),
        ("Approval", "None", PLANNED, False),
        ("Clarification", "Which test project may the agent write to?", "", False),
    ],
    ids=["approval-no-line", "approval-with-a-planned-run", "question-no-line"],
)
def test_an_approval_handoff_waits_for_the_real_service_line(
    tmp_path: Path, bare: str, handoff: str, blockers: str, line: str, unfinished: bool
) -> None:
    root = tmp_path / "project"
    init(root)
    plan = (
        with_line(bare, line)
        .replace("Status: Complete", "Status: Draft")
        .replace("Blockers: None", f"Blockers: {blockers}")
        .replace("Handoff: Approval", f"Handoff: {handoff}")
    )
    (root / "PLAN.md").write_text(plan)
    notice, stuck = plans.planning_feedback(root, {"PLAN.md"})
    assert stuck is unfinished
    assert ("Real service" in notice) is unfinished
