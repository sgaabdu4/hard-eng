#!/usr/bin/env python3
"""plan_state.py subcommands for planning-step receipts and the live tracker probe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import plan_steps
import tracker_probe
from plan_sections import PlanError, with_closing_rows
from safe_plan_io import replace_if_unchanged, repo_root


def record_step(args: argparse.Namespace, state) -> None:
    repo = repo_root(args.repo)
    payload = plan_steps.read_payload(args.payload_file)
    path = state.resolve_plan(repo, args.plan)
    with state.plan_lock(repo, path):
        path, text, mode, plan = state.read_checked(repo, str(path), validate_authorization=False)
        if plan["lifecycle_status"] != "planning":
            raise PlanError("record-step requires a planning brief")
        entry = plan_steps.record(repo, path, args.step, payload)
        if args.step == "closing":
            candidate = with_closing_rows(text, str(entry["tickets"]), str(entry["tracker"]))
            plan = state.validate_text(candidate)
            replace_if_unchanged(repo, path.relative_to(repo), text.encode("utf-8"), mode, candidate.encode("utf-8"))
            text = candidate
    state.emit(path, text, plan)
    print(f"recorded_step={args.step}")
    print(f"recorded_at={entry['recorded_at']}")


def probe_trackers(args: argparse.Namespace, state) -> None:
    repo = repo_root(args.repo)
    path, text, _, plan = state.read_checked(repo, args.plan, validate_authorization=False)
    if plan["lifecycle_status"] != "planning":
        raise PlanError("probe-trackers requires a planning brief")
    results = plan_steps.record_probes(repo, path)
    state.emit(path, text, plan)
    for line in tracker_probe.emit_lines(results):
        print(line)
    if args.write_env_example:
        print(f"env_example={'written' if tracker_probe.write_env_example(repo) else 'current'}")
