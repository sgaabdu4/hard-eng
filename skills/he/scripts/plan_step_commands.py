#!/usr/bin/env python3
"""plan_state.py subcommands for planning-step receipts and the live tracker probe."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_report
import build_steps
import external_claims
import mutation_receipt
import plan_steps
import review_packet
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


def _locked_record(args: argparse.Namespace, state, allowed: set[str], label: str, action):
    repo = repo_root(args.repo)
    payload = build_steps.read_payload(args.payload_file)
    path = state.resolve_plan(repo, args.plan)
    with state.plan_lock(repo, path):
        path, text, _, plan = state.read_checked(repo, str(path), validate_authorization=False)
        if plan["lifecycle_status"] not in allowed:
            raise PlanError(f"{label} requires a {' or '.join(sorted(allowed))} brief")
        entry = action(repo, path, payload)
    return path, text, plan, entry


def record_build(args: argparse.Namespace, state) -> None:
    path, text, plan, entry = _locked_record(
        args, state, {"building"}, "record-build", lambda r, p, y: build_steps.record(r, p, args.slice, args.step, y)
    )
    state.emit(path, text, plan)
    print(f"recorded_build={args.slice}:{args.step}")
    print(f"recorded_at={entry['recorded_at']}")


def review_packet_command(args: argparse.Namespace, state) -> None:
    repo = repo_root(args.repo)
    path, _, _, plan = state.read_checked(repo, args.plan, validate_authorization=False)
    if plan["lifecycle_status"] != "building":
        raise PlanError("review-packet requires a building brief")
    round_number = build_steps.next_review_round(repo, path, args.slice)
    if round_number > build_steps.MAX_REVIEW_ROUNDS:
        raise PlanError(f"{args.slice} already used {build_steps.MAX_REVIEW_ROUNDS} review rounds; ask the user")
    target, sha = review_packet.write(
        repo, path, args.slice, round_number, build_steps.edges_of(repo, path, args.slice)
    )
    print(f"packet={target}")
    print(f"packet_round={round_number}")
    print(f"packet_sha256={sha}")


def verify_packet_command(args: argparse.Namespace, state) -> None:
    repo = repo_root(args.repo)
    path, _, _, plan = state.read_checked(repo, args.plan, validate_authorization=False)
    if plan["lifecycle_status"] != "building":
        raise PlanError("verify-packet requires a building brief")
    edges = None if args.slice == build_steps.FULL else build_steps.edges_of(repo, path, args.slice)
    target, sha = review_packet.write_verify(repo, path, args.slice, edges)
    print(f"packet={target}")
    print(f"packet_sha256={sha}")


def validate_command(args: argparse.Namespace, state) -> None:
    repo = state.repo_root(args.repo)
    path, text, _, plan = state.read_checked(repo, args.plan)
    if plan["lifecycle_status"] == "planning" and (blocked := external_claims.claim_error(repo, path)):
        raise state.PlanError(blocked)
    state.emit(path, text, plan)


def build_report_command(args: argparse.Namespace, state) -> None:
    repo = state.repo_root(args.repo)
    path, text, _, plan = state.read_checked(repo, args.plan, validate_authorization=False)
    if plan["lifecycle_status"] not in {"building", "green"}:
        raise state.PlanError("build-report requires building or green state")
    target = build_report.write(repo, path)
    state.emit(path, text, plan)
    print(f"build_report={target.relative_to(repo)}")


def record_mutation(args: argparse.Namespace, state) -> None:
    path, text, plan, entry = _locked_record(
        args, state, {"building", "green"}, "record-mutation", mutation_receipt.record
    )
    state.emit(path, text, plan)
    scope, survivors = entry["scope"], entry["survivors"]
    assert isinstance(scope, list) and isinstance(survivors, list)
    print(f"recorded_mutation={entry['runner']}")
    print(f"mutation_scope={len(scope)}")
    print(f"mutation_survivors={len(survivors)}")
