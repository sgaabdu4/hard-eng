#!/usr/bin/env python3
"""CLI parser construction for the Hard Eng Feature Brief state owner."""

from __future__ import annotations

import argparse
from collections.abc import Collection


def build(replan_reasons: Collection[str]) -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Small deterministic state owner for the Hard Eng Feature Brief.")
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("inspect", "validate", "approve", "reopen", "checkpoint", "sync-excludes", "assert-green"):
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--plan")
        if name in {"approve", "reopen", "checkpoint"}:
            command.add_argument("--expect-token", required=True)
    init = commands.add_parser("init")
    init.add_argument("--repo", required=True)
    init.add_argument("--feature-slug", required=True)
    init.add_argument("--plan-id")
    cleanup = commands.add_parser("cleanup")
    cleanup.add_argument("--repo", required=True)
    cleanup.add_argument("--item", action="append", required=True, metavar="PATH=SHA256")
    cleanup.add_argument("--decision", required=True)
    cleanup.add_argument("--apply", action="store_true")
    cleanup.add_argument("--confirm-cancel", action="store_true")
    cleanup.add_argument("--confirm-delete", action="store_true")
    record_step = commands.add_parser("record-step")
    record_step.add_argument("--repo", required=True)
    record_step.add_argument("--plan", required=True)
    record_step.add_argument("--step", required=True)
    record_step.add_argument("--payload-file", required=True, help="JSON object path, or - for stdin")
    record_build = commands.add_parser("record-build")
    record_build.add_argument("--repo", required=True)
    record_build.add_argument("--plan", required=True)
    record_build.add_argument("--slice", required=True, help="S-N, or full for the whole-feature verify record")
    record_build.add_argument("--step", required=True)
    record_build.add_argument("--payload-file", required=True, help="JSON object path, or - for stdin")
    packet = commands.add_parser("review-packet")
    packet.add_argument("--repo", required=True)
    packet.add_argument("--plan", required=True)
    packet.add_argument("--slice", required=True)
    verify_packet = commands.add_parser("verify-packet")
    verify_packet.add_argument("--repo", required=True)
    verify_packet.add_argument("--plan", required=True)
    verify_packet.add_argument("--slice", required=True, help="S-N, or full for the whole-feature verifier packet")
    build_report = commands.add_parser("build-report")
    build_report.add_argument("--repo", required=True)
    build_report.add_argument("--plan", required=True)
    record_mutation = commands.add_parser("record-mutation")
    record_mutation.add_argument("--repo", required=True)
    record_mutation.add_argument("--plan", required=True)
    record_mutation.add_argument("--payload-file", required=True, help="JSON object path, or - for stdin")
    probe = commands.add_parser("probe-trackers")
    probe.add_argument("--repo", required=True)
    probe.add_argument("--plan", required=True)
    probe.add_argument("--write-env-example", action="store_true")
    draft = commands.add_parser("draft")
    draft.add_argument("--repo", required=True)
    draft.add_argument("--plan", required=True)
    draft.add_argument("--expect-token", required=True)
    draft.add_argument("--candidate", required=True)
    reopen = commands.choices["reopen"]
    reopen.add_argument("--reason", required=True, choices=sorted(replan_reasons))
    reopen.add_argument("--recover-invalid-authorization", action="store_true")
    approve = commands.choices["approve"]
    approve.add_argument("--approval-reply", required=True)
    approve.add_argument("--allowed-action", action="append", default=[])
    checkpoint = commands.choices["checkpoint"]
    checkpoint.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    checkpoint.add_argument("--confirm-cancel", action="store_true")
    assert_green = commands.choices["assert-green"]
    assert_green.add_argument("--delivered-head", action="store_true")
    assert_green.add_argument("--artifact-only", action="store_true")
    return root
