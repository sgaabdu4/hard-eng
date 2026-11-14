"""A plan lists its sources and gives each item they name a status before it is ready."""

import re
from pathlib import Path

import plans
import pytest
from conftest import init

REVIEWED = "Reviewer: a second reader read both sources and the plan; its two missing roles are rows now."
PART = f"""## Sources + coverage
Sources: client call of 3 March, read in full; price sheet, read in full.
{REVIEWED}
Deliverables: one walkthrough video for the client.
- Role, night staff: In scope — Observe the configured command exit
- Screen, export: Later — client, call at 14:20
- Rule, two approvals: Proposal — one approval is enough; yes — User, chat of 4 March
"""
NO_SOURCES = "## Sources + coverage\nSources: N/A — the request is the only source.\n"
EXCLUDED = PART.replace(
    "price sheet, read in full",
    "price sheet, tabs 2 to 5 not read, excluded by the user in chat of 4 March",
)
NAMED = PART.replace("Later — client, call", "Later — client (the owner), call")
ONE_SOURCE = PART.replace("; price sheet, read in full", "").replace(
    REVIEWED, "Reviewer: N/A — one page of notes."
)
OPEN = PART.replace(
    "Later — client, call at 14:20", "Open — does the export wait for phase two?"
)
UNANSWERED = PART.replace(
    "one approval is enough; yes — User, chat of 4 March", "one approval is enough"
)
QUESTION = "Does the export wait for phase two?"
ANCHOR = "## Repository context"


@pytest.fixture
def bare(completed_plan: str) -> str:
    assert NO_SOURCES in completed_plan
    return completed_plan.replace(NO_SOURCES, "")


def with_part(plan: str, part: str) -> str:
    return plan.replace(ANCHOR, part + ANCHOR)


def ready(plan: str) -> str:
    return plan.replace("Status: Complete", "Status: Ready").replace("[x]", "[ ]")


def stage(tmp_path: Path, plan: str, *, changed: bool = True) -> str:
    path = tmp_path / "PLAN.md"
    path.write_text(plan)
    return plans.validate_plan(path, changed=changed)


@pytest.mark.parametrize(
    "part",
    [PART, NO_SOURCES, EXCLUDED, ONE_SOURCE, NAMED],
    ids=["rows", "no-sources", "part-excluded", "one-small-source", "named-decider"],
)
def test_a_ready_plan_passes_with_each_named_item_given_a_status(
    tmp_path: Path, bare: str, part: str
) -> None:
    """HE-SOURCE-COVERAGE: a filled part, or a reasoned N/A for a task with no source, is ready."""
    assert stage(tmp_path, ready(with_part(bare, part))) == "Ready"


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        (PART, "", "needs one '## Sources + coverage' section"),
        ("Sources: client call", "Origin: client call", "needs one 'Sources:' line"),
        (
            "price sheet, read in full",
            "price sheet, tabs 2 to 5 not read",
            "is not read in full",
        ),
        (
            "price sheet, read in full",
            "price sheet, not read in full",
            "is not read in full",
        ),
        (
            "Sources: client call of 3 March, read in full; price sheet, read in full.",
            "Sources: N/A — the request is the only source.",
            "holds no rows",
        ),
        ("Reviewer: a second", "Checked: a second", "needs one 'Reviewer:' line"),
        (
            REVIEWED,
            "Reviewer: N/A — the material is small.",
            "second reader is required",
        ),
        (
            REVIEWED,
            "Reviewer: Pending",
            "second reader is required",
        ),
        (
            ONE_SOURCE,
            ONE_SOURCE.replace(
                "Reviewer: N/A — one page of notes.", "Reviewer: Pending"
            ),
            "second reader has not run",
        ),
        ("Deliverables: one", "Videos: one", "needs one 'Deliverables:' line"),
        (PART[PART.index("- Role") :], "", "needs one row"),
        ("Later — client, call at 14:20", "wait for phase two", "has no status"),
        (
            "Later — client, call at 14:20",
            "Out — client, call at 14:20",
            "has no status",
        ),
        (
            "In scope — Observe the configured command exit",
            "In scope — Show the night roster",
            "points to no acceptance line",
        ),
        ("Later — client, call at 14:20", "Later — the team", "names no decider"),
        ("Later — client, call at 14:20", "Later — client", "names no decider"),
        (
            "Later — client, call at 14:20",
            "Later — clients of ours, call at 14:20",
            "names no decider",
        ),
        (
            "Later — client, call at 14:20",
            "Later — client did not decide, call at 14:20",
            "names no decider",
        ),
        ("; yes — User, chat of 4 March", "", "is a proposal with no answer"),
        (
            "; yes — User, chat of 4 March",
            "; yes — the team",
            "is a proposal with no answer",
        ),
        (PART, OPEN, "is an open question"),
    ],
    ids=[
        "no-part",
        "no-sources-line",
        "source-not-read",
        "source-not-read-in-full",
        "rows-under-no-sources",
        "no-reviewer-line",
        "no-second-reader-for-two-sources",
        "second-reader-pending",
        "second-reader-pending-for-one-source",
        "no-deliverables-line",
        "no-rows",
        "no-status",
        "old-out-status",
        "no-acceptance-line",
        "no-decider",
        "no-decision-place",
        "decider-word-inside-another-word",
        "decider-word-in-a-denial",
        "proposal-with-no-answer",
        "proposal-answered-by-nobody",
        "open-question",
    ],
)
def test_a_ready_plan_fails_on_a_gap_in_its_coverage_part(
    tmp_path: Path, bare: str, old: str, new: str, error: str
) -> None:
    part = ONE_SOURCE if old == ONE_SOURCE else PART
    plan = ready(with_part(bare, part)).replace(old, new)
    with pytest.raises(ValueError, match=re.escape(error)):
        stage(tmp_path, plan)


def test_a_ready_plan_with_an_open_row_stays_refused_with_its_question_in_blockers(
    tmp_path: Path, bare: str
) -> None:
    plan = ready(with_part(bare, OPEN)).replace(
        "Blockers: None", f"Blockers: {QUESTION}"
    )
    with pytest.raises(ValueError, match="unresolved Blockers"):
        stage(tmp_path, plan)


def test_a_complete_plan_from_before_the_rule_stays_valid(
    tmp_path: Path, bare: str
) -> None:
    assert stage(tmp_path, bare, changed=False) == "Complete"


def draft(plan: str, handoff: str, blockers: str) -> str:
    return (
        plan.replace("Status: Complete", "Status: Draft")
        .replace("Blockers: None", f"Blockers: {blockers}")
        .replace("Handoff: Approval", f"Handoff: {handoff}")
    )


@pytest.mark.parametrize(
    ("handoff", "blockers", "part", "unfinished"),
    [
        ("Approval", "None", "", True),
        ("Clarification", QUESTION, "", False),
        ("Approval", "None", PART, False),
        ("Approval", "None", OPEN, True),
        ("Approval", QUESTION, OPEN, False),
        ("Approval", f"One question waits.\n\n1. {QUESTION}", OPEN, False),
        ("Approval", "Screen, export: which file format?", OPEN, True),
        ("Approval", "Which colour does the logo get?", OPEN, True),
        ("Approval", "Which colour does the logo get?", UNANSWERED, True),
        (
            "Approval",
            "Rule, two approvals: is it right that one approval is enough?",
            UNANSWERED,
            False,
        ),
    ],
    ids=[
        "approval-no-part",
        "question-no-part",
        "approval-with-part",
        "open-row-not-asked",
        "open-row-asked-in-blockers",
        "open-row-asked-in-a-list-under-blockers",
        "open-row-under-another-question-on-its-item",
        "open-row-under-another-question",
        "proposal-under-another-question",
        "proposal-asked-in-blockers",
    ],
)
def test_an_approval_handoff_waits_for_the_coverage_part_and_for_each_question_to_be_asked(
    tmp_path: Path, bare: str, handoff: str, blockers: str, part: str, unfinished: bool
) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "PLAN.md").write_text(draft(with_part(bare, part), handoff, blockers))
    notice, stuck = plans.planning_feedback(root, {"PLAN.md"})
    assert stuck is unfinished
    assert ("Sources + coverage" in notice) is unfinished


COVERED = """## Sources + coverage
Sources: docs/call-notes.md, read in full; docs/marks-sheet.md, read in full.
Reviewer: a second reader read both files and the plan; no item is missing.
Deliverables: None
- Role, class teacher: In scope — class average
- Role, office manager: In scope — school average
- Role, head teacher: In scope — two approvals
- Role, teaching assistant: In scope — hides the marks of one pupil
- Team, exam team: In scope — two approvals
- Output, parent summary: Later — client, call notes point 5 (minute 18)
- Rule, holiday: In scope — holiday
- Rule, empty class shows no marks: In scope — no marks
## Repository context
"""


@pytest.mark.parametrize(
    ("old", "new", "failures"),
    [
        ("", "", []),
        (
            "- Rule, holiday: In scope — holiday\n",
            "",
            ["no coverage row names the holiday rule"],
        ),
        (
            "In scope — hides the marks of one pupil",
            "In scope — reads the pupil column",
            [
                "no coverage row names the marks of one pupil that assistants must not see"
            ],
        ),
        (
            "office manager: In scope — school average",
            "office manager: In scope — the report",
            ["no coverage row names the school average"],
        ),
        (
            "docs/marks-sheet.md, read in full",
            "the sheet, read in full",
            ["Sources never names marks-sheet"],
        ),
        (
            "Team, exam team: In scope — two approvals",
            "Team, exam team: Later — client, call notes point 4; two approvals",
            [
                "a decision that no source holds: - team, exam team: later — client, call notes point 4; two approvals"
            ],
        ),
        (
            "Team, exam team: In scope — two approvals",
            "Team, exam team: Proposal — one of the two approvals is enough; yes — user, chat",
            [
                "a decision that no source holds: - team, exam team: proposal — one of the two approvals is enough; yes — user, chat"
            ],
        ),
        (
            "Later — client, call notes point 5 (minute 18)",
            "In scope — parent summary",
            ["the parent summary is not Later by the client's decision"],
        ),
        (
            "Later — client, call notes point 5 (minute 18)",
            "Later — client (head teacher), call notes point 5 (minute 18)",
            [],
        ),
        (
            "- Role, head teacher: In scope — two approvals",
            "- Role, head teacher: Later — client (head teacher), call notes point 5",
            [],
        ),
        (
            "Team, exam team: In scope — two approvals",
            "Team, exam team: Later — client (head teacher), point 4; two approvals",
            [
                "a decision that no source holds: - team, exam team: later — client (head teacher), point 4; two approvals"
            ],
        ),
    ],
    ids=[
        "covered",
        "rule-left-out",
        "restriction-left-out",
        "outcome-left-out",
        "source-not-named",
        "own-exclusion-as-client",
        "own-proposal-as-answered",
        "client-decision-lost",
        "client-decision-with-a-name",
        "decider-row-of-the-client",
        "own-exclusion-under-the-name-of-the-decider",
    ],
)
def test_the_agent_case_judges_coverage_against_the_source_files(
    old: str, new: str, failures: list[str]
) -> None:
    from agent_fixtures import source_coverage_failures

    assert source_coverage_failures([COVERED.replace(old, new)]) == failures
