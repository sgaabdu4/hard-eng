#!/usr/bin/env python3
"""Snapshot and restore Copilot integration paths across setup stages."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import stat
import sys
from pathlib import Path
from typing import NoReturn

SETUP_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SETUP_DIR.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup import safe_file
from scripts.setup.cli_errors import run_cli


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup:copilot-transaction: {message}")


def update_hash(digest: hashlib._Hash, value: bytes) -> None:
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def tree_digest(root: Path) -> str:
    root_metadata = root.lstat()
    if not stat.S_ISDIR(root_metadata.st_mode) or root.is_symlink():
        fail(f"transaction tree is not a regular directory: {root}")
    digest = hashlib.sha256()

    def visit(path: Path, relative: bytes) -> None:
        metadata = path.lstat()
        if metadata.st_uid != os.getuid():
            fail(f"transaction tree entry has another owner: {path}")
        update_hash(digest, relative)
        update_hash(digest, f"{stat.S_IMODE(metadata.st_mode):04o}".encode())
        if stat.S_ISDIR(metadata.st_mode):
            update_hash(digest, b"directory")
            entries = sorted(path.iterdir(), key=lambda item: os.fsencode(item.name))
            for entry in entries:
                child = os.fsencode(entry.name)
                visit(entry, relative + b"/" + child if relative else child)
        elif stat.S_ISREG(metadata.st_mode):
            update_hash(digest, b"file")
            descriptor = os.open(path, safe_file._flags(os.O_RDONLY))
            try:
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
            finally:
                os.close(descriptor)
        elif stat.S_ISLNK(metadata.st_mode):
            update_hash(digest, b"symlink")
            update_hash(digest, os.fsencode(os.readlink(path)))
        else:
            fail(f"transaction tree contains an unsupported entry: {path}")

    visit(root, b"")
    return digest.hexdigest()


def target_metadata(path: Path) -> os.stat_result | None:
    try:
        with safe_file.parent_fd(path.parent, Path(path.name)) as (directory, name):
            metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if metadata.st_uid != os.getuid():
        fail(f"transaction target has another owner: {path}")
    if stat.S_IMODE(metadata.st_mode) & 0o022:
        fail(f"transaction target has unsafe mode: {path}")
    return metadata


def capture_state(path: Path, destination: Path | None) -> dict[str, object]:
    metadata = target_metadata(path)
    if metadata is None:
        return {"kind": "absent"}
    mode = stat.S_IMODE(metadata.st_mode)
    if stat.S_ISREG(metadata.st_mode):
        content, observed_mode = safe_file.read_snapshot(path.parent, Path(path.name))
        if observed_mode != mode:
            fail(f"transaction file mode changed while reading: {path}")
        if destination is not None:
            safe_file.create_path(destination, content, 0o600)
        return {"kind": "file", "mode": mode, "sha256": hashlib.sha256(content).hexdigest()}
    if stat.S_ISDIR(metadata.st_mode):
        before = tree_digest(path)
        if destination is not None:
            shutil.copytree(path, destination, symlinks=True)
            after = tree_digest(path)
            copied = tree_digest(destination)
            if before != after or before != copied:
                fail(f"transaction tree changed while copying: {path}")
        return {"kind": "directory", "mode": mode, "sha256": before}
    fail(f"transaction target has an unsupported type: {path}")


def same_state(left: dict[str, object], right: dict[str, object]) -> bool:
    return all(left.get(key) == right.get(key) for key in ("kind", "mode", "sha256"))


def manifest_path(transaction: Path) -> Path:
    return transaction / "manifest.json"


def load_manifest(transaction: Path) -> tuple[dict[str, object], bytes, int]:
    path = manifest_path(transaction)
    try:
        raw, mode = safe_file.read_snapshot(path.parent, Path(path.name))
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"cannot read transaction manifest: {error}")
    if mode != 0o600 or not isinstance(value, dict) or not isinstance(value.get("entries"), list):
        fail("transaction manifest is invalid or not private")
    return value, raw, mode


def store_manifest(transaction: Path, value: dict[str, object], old: bytes | None = None) -> None:
    path = manifest_path(transaction)
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if old is None:
        safe_file.create_path(path, raw, 0o600)
    else:
        safe_file.replace_path_if_unchanged(path, old, 0o600, raw)


def capture(transaction: Path, paths: list[Path]) -> None:
    if manifest_path(transaction).exists():
        fail("transaction manifest already exists")
    entries: list[dict[str, object]] = []
    before_root = transaction / "before"
    before_root.mkdir(mode=0o700)
    for index, path in enumerate(paths):
        if not path.is_absolute():
            fail(f"transaction path must be absolute: {path}")
        snapshot = before_root / str(index)
        entries.append({"path": str(path), "before": capture_state(path, snapshot), "after": None})
    store_manifest(transaction, {"version": 1, "entries": entries})


def mark(transaction: Path, paths: list[Path]) -> None:
    manifest, raw, _ = load_manifest(transaction)
    entries = manifest["entries"]
    assert isinstance(entries, list)
    by_path = {entry["path"]: (index, entry) for index, entry in enumerate(entries)}
    for path in paths:
        selected = by_path.get(str(path))
        if selected is None:
            fail(f"transaction path was not captured: {path}")
        _, entry = selected
        entry["after"] = capture_state(path, None)
    store_manifest(transaction, manifest, raw)


def fsync_tree(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            continue
        flags = os.O_RDONLY
        if path.is_dir():
            flags |= getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(path, safe_file._flags(flags))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    descriptor = os.open(root, safe_file._flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def stage_directory(snapshot: Path, target: Path) -> Path:
    staging = target.with_name(f".hard-eng-copilot-restore-{secrets.token_hex(16)}")
    shutil.copytree(snapshot, staging, symlinks=True)
    fsync_tree(staging)
    return staging


def remove_directory(path: Path, expected: dict[str, object]) -> None:
    claimed_name = f".hard-eng-copilot-remove-{secrets.token_hex(16)}"
    with safe_file.parent_fd(path.parent, Path(path.name)) as (directory, name):
        os.rename(name, claimed_name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    claimed = path.with_name(claimed_name)
    if not same_state(capture_state(claimed, None), expected):
        with safe_file.parent_fd(path.parent, Path(path.name)) as (directory, name):
            os.rename(claimed_name, name, src_dir_fd=directory, dst_dir_fd=directory)
            os.fsync(directory)
        fail(f"transaction directory changed while it was claimed: {path}")
    shutil.rmtree(claimed)
    with safe_file.parent_fd(path.parent, Path(path.name), create=True) as (directory, _):
        os.fsync(directory)


def restore_directory(path: Path, before: dict[str, object], after: dict[str, object], snapshot: Path) -> None:
    if before["kind"] == "absent":
        remove_directory(path, after)
        return
    if before["kind"] != "directory" or after["kind"] != "directory":
        fail(f"unsupported transaction directory transition: {path}")
    staging = stage_directory(snapshot, path)
    try:
        with safe_file.parent_fd(path.parent, Path(path.name)) as (directory, name):
            safe_file._exchange(directory, name, staging.name)
            os.fsync(directory)
        restored = capture_state(path, None)
        displaced = capture_state(staging, None)
        if not same_state(restored, before) or not same_state(displaced, after):
            with safe_file.parent_fd(path.parent, Path(path.name)) as (directory, name):
                safe_file._exchange(directory, name, staging.name)
                os.fsync(directory)
            fail(f"transaction directory restore verification failed: {path}")
        shutil.rmtree(staging)
        with safe_file.parent_fd(path.parent, Path(path.name)) as (directory, _):
            os.fsync(directory)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def restore_file(path: Path, before: dict[str, object], after: dict[str, object], snapshot: Path) -> None:
    current, current_mode = safe_file.read_snapshot(path.parent, Path(path.name))
    if before["kind"] == "absent":
        safe_file.consume_if_unchanged(path.parent, Path(path.name), current, current_mode)
        return
    if before["kind"] != "file" or after["kind"] != "file":
        fail(f"unsupported transaction file transition: {path}")
    original, snapshot_mode = safe_file.read_snapshot(snapshot.parent, Path(snapshot.name))
    if snapshot_mode != 0o600:
        fail(f"transaction file snapshot is not private: {snapshot}")
    safe_file.replace_path_if_unchanged(path, current, current_mode, original)


def restore(transaction: Path) -> None:
    manifest, _, _ = load_manifest(transaction)
    entries = manifest["entries"]
    assert isinstance(entries, list)
    current_states: dict[int, dict[str, object]] = {}
    for index, entry in enumerate(entries):
        path = Path(entry["path"])
        current = capture_state(path, None)
        current_states[index] = current
        before = entry["before"]
        after = entry["after"]
        if after is None:
            if not same_state(current, before):
                fail(f"unrecorded transaction mutation prevents rollback: {path}")
        elif not same_state(current, before) and not same_state(current, after):
            fail(f"transaction target changed after its setup stage: {path}")
    for index in reversed(range(len(entries))):
        entry = entries[index]
        before = entry["before"]
        after = entry["after"]
        if after is None:
            continue
        path = Path(entry["path"])
        current = current_states[index]
        if same_state(current, before):
            continue
        snapshot = transaction / "before" / str(index)
        if after["kind"] == "file":
            restore_file(path, before, after, snapshot)
        elif after["kind"] == "directory":
            restore_directory(path, before, after, snapshot)
        else:
            fail(f"unsupported marked transaction state: {path}")


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in {"capture", "mark", "restore"}:
        fail("usage: copilot-transaction.py capture|mark|restore TRANSACTION [PATH ...]")
    operation = sys.argv[1]
    transaction = Path(sys.argv[2])
    if not transaction.is_absolute():
        fail("transaction directory must be absolute")
    paths = [Path(value) for value in sys.argv[3:]]
    try:
        if operation == "capture":
            if not paths:
                fail("capture requires at least one path")
            capture(transaction, paths)
        elif operation == "mark":
            if not paths:
                fail("mark requires at least one path")
            mark(transaction, paths)
        else:
            if paths:
                fail("restore does not accept paths")
            restore(transaction)
    except (OSError, shutil.Error) as error:
        fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli("setup:copilot-transaction", main))
