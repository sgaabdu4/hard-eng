"""Check plan declarations; evidence truth and authorization still need review."""

import re
from pathlib import Path

from gate_config import changed_files, repository_files
from shipping import load_policy

SECTIONS = (
    "Outcome + scope",
    "Repository context",
    "Decisions + authorization",
    "Acceptance + steps",
    "Baseline + execution",
    "Risks + recovery",
    "ux_reference",
    "Verification",
)
STAGES = ("Draft", "Ready", "Complete")


def is_plan_path(path: Path) -> bool:
    return path.name.lower() == "plan.md" and (
        path.parent == Path(".") or path.parts[0] == "features"
    )


def report_stage(failed: bool, stage: str | None) -> None:
    if failed:
        print("Hard Eng: verification failed; the next stage is blocked.")
    elif stage == "Ready":
        print(
            "Hard Eng: planning checks passed — ready for build within the authorized scope."
        )
    elif stage == "Complete":
        print(
            "Hard Eng: build checks passed — ready for ship; remote delivery is not verified by this check."
        )


def field(content: str, name: str) -> str:
    values = re.findall(rf"(?m)^{re.escape(name)}: *(.*)$", content)
    if len(values) != 1 or not values[0].strip():
        raise ValueError(f"plan needs one filled '{name}:' field")
    return values[0].strip()


def proof(content: str, allowed: set[str]) -> None:
    result = field(content, "Result")
    if result not in allowed:
        raise ValueError(f"plan Result {result!r} must be one of {sorted(allowed)}")
    if re.match(r"(?i)^(?:pending|none|blocked|n/a)\b", field(content, "Evidence")):
        raise ValueError(
            "plan Evidence must describe actual proof, not a pending result"
        )


def plan_sections(content: str) -> dict[str, str]:
    if re.search(
        r"(?im)\[TODO:|^\s*(?:#\s+|[\w +]+:\s*)?(?:TODO(?::[^\n]*)?|TBD|<(?!https?://)[^>\n]+>)\s*$",
        content,
    ):
        raise ValueError("plan contains unfilled template placeholders")
    if not re.search(r"(?m)^# \S.+$", content):
        raise ValueError("plan needs a title")
    parts = re.split(r"(?m)^## +([^\n]+)\n", content + "\n")
    headings = [heading.strip() for heading in parts[1::2]]
    sections = dict(zip(headings, parts[2::2]))
    for heading in SECTIONS:
        if headings.count(heading) != 1 or not sections[heading].strip():
            raise ValueError(f"plan needs one filled '## {heading}' section")
    for line in content.splitlines():
        for marker in re.finditer(r"(?i)\bN/A\b", line):
            if not re.match(r"\s+—\s+\S", line[marker.end() :]):
                raise ValueError("plan N/A needs an inline reason: N/A — reason")
    return sections


def e2e_proof(verification: str, status: str) -> None:
    e2e = field(verification, "E2E")
    match = re.fullmatch(r"(Required|Passed|Delivery|N/A) — (\S.*)", e2e)
    if match is None:
        raise ValueError(
            "plan E2E needs Required, Passed, Delivery or N/A — concrete journey/evidence or reason"
        )
    if status == "Complete" and match[1] == "Required":
        raise ValueError(
            "complete plan E2E is still Required; run the journey and record Passed evidence"
        )
    if match[1] == "Passed" and re.match(
        r"(?i)^(pending|none|blocked|n/a)\b", match[2]
    ):
        raise ValueError("plan E2E Passed needs actual runtime evidence")
    if match[1] == "Delivery" and not re.search(
        r"(?im)^\s*(?:[-*+]\s+)?Delivery target:\s*Deploy\s*$", verification
    ):
        raise ValueError(
            "delivery E2E requires Delivery target: Deploy and configured delivery checks"
        )


def validate_plan(path: Path) -> str:
    content = path.read_text()
    sections = plan_sections(content)
    status = field(content, "Status")
    if status not in STAGES:
        raise ValueError("plan Status must be Draft, Ready or Complete")
    baseline = sections["Baseline + execution"]
    ux = sections["ux_reference"]
    verification = sections["Verification"]
    if status == "Draft":
        return status
    if field(sections["Decisions + authorization"], "Blockers") != "None":
        raise ValueError("ready/complete plan has unresolved Blockers")
    proof(baseline, {"Passed"})
    e2e_proof(verification, status)
    if not re.fullmatch(r"N/A — [^\n]+", ux.strip()):
        proof(ux, {"Passed"})
        if not re.search(r"!\[[^\]\n]*\]\(\S[^)\n]*\)", ux):
            raise ValueError(
                "UX evidence needs a Markdown image reference to the rendered proposal; "
                "show and inspect it in the conversation before Ready"
            )
    if status == "Complete":
        markers = re.findall(
            r"(?m)^\s*(?:[-*+]|\d+[.)])\s+\[([^]\n]*)\](?:\s|$)", content
        )
        if any(marker.lower() != "x" for marker in markers):
            raise ValueError("complete plan has unchecked requirements")
        proof(verification, {"Passed"})
    return status


def _validate_shipping(root: Path, path: Path, status: str) -> None:
    content = path.read_text()
    if status in {"Ready", "Complete"} and re.search(
        r"(?im)^\s*(?:[-*+]\s+)?Delivery target:", content
    ):
        policy = load_policy(root)
        if (
            policy is not None
            and not policy["delivery"]
            and re.search(
                r"(?im)^\s*(?:[-*+]\s+)?Delivery target:\s*Deploy\s*$",
                plan_sections(content)["Verification"],
            )
        ):
            raise ValueError("Deploy target requires configured delivery checks")


def validate_plans(
    root: Path, base: str | None = None, stage: str | None = None
) -> str:
    explicit_stage = stage is not None
    changed = changed_files(root, base or "HEAD")
    if changed is None:
        raise ValueError("Cannot verify plan scope; fetch or supply a valid Git --base")
    if stage is None:
        stage = (
            "Complete"
            if any(Path(name).suffix.lower() != ".md" for name in changed)
            else "Draft"
        )
    paths = [
        path for path in repository_files(root) if is_plan_path(path.relative_to(root))
    ]
    applicable = [path for path in paths if str(path.relative_to(root)) in changed]
    if not applicable:
        applicable = [
            path for path in paths if field(path.read_text(), "Status") != "Complete"
        ]
    if not applicable and explicit_stage:
        applicable = paths
    if (changed != set() or explicit_stage) and not applicable:
        raise ValueError(
            "repository changes need an applicable PLAN.md; use the HE Plan template"
        )
    effective_stage = "Complete"
    for path in applicable:
        try:
            status = validate_plan(path)
            _validate_shipping(root, path, status)
            if STAGES.index(status) < STAGES.index(stage):
                raise ValueError(f"plan is {status}; this check requires {stage}")
            effective_stage = min(effective_stage, status, key=STAGES.index)
        except ValueError as error:
            raise ValueError(f"{path.relative_to(root)}: {error}") from error
    return stage if explicit_stage or not applicable else effective_stage
