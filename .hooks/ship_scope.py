"""The plan and the delivery target that a shipment is judged against."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from gate_config import JsonValue
from shipping import (
    Delivery,
    ShippingError,
    ShippingPolicy,
    _pull,
    _PullRequest,
    load_policy,
)

DELIVERY_TARGET_LINE = re.compile(
    r"(?im)^\s*(?:[-*+]\s+)?Delivery target:\s*(PR|Merge|Deploy)\s*$"
)
ONE_TARGET = (
    "Verification needs one Delivery target: PR, Merge or Deploy, alone on its line"
)


def plan_target(root: Path, plan: Path) -> tuple[Path, str]:
    resolved_root = root.resolve()
    resolved_plan = plan.resolve()
    if not resolved_plan.is_relative_to(resolved_root):
        raise ShippingError("shipping plan must be inside the repository")
    if not resolved_plan.is_file():
        raise ShippingError(
            "shipping plan not found in this checkout; check out the PR's head branch"
        )
    try:
        from plans import plan_sections, validate_plan

        if validate_plan(resolved_plan) != "Complete":
            raise ShippingError("shipping requires a Complete plan")
        from plan_controls import plan_root, tracked_problem

        if problem := tracked_problem(
            resolved_plan.read_text(), plan_root(resolved_plan)
        ):
            raise ShippingError(problem)
        sections = plan_sections(resolved_plan.read_text())
    except ShippingError:
        raise
    except (OSError, UnicodeError, ValueError) as error:
        raise ShippingError(
            "shipping plan failed native Complete validation"
        ) from error
    targets = DELIVERY_TARGET_LINE.findall(sections["Verification"])
    if len(targets) != 1:
        raise ShippingError(ONE_TARGET)
    return resolved_plan, targets[0]


def target_problem(target: str, delivery: list[Delivery]) -> str | None:
    if target.lower() == "deploy" and not delivery:
        return "Deploy target requires configured delivery checks"
    if target.lower() == "merge" and delivery:
        return "configured delivery checks need Delivery target: Deploy"
    return None


def plan_target_problem(root: Path, verification: str) -> str | None:
    """Why the delivery target in a plan's Verification does not fit the shipping policy."""
    targets = DELIVERY_TARGET_LINE.findall(verification)
    if len(targets) != 1:
        return ONE_TARGET
    policy = load_policy(root)
    return None if policy is None else target_problem(targets[0], policy["delivery"])


def delivery_scope(
    root: Path, plan: Path | None, delivery: list[Delivery]
) -> tuple[Path | None, str]:
    if plan is not None:
        return plan_target(root, plan)
    from change_size import size_verdict

    small, reason = size_verdict(root)
    if not small:
        raise ShippingError(f"a big change needs a plan: {reason}")
    return None, "Deploy" if delivery else "Merge"


def plan_scope(
    root: Path,
    plan: Path | None,
    policy: ShippingPolicy,
    identity: tuple[str, str, int],
) -> tuple[Path | None, str]:
    """The plan and delivery target; a release, hotfix or join needs no plan even when the branch is big."""
    from ship_record import route

    try:
        return delivery_scope(root, plan, policy["delivery"])
    except ShippingError:
        found = route(root, _pull(root, *identity), policy["base"])
        if plan is not None or found not in ("release", "join"):
            raise
        return None, "Deploy" if policy["delivery"] else "Merge"


def plan_in(files: list[dict[str, JsonValue]]) -> str | None:
    """The first plan that the PR adds or changes; a change that needed a plan changes one."""
    from plans import is_plan_path

    for item in files:
        name = cast(str, item["filename"])
        if item.get("status") != "removed" and is_plan_path(Path(name)):
            return name
    return None


def delivered_files(
    root: Path,
    pull: _PullRequest,
    identity: tuple[str, str, int],
    policy: ShippingPolicy,
    plan: Path | None,
    stage: str,
) -> list[dict[str, JsonValue]]:
    """The files of the PR when screens need them or the delivered stage has no plan; a delivered stage with no `--plan` for an ordinary PR that changed a plan is refused."""
    from ship_record import route
    from ui_proof import changed_files

    unplanned = (
        stage == "delivered"
        and plan is None
        and route(root, pull, policy["base"]) is None
    )
    if not (policy["ui_paths"] or unplanned):
        return []
    files = changed_files(root, *identity)
    if unplanned and (named := plan_in(files)):
        raise ShippingError(
            f"--plan is missing: this PR changed {named}; pass --plan {named}"
        )
    return files
