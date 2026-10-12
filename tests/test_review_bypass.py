"""Admin review bypass refuses any merge requirement besides the review."""

import pytest
import shipping
from gate_config import JsonValue

EMPTY: JsonValue = {"totalCount": 0, "nodes": []}


def nodes(*items: JsonValue) -> JsonValue:
    return {"totalCount": len(items), "nodes": list(items)}


def protection(**changes: JsonValue) -> JsonValue:
    rule: dict[str, JsonValue] = {
        "requiresCommitSignatures": False,
        "requiresDeployments": False,
        "lockBranch": False,
        "requiresStrictStatusChecks": False,
    }
    return {"branchProtectionRule": rule | changes, "rules": EMPTY}


def required_rule(context: str, strict: JsonValue = False) -> JsonValue:
    parameters: dict[str, JsonValue] = {"requiredStatusChecks": [{"context": context}]}
    if strict is not None:
        parameters["strictRequiredStatusChecksPolicy"] = strict
    rule: JsonValue = {"type": "REQUIRED_STATUS_CHECKS", "parameters": parameters}
    return {"branchProtectionRule": None, "rules": nodes(rule)}


def ruleset(*types: str) -> JsonValue:
    rules: list[JsonValue] = [{"type": kind} for kind in types]
    return {"rules": nodes(*rules)}


BUILD: JsonValue = {"name": "build", "conclusion": "SUCCESS"}


@pytest.mark.parametrize(
    ("pull", "contexts", "message"),
    [
        ({}, nodes(BUILD), None),
        ({"reviewThreads": nodes({"isResolved": True})}, nodes(BUILD), None),
        ({"reviewThreads": nodes({"isResolved": False})}, nodes(BUILD), "unresolved"),
        ({"reviewThreads": {"totalCount": 2, "nodes": []}}, nodes(BUILD), "unresolved"),
        ({"isMergeQueueEnabled": True}, nodes(BUILD), "merge queue"),
        ({"isMergeQueueEnabled": None}, nodes(BUILD), "merge queue"),
        ({"baseRef": None}, nodes(BUILD), "unreadable"),
        ({"baseRef": {"rules": {"totalCount": 101, "nodes": []}}}, EMPTY, "unreadable"),
        ({"baseRef": protection()}, nodes(BUILD), None),
        ({"baseRef": protection(requiresCommitSignatures=True)}, EMPTY, "protection"),
        ({"baseRef": protection(requiresDeployments=True)}, EMPTY, "protection"),
        ({"baseRef": protection(lockBranch=None)}, EMPTY, "protection"),
        ({"baseRef": protection(requiresStrictStatusChecks=True)}, EMPTY, "protection"),
        ({"baseRef": ruleset("PULL_REQUEST", "DELETION")}, EMPTY, None),
        ({"baseRef": ruleset("CODE_SCANNING")}, EMPTY, "CODE_SCANNING"),
        ({"baseRef": ruleset("MERGE_QUEUE")}, EMPTY, "MERGE_QUEUE"),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["build"])},
            nodes(BUILD),
            None,
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["security"])},
            nodes(BUILD),
            "required check has not passed: security",
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["build"])},
            nodes({"name": "build", "conclusion": "SKIPPED"}),
            None,
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["ci/legacy"])},
            nodes({"context": "ci/legacy", "state": "SUCCESS"}),
            None,
        ),
        (
            {"baseRef": protection(requiredStatusCheckContexts=["build"])},
            {"totalCount": 2, "nodes": [BUILD]},
            "required check",
        ),
        ({"baseRef": required_rule("build")}, nodes(BUILD), None),
        ({"baseRef": required_rule("security")}, nodes(BUILD), "security"),
        ({"baseRef": required_rule("build", True)}, nodes(BUILD), "up to date"),
        ({"baseRef": required_rule("build", None)}, nodes(BUILD), "up to date"),
    ],
)
def test_bypass_needs_every_other_merge_requirement_satisfied(
    pull: dict[str, JsonValue], contexts: JsonValue, message: str | None
) -> None:
    review: dict[str, JsonValue] = {
        "isMergeQueueEnabled": False,
        "reviewThreads": EMPTY,
        "baseRef": {"branchProtectionRule": None, "rules": EMPTY},
    }
    problem = shipping._other_merge_requirement(
        review | pull, {"state": "SUCCESS", "contexts": contexts}
    )
    if message is None:
        assert problem is None
    else:
        assert problem is not None and message in problem
