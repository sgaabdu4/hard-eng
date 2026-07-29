#!/usr/bin/env python3
"""CLI parser construction for the Hard Eng Feature Brief state owner."""

from __future__ import annotations

import argparse
from collections.abc import Collection


def build(replan_reasons: Collection[str]) -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Small deterministic state owner for the Hard Eng Feature Brief."
    )
    commands = root.add_subparsers(dest="command", required=True)
    for name in (
        "inspect",
        "validate",
        "approve",
        "reopen",
        "checkpoint",
        "sync-excludes",
        "assert-green",
    ):
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--plan")
        if name in {"approve", "reopen", "checkpoint"}:
            command.add_argument("--expect-token", required=True)
    init = commands.add_parser("init")
    init.add_argument("--repo", required=True)
    init.add_argument("--feature-slug", required=True)
    init.add_argument("--plan-id")
    reopen = commands.choices["reopen"]
    reopen.add_argument("--reason", required=True, choices=sorted(replan_reasons))
    commands.choices["approve"].add_argument("--approval-reply", required=True)
    checkpoint = commands.choices["checkpoint"]
    checkpoint.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    checkpoint.add_argument("--confirm-cancel", action="store_true")
    commands.choices["assert-green"].add_argument(
        "--delivered-head", action="store_true"
    )
    return root
