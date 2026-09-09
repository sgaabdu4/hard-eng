#!/usr/bin/env python3
"""Reviewer packet: the slice row, brief outcome, decisions, acceptance examples, edge list, and the diff, nothing else."""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"))

from bounded_run import run_captured
from git_env import git_env
from plan_sections import PlanError, parse_sections
from safe_plan_io import lifecycle_excluded

PACKET_SECTIONS = ("Outcome", "Material decisions", "Acceptance examples")


class ReviewPacketError(Exception):
    """The packet cannot be built from the current brief and tree."""


VERIFIER_RULES = (
    "- You did not write this code; drive the whole feature from the outside.",
    "- Every outside host must go through a fake you control; list every host reached in outside_calls.",
    "- Every fake log line starts with the host reached; a host outside the fakes list fails the record.",
    "- One real outside call means FAIL.",
    "- mode ui = screenshots before and after per view (png/jpg/webp); mode logic = recorded inputs and outputs as JSON.",
    "- Evidence files live under features/<slug>/receipts/ and are listed with their sha256.",
    "- Edit no product file; report defects, do not patch them.",
    "- Delete, overwrite, or truncate nothing your own run log did not prove you created; a pre-existing or ignored directory under the checkout is someone else's work.",
)


def packet_path(plan: Path, name: str, round_number: int) -> Path:
    return plan.parent / "receipts" / f"{name}-review-{round_number}.txt"


def verify_packet_path(plan: Path, name: str) -> Path:
    return plan.parent / "receipts" / f"{name}-verify.txt"


def _git(repo: Path, *args: str) -> bytes:
    result = run_captured(["git", *args], 60, cwd=str(repo), env=git_env())
    if result.returncode != 0:
        raise ReviewPacketError(result.stderr.decode(errors="replace").strip() or "git failed")
    return result.stdout


def _has_head(repo: Path) -> bool:
    return run_captured(["git", "rev-parse", "--verify", "HEAD"], 60, cwd=str(repo), env=git_env()).returncode == 0


def diff_text(repo: Path) -> str:
    parts: list[str] = []
    if _has_head(repo):
        parts.append(_git(repo, "diff", "HEAD", "--").decode("utf-8", errors="replace"))
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for raw in sorted(filter(None, untracked)):
        relative = Path(os.fsdecode(raw))
        if lifecycle_excluded(relative):
            continue
        body = (repo / relative).read_text(encoding="utf-8", errors="replace")
        parts.append(f"diff --git a/{relative} b/{relative}\nnew file\n--- /dev/null\n+++ b/{relative}\n")
        parts.append("".join(f"+{line}\n" for line in body.splitlines()))
    return "".join(parts)


def slice_row(sections: dict[str, str], name: str) -> str:
    for line in sections["Vertical slices"].splitlines():
        if line.startswith(f"- {name} = "):
            return line[2:]
    raise ReviewPacketError(f"{name} has no row in Vertical slices")


def edge_lines(edges: dict[str, object] | None) -> list[str]:
    cases = edges.get("cases") if isinstance(edges, dict) else None
    if not isinstance(cases, list) or not cases:
        raise ReviewPacketError("record the edges step before building the review packet")
    return [
        f"- {item['name']} (success: {item['success_test']}; failure: {item['failure_test']})"
        for item in cases
        if isinstance(item, dict)
    ]


def build(repo: Path, plan: Path, name: str, edges: dict[str, object] | None) -> str:
    try:
        sections = parse_sections(plan.read_text(encoding="utf-8"))
    except PlanError as error:
        raise ReviewPacketError(str(error)) from error
    diff = diff_text(repo)
    if not diff.strip():
        raise ReviewPacketError("the tree has no changes to review")
    scope = "whole feature" if name == "full" else slice_row(sections, name)
    edges_block = edge_lines(edges) if name != "full" else ["- every slice edge list applies"]
    lines = [f"# Review packet: {name}", "", "## Slice", scope, ""]
    for heading in PACKET_SECTIONS:
        lines += [f"## {heading}", sections[heading], ""]
    lines += ["## Edge list", *edges_block, "", "## Diff", "```diff", diff.rstrip("\n"), "```", ""]
    return "\n".join(lines)


def build_verify(plan: Path, name: str, edges: dict[str, object] | None) -> str:
    try:
        sections = parse_sections(plan.read_text(encoding="utf-8"))
    except PlanError as error:
        raise ReviewPacketError(str(error)) from error
    scope = "whole feature" if name == "full" else slice_row(sections, name)
    edges_block = edge_lines(edges) if name != "full" else ["- every slice edge list applies"]
    lines = [f"# Verifier packet: {name}", "", "## Scope", scope, ""]
    for heading in PACKET_SECTIONS:
        lines += [f"## {heading}", sections[heading], ""]
    lines += ["## Edge list", *edges_block, "", "## Rules", *VERIFIER_RULES, ""]
    lines += ["## Evidence directory", str(plan.parent / "receipts"), ""]
    return "\n".join(lines)


def write_verify(repo: Path, plan: Path, name: str, edges: dict[str, object] | None) -> tuple[Path, str]:
    target = verify_packet_path(plan, name)
    target.parent.mkdir(mode=0o700, exist_ok=True)
    text = build_verify(plan, name, edges)
    target.write_text(text, encoding="utf-8")
    return target, hashlib.sha256(text.encode("utf-8")).hexdigest()


def write(repo: Path, plan: Path, name: str, round_number: int, edges: dict[str, object] | None) -> tuple[Path, str]:
    target = packet_path(plan, name, round_number)
    target.parent.mkdir(mode=0o700, exist_ok=True)
    text = build(repo, plan, name, edges)
    target.write_text(text, encoding="utf-8")
    return target, hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()
