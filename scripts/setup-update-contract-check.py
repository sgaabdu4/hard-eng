#!/usr/bin/env python3
"""Deterministic behavior checks for the reviewed-pin update transaction."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
UPDATE_PATH = ROOT / "scripts/setup/update.py"
PIN_STATE_PATH = ROOT / "scripts/setup/pin-state.py"


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


def load_pin_state_module():
    spec = importlib.util.spec_from_file_location("setup_pin_state", PIN_STATE_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load installed pin-state owner")
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


def check_change_after_snapshot(update) -> None:
    with tempfile.TemporaryDirectory(prefix="setup-update-cas-") as name:
        updates, _ = fixture(Path(name))
        changed = next(iter(updates))

        def race(target: Path, before: bytes, mode: int, content: bytes) -> None:
            if target == changed:
                target.write_bytes(b"late-concurrent-user-change\n")
            update.safe_file.replace_path_if_unchanged(
                target, before, mode, content
            )

        try:
            update.commit_files(updates, lambda: None, safe_replace=race)
        except OSError:
            pass
        else:
            fail("post-snapshot concurrent change was overwritten")
        if changed.read_bytes() != b"late-concurrent-user-change\n":
            fail("post-snapshot concurrent bytes were not preserved")


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


def check_download_deadline(update) -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, _size: int) -> bytes:
            return b"slow-byte"

    original_urlopen = update.urllib.request.urlopen
    original_monotonic = update.time.monotonic
    ticks = iter((0.0, 121.0))
    update.urllib.request.urlopen = lambda _url, timeout: Response()
    update.time.monotonic = lambda: next(ticks)
    candidate = {
        "binaries": {
            "tool": {
                "assets": {
                    "platform": {
                        "url": "https://example.invalid/slow",
                        "sha256": "0" * 64,
                    }
                }
            }
        }
    }
    try:
        with tempfile.TemporaryDirectory(prefix="setup-update-deadline-") as name:
            try:
                update.verify_binary_assets(candidate, Path(name))
            except update.UpdateError as error:
                if "deadline" not in str(error):
                    fail("download deadline returned an unrelated failure")
            else:
                fail("slow-byte download ignored its whole-run deadline")
    finally:
        update.urllib.request.urlopen = original_urlopen
        update.time.monotonic = original_monotonic


def check_static_contract(update) -> None:
    if {update.MANIFEST_PATH, update.PACKAGE_PATH, update.LOCK_PATH} != {
        ROOT / "scripts/setup/manifest.json",
        ROOT / "runtime/npm/package.json",
        ROOT / "runtime/npm/package-lock.json",
    }:
        fail("managed update target set drifted")
    if "latest" in UPDATE_PATH.read_text(encoding="utf-8").lower():
        fail("updater contains latest-floating resolution")


def check_documented_convergence() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)^Pin updates are explicit:\n\n```bash\n(?P<commands>.*?)\n```",
        readme,
    )
    if match is None:
        fail("README pin-update sequence is missing")
    commands = match.group("commands").splitlines()
    expected = [
        "./setup.sh update /tmp/reviewed-setup-manifest.json",
        "git diff -- scripts/setup/manifest.json runtime/npm/package.json runtime/npm/package-lock.json",
        "./setup.sh install",
        "./setup.sh check",
    ]
    if commands != expected:
        fail("README pin-update sequence does not converge installed state before check")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    install = setup.partition("install_tools() {")[2].partition("\n}\n")[0]
    check = setup.partition("check_tools() {")[2].partition("\n}\n")[0]
    if "install_npm_runtime" not in install or "check_npm_runtime" not in check:
        fail("documented install/check sequence is not wired to the pinned runtime")
    record = 'pin-state.py" record'
    verify = 'pin-state.py" check'
    if record not in setup or verify not in setup or setup.index(record) > setup.index(verify):
        fail("setup does not record and verify exact installed pins after convergence")


def check_end_to_end_pin_change(update) -> None:
    pin_state = load_pin_state_module()
    with tempfile.TemporaryDirectory(prefix="setup-update-e2e-") as name:
        root = Path(name)
        files = {
            root / "scripts/setup/manifest.json": b'{"pin":"1.0.0"}\n',
            root / "runtime/npm/package.json": b'{"dependency":"1.0.0"}\n',
            root / "runtime/npm/package-lock.json": b'{"lock":"1.0.0"}\n',
        }
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            path.chmod(0o644)
        for arguments in (
            ["git", "init", "-q", str(root)],
            ["git", "-C", str(root), "config", "user.name", "Fixture"],
            ["git", "-C", str(root), "config", "user.email", "fixture@example.invalid"],
            ["git", "-C", str(root), "add", "."],
            ["git", "-C", str(root), "commit", "-qm", "baseline"],
        ):
            result = update.run(arguments, timeout=30)
            if result.returncode:
                fail(result.stderr.strip() or "cannot create pin convergence fixture")
        state = root / ".state/setup-pins.sha256"
        pin_state.record(root, state)
        pin_state.check(root, state)
        updates = {
            path: content.replace(b"1.0.0", b"1.0.1")
            for path, content in files.items()
        }
        update.commit_files(updates, lambda: None)
        reviewed = update.run(
            [
                "git",
                "-C",
                str(root),
                "diff",
                "--",
                "scripts/setup/manifest.json",
                "runtime/npm/package.json",
                "runtime/npm/package-lock.json",
            ],
            timeout=30,
        )
        if reviewed.returncode or not all(
            path.relative_to(root).as_posix() in reviewed.stdout for path in updates
        ):
            fail("representative pin update did not produce the documented review diff")
        try:
            pin_state.check(root, state)
        except pin_state.PinStateError:
            pass
        else:
            fail("updated pins passed before install convergence")
        pin_state.record(root, state)
        pin_state.check(root, state)


def main() -> int:
    update = load_update_module()
    check_static_contract(update)
    check_success(update)
    check_validator_rollback(update)
    check_replace_rollback(update)
    check_concurrent_change(update)
    check_change_after_snapshot(update)
    check_structure_restrictions(update)
    check_download_deadline(update)
    check_documented_convergence()
    check_end_to_end_pin_change(update)
    print("setup-update-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
