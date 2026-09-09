#!/usr/bin/env python3
"""More regression checks that kill surviving mutants of execution_direct.py."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execution_direct as ed
import execution_direct_survivors_regression as base
from evidence_lib import direct_receipt_path

fail, require = base.make_checker("execution-direct-survivors-2")

capture = base.capture
expect_fail = base.expect_fail
make_repo = base.make_repo
start_args = base.start_args
read_receipt = base.read_receipt
base_value = base.base_value
DIGEST_B = base.DIGEST_B
protected_consume_fixture = base.protected_consume_fixture


def test_command_check_direct_sorts_keys(repo: Path) -> None:
    ed.command_start_direct(start_args(repo))
    stored = read_receipt(repo)
    reordered = dict(reversed(list(stored.items())))
    direct_receipt_path(repo).write_text(json.dumps(reordered), encoding="utf-8")
    printed = capture(ed.command_check_direct, argparse.Namespace(repo=str(repo)))
    require(
        printed == json.dumps(stored, sort_keys=True, separators=(",", ":")),
        f"check-direct must print keys in sorted order, got {printed!r}",
    )


def test_command_consume_direct_passes_decoded_value(repo: Path) -> None:
    ed.command_start_direct(start_args(repo))
    nonce = read_receipt(repo)["write_nonce"]
    captured: dict[str, object] = {}
    original = ed.validate_direct_receipt

    def spy(repo_arg: Path, *, value: dict[str, object] | None = None) -> dict[str, object]:
        captured["value"] = value
        return original(repo_arg, value=value)

    ed.validate_direct_receipt = spy
    try:
        ed.command_consume_direct(argparse.Namespace(repo=str(repo), write_nonce=nonce))
    finally:
        ed.validate_direct_receipt = original
    require(
        captured.get("value") is not None,
        "consume-direct must validate the already-decoded receipt, not reload it from disk",
    )


def test_command_consume_protected_direct_rejects_non_dict(repo: Path) -> None:
    consume_args, path, original = protected_consume_fixture(repo)
    path.write_bytes(b"[]")
    expect_fail("direct protected authorization is invalid", ed.command_consume_protected_direct, consume_args)
    path.write_bytes(original)


def test_command_start_direct_allow_subagents(repo: Path) -> None:
    ed.command_start_direct(start_args(repo, allow_subagents=True))
    stored = read_receipt(repo)
    require(
        stored["allowed"] == ["reversible-local-work", "parallel-subagents"],
        f"allow_subagents must add the exact literal parallel-subagents, got {stored['allowed']!r}",
    )


def test_validate_direct_receipt_accepts_tree_scope(repo: Path) -> None:
    tree_value = base_value(repo, intended_paths=[{"path": "newdir", "scope": "tree"}])
    require(
        ed.validate_direct_receipt(repo, value=tree_value) == tree_value,
        "an intended path scoped as tree must be accepted",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="execution-direct-survivors2-") as temporary:
        repo = make_repo(Path(temporary))
        test_command_check_direct_sorts_keys(repo)
        test_command_consume_direct_passes_decoded_value(repo)
        test_command_consume_protected_direct_rejects_non_dict(repo)
        test_command_start_direct_allow_subagents(repo)
        test_validate_direct_receipt_accepts_tree_scope(repo)
    print("execution-direct-survivors-2: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
