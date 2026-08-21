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
        if name != "approve":
            command.add_argument("--session-id", default=None)
            command.add_argument("--request-digest", default=None)
        if name in {"approve", "reopen", "checkpoint"}:
            command.add_argument("--expect-token", required=True)
    init = commands.add_parser("init")
    init.add_argument("--repo", required=True)
    init.add_argument("--feature-slug", required=True)
    init.add_argument("--plan-id")
    reopen = commands.choices["reopen"]
    reopen.add_argument("--reason", required=True, choices=sorted(replan_reasons))
    reopen.add_argument("--recover-invalid-authorization", action="store_true")
    approve = commands.choices["approve"]
    approve.add_argument("--approval-reply", required=True)
    approve.add_argument("--session-id", required=True)
    approve.add_argument("--request-digest", required=True)
    approve.add_argument("--allowed-action", action="append", default=[])
    approve.add_argument("--expires-in-seconds", type=int, default=3600)
    checkpoint = commands.choices["checkpoint"]
    checkpoint.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    checkpoint.add_argument("--confirm-cancel", action="store_true")
    assert_green = commands.choices["assert-green"]
    assert_green.add_argument("--delivered-head", action="store_true")
    assert_green.add_argument("--artifact-only", action="store_true")
    return root
