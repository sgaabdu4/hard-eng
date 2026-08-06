#!/usr/bin/env python3
"""Deterministic behavior checks for the reviewed-pin update transaction."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
UPDATE_PATH = ROOT / "scripts/setup/update.py"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-update-contract: FAIL: {message}")


def load_update_module():
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("setup_update", UPDATE_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load update owner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(directory: Path) -> tuple[dict[Path, bytes], dict[Path, tuple[bytes, int]]]:
    updates: dict[Path, bytes] = {}
    snapshots: dict[Path, tuple[bytes, int]] = {}
    for index, mode in enumerate((0o600, 0o640, 0o644)):
        target = directory / f"managed-{index}.json"
        before = f"before-{index}\n".encode()
        target.write_bytes(before)
        target.chmod(mode)
        updates[target] = f"after-{index}\n".encode()
        snapshots[target] = (before, mode)
    return updates, snapshots


def assert_state(expected: dict[Path, tuple[bytes, int]]) -> None:
    for target, (content, mode) in expected.items():
        if target.read_bytes() != content:
            fail(f"content mismatch: {target.name}")
        actual_mode = stat.S_IMODE(target.stat().st_mode)
        if actual_mode != mode:
            fail(f"mode mismatch: {target.name}")


def check_success(update) -> None:
    with tempfile.TemporaryDirectory(prefix="setup-update-success-") as name:
        updates, snapshots = fixture(Path(name))
        calls = []
        update.commit_files(updates, lambda: calls.append("validated"))
        assert_state(
            {
                target: (content, snapshots[target][1])
                for target, content in updates.items()
            }
        )
        if calls != ["validated"]:
            fail("successful update did not validate once")
        update.commit_files(updates, lambda: calls.append("revalidated"))
        if calls != ["validated", "revalidated"]:
            fail("no-op update did not revalidate")


def check_validator_rollback(update) -> None:
    with tempfile.TemporaryDirectory(prefix="setup-update-validator-") as name:
        updates, snapshots = fixture(Path(name))

        def reject() -> None:
            raise update.UpdateError("injected validator failure")

        try:
            update.commit_files(updates, reject)
        except update.UpdateError:
            pass
        else:
            fail("validator failure was accepted")
        assert_state(snapshots)


def check_replace_rollback(update) -> None:
    with tempfile.TemporaryDirectory(prefix="setup-update-replace-") as name:
        updates, snapshots = fixture(Path(name))
        calls = 0

        def fail_second(source, target) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected replace failure")
            os.replace(source, target)

        try:
            update.commit_files(updates, lambda: None, replace=fail_second)
        except OSError:
            pass
        else:
            fail("replace failure was accepted")
        assert_state(snapshots)


def check_concurrent_change(update) -> None:
    with tempfile.TemporaryDirectory(prefix="setup-update-concurrent-") as name:
        updates, snapshots = fixture(Path(name))
        expected = {target: content for target, (content, _) in snapshots.items()}
        changed = next(iter(updates))
        changed.write_bytes(b"concurrent-user-change\n")
        try:
            update.commit_files(updates, lambda: None, expected=expected)
        except update.UpdateError:
            pass
        else:
            fail("concurrent managed-file change was overwritten")
        if changed.read_bytes() != b"concurrent-user-change\n":
            fail("concurrent managed-file bytes were not preserved")


def check_structure_restrictions(update) -> None:
    current = json.loads(
        (ROOT / "scripts/setup/manifest.json").read_text(encoding="utf-8")
    )
    candidate = json.loads(json.dumps(current))
    candidate["npm_runtime"]["remove_paths"].append("user-owned")
    try:
        update.validate_structure(current, candidate)
    except update.UpdateError:
        pass
    else:
        fail("non-pin manifest change was accepted")
    candidate = json.loads(json.dumps(current))
    candidate["unexpected"] = "not-a-pin"
    try:
        update.load_manifest_module().validate(candidate)
    except SystemExit:
        pass
    else:
        fail("unknown manifest structure was accepted")


def check_static_contract(update) -> None:
    if {update.MANIFEST_PATH, update.PACKAGE_PATH, update.LOCK_PATH} != {
        ROOT / "scripts/setup/manifest.json",
        ROOT / "runtime/npm/package.json",
        ROOT / "runtime/npm/package-lock.json",
    }:
        fail("managed update target set drifted")
    if "latest" in UPDATE_PATH.read_text(encoding="utf-8").lower():
        fail("updater contains latest-floating resolution")


def main() -> int:
    update = load_update_module()
    check_static_contract(update)
    check_success(update)
    check_validator_rollback(update)
    check_replace_rollback(update)
    check_concurrent_change(update)
    check_structure_restrictions(update)
    print("setup-update-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
