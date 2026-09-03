#!/usr/bin/env python3
"""External claim check: every vendor tool the brief or manifest relies on must have a cited research source."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"), str(SCRIPT_DIR)]

from bounded_run import run_captured
from evidence_lib import EvidenceError, enforcement_configured, load_receipt, plan_id, utc_now
from git_env import git_env
from plan_sections import PlanError, parse_sections

VENDOR_TOOLS: dict[str, tuple[str, ...]] = {
    "fallow": ("fallow",),
    "jscpd": ("jscpd",),
    "stryker": ("stryker",),
    "mutmut": ("mutmut",),
    "react-doctor": ("react-doctor",),
    "dart-decimate": ("decimate",),
    "biome": ("biomejs", "biome"),
    "ruff": ("ruff",),
    "pyright": ("pyright",),
    "gitleaks": ("gitleaks",),
    "tsc": ("typescriptlang", "typescript"),
    "playwright": ("playwright",),
    "jira": ("atlassian", "jira"),
    "azure devops": ("dev.azure", "azure"),
    "gh": ("cli.github", "gh"),
}
BACKTICKED = re.compile(r"`([^`]+)`")
MANIFEST = "hard-eng.gates.json"


class ExternalClaimError(Exception):
    """The brief or manifest relies on an uncited vendor tool."""


def _tools_in(text: str) -> list[str]:
    words = set(re.findall(r"[a-z0-9.-]+", text.lower()))
    return [tool for tool in VENDOR_TOOLS if all(part in words for part in tool.split())]


def named_tools(text: str) -> list[str]:
    seen: list[str] = []
    for span in BACKTICKED.findall(text):
        seen.extend(tool for tool in _tools_in(span) if tool not in seen)
    return seen


def brief_claims(repo: Path, plan: Path) -> list[tuple[str, str]]:
    try:
        section = parse_sections(plan.read_text(encoding="utf-8"))["Material decisions"]
    except (OSError, PlanError):
        return []
    claims = [(tool, "Material decisions") for tool in named_tools(section)]
    study = _code_study_contract(repo, plan)
    claims += [(tool, "code-study external_contract") for tool in _tools_in(study) if tool not in dict(claims)]
    return claims


def _code_study_contract(repo: Path, plan: Path) -> str:
    try:
        value, _, _ = load_receipt(repo, plan, "plan-steps.json")
    except EvidenceError:
        return ""
    steps = value.get("steps")
    study = steps.get("code-study") if isinstance(steps, dict) else None
    answers = study.get("answers") if isinstance(study, dict) else None
    contract = answers.get("external_contract") if isinstance(answers, dict) else None
    return contract if isinstance(contract, str) else ""


def _rows(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _hint_matches(hint: str, words: set[str]) -> bool:
    return all(part in words for part in re.findall(r"[a-z0-9]+", hint))


def cited_tools(repo: Path, plan: Path) -> set[str]:
    try:
        value, _, _ = load_receipt(repo, plan, "research.json")
    except EvidenceError:
        return set()
    if value.get("plan_id") != plan_id(plan):
        return set()
    try:
        if utc_now().date() > date.fromisoformat(str(value.get("fresh_until"))):
            return set()
    except ValueError:
        return set()
    sources = _rows(value.get("sources"))
    versions = _rows(value.get("source_versions"))
    cited: set[str] = set()
    for source, version in zip(sources, versions, strict=False):
        if not isinstance(source, str) or not source.startswith("https://"):
            continue
        if not isinstance(version, str) or not version.strip():
            continue
        words = set(re.findall(r"[a-z0-9]+", source.lower()))
        cited.update(tool for tool, hints in VENDOR_TOOLS.items() if any(_hint_matches(hint, words) for hint in hints))
    return cited


def claim_error(repo: Path, plan: Path) -> str | None:
    if not enforcement_configured(repo):
        return None
    cited = cited_tools(repo, plan)
    for tool, where in brief_claims(repo, plan):
        if tool not in cited:
            return (
                f"external claim `{tool}` in {where} has no research source row "
                "(https url + version in this plan's research.json); record it with execution_evidence.py record-research"
            )
    return None


def _manifest_tools(text: str) -> set[str]:
    try:
        data = json.loads(text)
    except ValueError:
        return set()
    families = data.get("families") if isinstance(data, dict) else None
    found: set[str] = set()
    for command in (families or {}).values():
        if isinstance(command, list):
            found.update(_tools_in(" ".join(Path(str(item)).name for item in command[:3])))
    return found


def manifest_claim_error(repo: Path, plan: Path) -> str | None:
    if not enforcement_configured(repo):
        return None
    current = (repo / MANIFEST).read_text(encoding="utf-8") if (repo / MANIFEST).is_file() else ""
    result = run_captured(["git", "show", f"HEAD:{MANIFEST}"], 30, cwd=str(repo), env=git_env())
    previous = result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else ""
    introduced = sorted(_manifest_tools(current) - _manifest_tools(previous))
    cited = cited_tools(repo, plan) if introduced else set()
    for tool in introduced:
        if tool not in cited:
            return (
                f"{MANIFEST} introduces `{tool}` without a research source row "
                "(https url + version in this plan's research.json); record it with execution_evidence.py record-research"
            )
    return None
