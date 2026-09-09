#!/usr/bin/env python3
"""Tracker mirror contract shared by GitHub, Jira Cloud, and Azure DevOps: config, epic receipt, self-contained bodies."""

from __future__ import annotations

import importlib
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import plan_handoff
import plan_sections
import tracker_probe
from evidence_lib import EvidenceError, safe_receipt_json, utc_now, utc_text

ADAPTERS = tracker_probe.ADAPTERS
EPIC_RECEIPT = "tracker.json"
KINDS = ("epic", "story", "task")
ISSUE_NUMBER = re.compile(r"/issues/(\d+)$|^#?(\d+)$")


class TrackerError(RuntimeError):
    pass


def read_config(repo: Path) -> dict[str, str] | None:
    gates_path = repo / "hard-eng.gates.json"
    if not gates_path.is_file() or gates_path.is_symlink():
        return None
    try:
        data = json.loads(gates_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    tracker = data.get("tracker") if isinstance(data, dict) else None
    if not isinstance(tracker, dict) or tracker.get("adapter") not in ADAPTERS:
        return None
    config = {"adapter": str(tracker["adapter"])}
    for key in ("repository", "project"):
        value = tracker.get(key)
        if isinstance(value, str) and value:
            config[key] = value
    if config["adapter"] == "github" and "/" not in config.get("repository", ""):
        return None
    return config


def adapter_module(name: str) -> ModuleType | None:
    try:
        return importlib.import_module(f"tracker_{name}")
    except ImportError:
        return None


def select(repo: Path) -> tuple[dict[str, str], ModuleType, dict[str, str]] | None:
    config = read_config(repo)
    if config is None:
        return None
    module = adapter_module(config["adapter"])
    if module is None:
        return None
    credentials = tracker_probe.credentials(repo)
    if config["adapter"] == "github" and "repository" not in config and credentials.get("GITHUB_REPOSITORY"):
        config["repository"] = credentials["GITHUB_REPOSITORY"]
    if not module.available(config, credentials):
        return None
    return config, module, credentials


def issue_number(ref: str) -> str | None:
    match = ISSUE_NUMBER.search(ref.strip())
    if match is None:
        return None
    return match.group(1) or match.group(2)


def epic_receipt_path(epic_plan: Path) -> Path:
    return epic_plan.parent / "receipts" / EPIC_RECEIPT


def read_epic_ref(epic_plan: Path, adapter: str) -> str | None:
    path = epic_receipt_path(epic_plan)
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("adapter") != adapter:
        return None
    ref = value.get("epic_ref")
    return ref if isinstance(ref, str) and ref else None


def write_epic_ref(repo: Path, epic_plan: Path, adapter: str, ref: str, children: list[str] | None = None) -> None:
    path = epic_receipt_path(epic_plan)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    payload = {
        "schema_version": 1,
        "adapter": adapter,
        "epic_ref": ref,
        "children": children or [],
        "created_at": utc_text(utc_now()),
    }
    try:
        safe_receipt_json(repo, path, payload)
    except EvidenceError as error:
        raise TrackerError(str(error)) from error


def brief_sections(epic_plan: Path) -> dict[str, str]:
    return plan_sections.parse_sections(epic_plan.read_text(encoding="utf-8"))


def acceptance_lines(sections: Mapping[str, str]) -> list[str]:
    return [line[2:].strip() for line in sections.get("Acceptance examples", "").splitlines() if line.startswith("- ")]


def epic_title(epic_plan: Path) -> str:
    return f"Epic: {epic_plan.parent.name}"


def epic_body(epic_plan: Path) -> str:
    sections = brief_sections(epic_plan)
    slices = sections.get("Vertical slices", "")
    return "\n".join(
        [
            "## Outcome",
            sections.get("Outcome", ""),
            "",
            "## Non-goals",
            sections.get("Non-goals", ""),
            "",
            "## Acceptance examples",
            "\n".join(f"- A-{index} = {text}" for index, text in enumerate(acceptance_lines(sections), start=1)),
            "",
            "## Vertical slices",
            slices,
            "",
            f"Source of truth: `{epic_plan.parent.name}/PLAN.md` in the repository; this item mirrors it.",
        ]
    )


def _items(ticket: Mapping[str, object], key: str) -> list[str]:
    value = ticket.get(key, ())
    if isinstance(value, str):
        return [] if value == "none" else [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item) != "none"]
    return []


def ticket_title(ticket: Mapping[str, object]) -> str:
    goal = str(ticket.get("goal_text", "")).strip().splitlines()
    summary = goal[0].lstrip("- ").strip() if goal else "work"
    return f"{ticket['ticket_id']}: {summary[:80]}"


def ticket_body(
    repo: Path, epic_plan: Path, ticket: Mapping[str, object], siblings: Mapping[str, Mapping[str, object]]
) -> str:
    sections = brief_sections(epic_plan)
    acceptance = acceptance_lines(sections)
    depends = _items(ticket, "depends_on")
    covers = _items(ticket, "covers")
    touches = _items(ticket, "touches")
    relative_plan = epic_plan.relative_to(repo)
    dependency_rows = [
        f"- {dependency}: {str(siblings.get(dependency, {}).get('goal_text', 'see ticket')).strip().splitlines()[0]}"
        for dependency in depends
    ] or ["- none; this ticket can start now"]
    covered_rows = []
    for ordinal in covers:
        index = int(ordinal.split("-", 1)[1]) - 1 if ordinal.startswith("A-") else -1
        text = acceptance[index] if 0 <= index < len(acceptance) else "see PLAN.md"
        covered_rows.append(f"- {ordinal}: {text}")
    return "\n".join(
        [
            "## Goal",
            str(ticket.get("goal_text", "")).strip(),
            "",
            "## Why",
            sections.get("Outcome", "").strip(),
            "",
            "## Depends on",
            *dependency_rows,
            "",
            "## Slices",
            "- " + ", ".join(_items(ticket, "slices")),
            "",
            "## Files this ticket may touch",
            *([f"- `{path}`" for path in touches] or ["- decided during build; record in the ticket file"]),
            "",
            "## Acceptance covered",
            *(covered_rows or ["- none listed"]),
            "",
            "## Definition of done",
            "- every listed slice demonstrably works end to end",
            "- ticket-scoped full gate green + code review of the ticket diff",
            "- pull request merged to the default branch; ticket status shipped",
            "",
            "## Proof",
            str(ticket.get("acceptance_text", "")).strip(),
            "",
            "## Start here",
            plan_handoff.ticket_prompt(repo, relative_plan, str(ticket["ticket_id"])),
            "",
            f"Source of truth: `{relative_plan.parent}/tickets/{ticket['ticket_id']}.md`; this item mirrors it.",
        ]
    )


def ensure_epic(repo: Path, epic_plan: Path, config: dict[str, str], module: ModuleType, creds: dict[str, str]) -> str:
    existing = read_epic_ref(epic_plan, config["adapter"])
    if existing is not None:
        return existing
    ref = module.create_ticket(
        config,
        creds,
        ticket_id="epic",
        title=epic_title(epic_plan),
        body=epic_body(epic_plan),
        kind="epic",
        parent=None,
        blocked_by=(),
    )
    if not isinstance(ref, str) or not ref:
        raise TrackerError("epic creation returned no reference")
    write_epic_ref(repo, epic_plan, config["adapter"], ref)
    return ref
