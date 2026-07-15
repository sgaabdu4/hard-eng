"""Focused approval-content regressions for the Hard Eng state contract."""
from __future__ import annotations


def bind_approved(module, text: str) -> str:
    state = module.parse_state(text)
    if state["plan_approved"] != "yes":
        return text
    return text.replace(
        f"- approved_plan_digest = {state['approved_plan_digest']}",
        f"- approved_plan_digest = {module.approved_plan_digest(text)}",
    )


def check_approved_content_lock(module, path, approved: str, expect_error) -> None:
    changed = approved.replace("Fixture.", "Changed after approval.")
    expect_error(
        module,
        lambda: module.validate_document(path, changed),
        "approved plan content rewrite",
    )
