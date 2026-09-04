#!/usr/bin/env python3
"""Generated BUILD.md: one human-readable summary of every slice's build records for review."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_steps
from plan_sections import parse_sections, parse_slices

REPORT_NAME = "BUILD.md"


def _receipt(plan: Path, name: str) -> dict[str, object]:
    path = plan.parent / "receipts" / f"{name}.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _findings(review: object) -> list[str]:
    lines: list[str] = []
    for raw in _list(_dict(review).get("rounds")):
        entry = _dict(raw)
        if not entry:
            continue
        summary = (
            ", ".join(
                f"{item.get('id')} {item.get('status')}"
                for item in _list(entry.get("findings"))
                if isinstance(item, dict)
            )
            or "no findings"
        )
        lines.append(f"  - round {entry.get('round')}: {summary}")
    return lines


def _paths(rows: object) -> str:
    if not isinstance(rows, list):
        return "none"
    return ", ".join(f"`{item.get('path')}`" for item in rows if isinstance(item, dict)) or "none"


def slice_lines(plan: Path, name: str, entry: dict[str, object]) -> list[str]:
    gate = _receipt(plan, name)
    edges, green, verify = _dict(entry.get("edges")), _dict(entry.get("green")), _dict(entry.get("verify"))
    cases = _list(edges.get("cases"))
    lines = [f"## {name}", f"- behavior = {gate.get('behavior', 'not gated')}"]
    lines.append(f"- edge cases = {len(cases)}")
    lines.extend(f"  - {item.get('name')}" for item in cases if isinstance(item, dict))
    command = _list(green.get("command"))
    lines.append(f"- green = `{' '.join(str(item) for item in command)}`" if command else "- green = not recorded")
    lines.append("- review =")
    lines.extend(_findings(entry.get("review")) or ["  - not recorded"])
    if verify:
        lines.append(
            f"- verify = {verify.get('mode')} mode; before {_paths(verify.get('before'))}; after {_paths(verify.get('after'))}"
        )
        hosts = ", ".join(str(item) for item in _list(verify.get("outside_calls")))
        lines.append(f"- outside calls = {hosts or 'none'} (all faked)")
    else:
        lines.append("- verify = not recorded")
    lines.append(f"- gate families = {_families(gate) or 'none'}")
    return lines


def _families(gate: dict[str, object]) -> str:
    return ", ".join(str(item.get("family")) for item in _list(gate.get("checks")) if isinstance(item, dict))


def render(repo: Path, plan: Path) -> str:
    text = plan.read_text(encoding="utf-8")
    sections = parse_sections(text)
    receipt = build_steps.load(repo, plan)
    slices = receipt["slices"]
    assert isinstance(slices, dict)
    lines = [
        f"# Build record: {plan.parent.name}",
        "",
        "Generated from the build receipts; edit the receipts, not this file.",
        "",
    ]
    lines += ["## Outcome", sections["Outcome"], ""]
    for name in parse_slices(sections["Vertical slices"]):
        entry = slices.get(name)
        lines += slice_lines(plan, name, entry if isinstance(entry, dict) else {})
        lines.append("")
    full_verify = _dict(_dict(slices.get(build_steps.FULL)).get("verify"))
    lines += ["## Whole feature"]
    if full_verify:
        lines.append(
            f"- verify = {full_verify.get('mode')} mode; before {_paths(full_verify.get('before'))}; after {_paths(full_verify.get('after'))}"
        )
    else:
        lines.append("- verify = not recorded")
    lines.append("- full gate = " + (_families(_receipt(plan, "full")) or "not run"))
    return "\n".join(lines) + "\n"


def write(repo: Path, plan: Path) -> Path:
    target = plan.parent / REPORT_NAME
    target.write_text(render(repo, plan), encoding="utf-8")
    return target


def walkthrough_video(repo: Path, plan: Path) -> str | None:
    slices = build_steps.load(repo, plan)["slices"]
    assert isinstance(slices, dict)
    rows = _list(_dict(_dict(slices.get(build_steps.FULL)).get("verify")).get("after"))
    for item in rows:
        if isinstance(item, dict) and Path(str(item.get("path"))).suffix.lower() in build_steps.VIDEO_SUFFIXES:
            return str(item.get("path"))
    return None


def closing_error(repo: Path, plan: Path, state: dict[str, str]) -> str | None:
    answer = state.get("walkthrough", "pending")
    if answer == "pending":
        return "green requires the closing answer: checkpoint --set walkthrough=yes|no (walkthrough video?)"
    if answer == "yes" and walkthrough_video(repo, plan) is None:
        return "walkthrough=yes requires a video (mp4/webm/mov) in the full verify record's after list"
    return None
