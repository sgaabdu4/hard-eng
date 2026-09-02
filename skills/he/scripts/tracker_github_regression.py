#!/usr/bin/env python3
"""Regression: decompose mirrors the epic, stories, blockers, and self-contained bodies through a fake gh."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import ticket_state_regression as fixture

BODY_ANCHORS = (
    "## Goal",
    "## Why",
    "## Depends on",
    "- T-1:",
    "## Files this ticket may touch",
    "## Acceptance covered",
    "## Definition of done",
    "## Start here",
    "ticket_state.py claim",
    "Source of truth",
)


def check_hierarchy(base: Path) -> None:
    repo, plan = fixture.setup_epic(base, "gh-mirror", "ghmirror", fixture.behaves("S-1", "S-2", "S-3"), tracker=True)
    log_path = fixture.install_fake_gh(base / "gh-mirror-shim")
    fixture.reset_gh_log(log_path)
    chained = fixture.three_way_tickets()
    chained[1] = {**chained[1], "depends_on": ("T-1",)}
    fixture.run_decompose(repo, plan, chained)
    creates = [call for call in fixture.read_gh_log(log_path) if call[:2] == ["issue", "create"]]
    fixture.require(len(creates) == 5, f"epic + three stories + integration task expected: {len(creates)}")
    fixture.require("epic" in creates[0] and "Epic: ghmirror" in creates[0], f"epic first: {creates[0]}")
    epic_body = creates[0][creates[0].index("--body") + 1]
    for anchor in ("## Outcome", "## Acceptance examples", "- A-1 =", "## Vertical slices"):
        fixture.require(anchor in epic_body, f"epic body missing {anchor!r}")
    for call in creates[1:]:
        fixture.require("--parent" in call and call[call.index("--parent") + 1] == "1", f"sub-issue: {call}")
    t1 = next(call for call in creates if any(item.startswith("T-1:") for item in call))
    fixture.require("--blocked-by" not in t1 and "story" in t1, f"T-1 has no blockers: {t1}")
    t2 = next(call for call in creates if any(item.startswith("T-2:") for item in call))
    fixture.require("--blocked-by" in t2 and t2[t2.index("--blocked-by") + 1] == "2", f"T-2 blocked by T-1: {t2}")
    body = t2[t2.index("--body") + 1]
    for anchor in BODY_ANCHORS:
        fixture.require(anchor in body, f"ticket body must be self-contained, missing {anchor!r}")
    tint = next(call for call in creates if any(item.startswith("T-int:") for item in call))
    blockers = set(tint[tint.index("--blocked-by") + 1].split(","))
    fixture.require(blockers == {"2", "3", "4"} and "task" in tint, f"integration blocked by every story: {tint}")
    receipt = json.loads((plan.parent / "receipts" / "tracker.json").read_text(encoding="utf-8"))
    fixture.require(receipt["epic_ref"] == "https://example.invalid/issues/1", str(receipt))
    for ticket_id, number in (("T-1", "2"), ("T-2", "3"), ("T-3", "4"), ("T-int", "5")):
        ref = fixture.read_ticket_state(repo, "ghmirror", ticket_id)["tracker_ref"]
        fixture.require(ref.endswith(f"/issues/{number}"), f"{ticket_id} ref drifted: {ref}")
    fixture.reset_gh_log(log_path)
    import contextlib
    import io

    with contextlib.redirect_stdout(io.StringIO()):
        fixture.ticket_state.command_sync_tracker(fixture.base_args(repo, plan))
    later = [call for call in fixture.read_gh_log(log_path) if call[:2] == ["issue", "create"]]
    fixture.require(not later, f"sync must not recreate mirrored items: {later}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tracker-github-regression-") as directory:
        check_hierarchy(Path(directory).resolve())
    print("tracker-github regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
