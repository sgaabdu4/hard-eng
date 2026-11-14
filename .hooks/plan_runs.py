"""The E2E and Real service lines of a plan's Verification section; the form proves no truth."""

import re
from collections.abc import Callable

import plans

RUN_LINE = re.compile(r"(Required|Passed|Delivery|N/A) — (\S.*)")
NO_EVIDENCE = re.compile(r"(?i)^(pending|none|blocked|n/a)\b")
DEPLOY_TARGET = re.compile(r"(?im)^\s*(?:[-*+]\s+)?Delivery target:\s*Deploy\s*$")
SERVICE_FIRST = re.compile(r"[^:]*\S: \S")
NOT_REAL = re.compile(
    r"(?i)\b(?:fakes?|faked|mocks?|mocked|stubs?|stubbed|test doubles?|in-memory)\b"
)
E2E = "E2E"
REAL = "Real service"
REAL_HELP = (
    "write one line under Verification: `Real service: Required — <service>: <the "
    "calls that will run>`, `Real service: Passed — <service>: <what ran and what "
    "the service returned>` or `Real service: N/A — <reason that the change calls "
    "no outside service>`. With no approved test account, keep Required, set the "
    "plan to Draft and ask the user. If the user decides to skip the run, write "
    "`Real service: N/A — user, <place of the decision>: <reason>`"
)
FORMS = {
    E2E: (
        ("Required", "Passed", "Delivery", "N/A"),
        "concrete journey/evidence or reason",
        "run the journey and record Passed evidence",
        "actual runtime evidence",
    ),
    REAL: (
        ("Required", "Passed", "N/A"),
        "the real run, or the reason that the change calls no outside service",
        "run the changed calls one time against the real service and record Passed evidence",
        "what ran against the real service and what it returned",
    ),
}


def run_line(verification: str, name: str, status: str) -> tuple[str, str]:
    kinds, needs, run, evidence = FORMS[name]
    match = RUN_LINE.fullmatch(plans.field(verification, name))
    if match is None or match[1] not in kinds:
        raise ValueError(
            f"plan {name} needs {', '.join(kinds[:-1])} or {kinds[-1]} — {needs}"
        )
    if status == "Complete" and match[1] == "Required":
        raise ValueError(f"complete plan {name} is still Required; {run}")
    if match[1] == "Passed" and NO_EVIDENCE.match(match[2]):
        raise ValueError(f"plan {name} Passed needs {evidence}")
    if match[1] == "Delivery" and not DEPLOY_TARGET.search(verification):
        raise ValueError(
            f"delivery {name} requires Delivery target: Deploy and configured delivery checks"
        )
    return match[1], match[2]


def real_service(verification: str, status: str) -> None:
    kind, text = run_line(verification, REAL, status)
    if kind != "Required" and (word := NOT_REAL.search(text)):
        raise ValueError(
            f"plan {REAL} says '{word[0]}', and a fake is not the real service; do "
            "the run against the real service and describe only that run, because "
            "other words do not make a run on a fake real"
        )
    if kind != "N/A" and not SERVICE_FIRST.match(text):
        raise ValueError(f"plan {REAL} {kind} needs the name of the service first")


def run_errors(
    verification: str, status: str, legacy: bool, age: Callable[[], bool] | None
) -> list[str]:
    """A Complete plan from before the Real service rule stays valid: an unchanged one, and one last edited before the installed update."""
    errors = []
    try:
        run_line(verification, E2E, status)
    except ValueError as error:
        errors.append(f"Verification: {error}")
    try:
        if not legacy:
            real_service(verification, status)
    except ValueError as error:
        if age is None or age():
            errors.append(f"Verification: {error}; {REAL_HELP} (HE-REAL-SERVICE-RUN)")
    return errors
