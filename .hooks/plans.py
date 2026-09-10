"""Check plan declarations; evidence truth and authorization still need review."""

import re
from pathlib import Path

from gate_config import changed_files, repository_files

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


def field(content: str, name: str) -> str:
    values = re.findall(rf"(?m)^{re.escape(name)}: *(.*)$", content)
    if len(values) != 1 or not values[0].strip():
        raise ValueError(f"plan needs one filled '{name}:' field")
    return values[0].strip()


def proof(content: str, allowed: set[str]) -> None:
    result = field(content, "Result")
    if result not in allowed:
        raise ValueError(f"plan Result {result!r} must be one of {sorted(allowed)}")
    required = (
        ("Evidence", "Authorization", "Impact")
        if result == "Exception"
        else ("Evidence",)
    )
    for name in required:
        if re.match(r"(?i)^(?:pending|none|blocked|n/a)\b", field(content, name)):
            raise ValueError(
                f"plan {name} must describe actual proof, not a pending result"
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
    proof(baseline, {"Passed", "Exception"})
    if not re.fullmatch(r"N/A — [^\n]+", ux.strip()):
        proof(ux, {"Passed"})
    if status == "Complete":
        markers = re.findall(
            r"(?m)^\s*(?:[-*+]|\d+[.)])\s+\[([^]\n]*)\](?:\s|$)", content
        )
        if any(marker.lower() != "x" for marker in markers):
            raise ValueError("complete plan has unchecked requirements")
        proof(verification, {"Passed"})
    return status


def validate_plans(
    root: Path, base: str | None = None, stage: str | None = None
) -> None:
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
        path
        for path in repository_files(root)
        if path.name.lower() == "plan.md"
        and (path.parent == root or path.relative_to(root).parts[0] == "features")
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
    for path in applicable:
        try:
            status = validate_plan(path)
            if STAGES.index(status) < STAGES.index(stage):
                raise ValueError(f"plan is {status}; this check requires {stage}")
        except ValueError as error:
            raise ValueError(f"{path.relative_to(root)}: {error}") from error
