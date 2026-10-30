"""Say why React Doctor reports a project as incomplete."""

from gate_config import JsonObject

DETAIL_LIMIT = 2000


def incomplete_reason(project: JsonObject) -> str:
    skipped = project.get("skippedChecks")
    reasons = project.get("skippedCheckReasons")
    notes = reasons if isinstance(reasons, dict) else {}
    names = dict.fromkeys(
        str(name) for name in [*(skipped if isinstance(skipped, list) else []), *notes]
    )
    details = [
        f"{name} skipped: {str(notes.get(name, 'no reason reported'))[:DETAIL_LIMIT]}"
        for name in names
    ]
    diagnostics = project.get("diagnostics")
    if isinstance(diagnostics, list) and diagnostics:
        details.append(f"{len(diagnostics)} diagnostics")
    if not details:
        details.append("the project scan did not complete")
    return "React Doctor reports incomplete checks or diagnostics: " + "; ".join(
        details
    )
