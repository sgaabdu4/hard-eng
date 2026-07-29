#!/usr/bin/env python3
"""Coordinate read-only gates around scanners that transiently rewrite source."""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

from git_env import git_env

LOCK_NAME = "hard-eng-source-tree.lock"
POISON_NAME = "hard-eng-source-tree.poison.json"
SCANNER_PACKAGES = {"dart-decimate", "fallow", "react-doctor"}
SCANNER_BIN_NAMES = {
    name
    for package in SCANNER_PACKAGES
    for name in (package, f"{package}.cmd", f"{package}.ps1")
}


class CoordinationError(ValueError):
    """Unsafe source-tree coordination state."""


def remaining(deadline: float, action: str) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise CoordinationError(f"whole-run timeout exhausted {action}")
    return value


def git_private_path(repo: Path, name: str) -> Path:
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "rev-parse",
            "--path-format=absolute",
            "--git-path",
            name,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise CoordinationError(f"cannot resolve Git-private {name}")
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else (repo / path).resolve()


def boot_identity() -> str:
    linux = Path("/proc/sys/kernel/random/boot_id")
    if linux.is_file():
        value = linux.read_text(encoding="utf-8").strip()
        if value:
            return f"linux:{value}"
    if sys.platform == "darwin":
        result = subprocess.run(
            ["sysctl", "-n", "kern.boottime"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"darwin:{result.stdout.strip()}"
    raise CoordinationError("cannot establish a reboot-safe boot identity")


def _write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise CoordinationError("cannot write coordination metadata")
        offset += written


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    if path.exists() or path.is_symlink():
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise CoordinationError(
                "coordination metadata must be a current-user regular file"
            )
    temporary = path.parent / (
        f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise CoordinationError(
                "coordination temporary must be a current-user regular file"
            )
        _write_all(
            descriptor,
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(),
        )
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, object]:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or metadata.st_size > 4096
        ):
            raise CoordinationError(
                "coordination metadata must be a bounded current-user regular file"
            )
        raw = os.read(descriptor, metadata.st_size)
    finally:
        os.close(descriptor)
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise CoordinationError("coordination metadata is invalid") from error
    if not isinstance(value, dict):
        raise CoordinationError("coordination metadata is invalid")
    return value


def _git_bytes(repo: Path, args: list[str], deadline: float | None) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=False,
            capture_output=True,
            env=git_env(),
            timeout=remaining(deadline, "while fingerprinting") if deadline else None,
        )
    except subprocess.TimeoutExpired as error:
        raise CoordinationError(
            "whole-run timeout exhausted while fingerprinting"
        ) from error
    if result.returncode:
        raise CoordinationError("cannot snapshot repository files")
    return result.stdout


def tree_fingerprint(repo: Path, *, deadline: float | None = None) -> str:
    tracked: dict[bytes, list[bytes]] = {}
    for record in _git_bytes(repo, ["ls-files", "-z", "-s", "-c"], deadline).split(
        b"\0"
    ):
        if not record:
            continue
        try:
            metadata, path = record.split(b"\t", 1)
            mode = metadata.split(b" ", 1)[0]
        except ValueError as error:
            raise CoordinationError("cannot parse tracked repository mode") from error
        if not re.fullmatch(rb"[0-7]{6}", mode):
            raise CoordinationError("cannot parse tracked repository mode")
        tracked.setdefault(path, []).append(metadata)
    untracked = {
        path
        for path in _git_bytes(
            repo, ["ls-files", "-z", "-o", "--exclude-standard"], deadline
        ).split(b"\0")
        if path
    }
    paths = set(tracked) | untracked
    include = repo / ".worktreeinclude"
    if include.is_file():
        for entry in include.read_text(encoding="utf-8").splitlines():
            entry = entry.strip()
            if not entry or entry.startswith("#"):
                continue
            ignored = _git_bytes(
                repo,
                [
                    "ls-files",
                    "-z",
                    "--others",
                    "--ignored",
                    "--exclude-standard",
                    "--",
                    entry,
                ],
                deadline,
            )
            paths.update(path for path in ignored.split(b"\0") if path)
    digest = hashlib.sha256()
    for raw in sorted(paths):
        relative = os.fsdecode(raw)
        path = repo / relative
        digest.update(raw)
        digest.update(b"\0index=")
        digest.update(
            b"|".join(sorted(tracked[raw])) if raw in tracked else b"untracked"
        )
        digest.update(b"\0")
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            digest.update(b"<deleted>\0")
            continue
        except OSError as error:
            raise CoordinationError(f"cannot snapshot {relative}: {error}") from error
        digest.update(f"worktree-mode={metadata.st_mode:o}\0".encode())
        try:
            if stat.S_ISLNK(metadata.st_mode):
                content = os.fsencode(os.readlink(path))
            elif stat.S_ISDIR(metadata.st_mode):
                content = b"<directory>"
            else:
                content = path.read_bytes()
        except OSError as error:
            raise CoordinationError(f"cannot snapshot {relative}: {error}") from error
        digest.update(content)
        digest.update(b"\0")
    if deadline:
        remaining(deadline, "while fingerprinting")
    return digest.hexdigest()


def terminal_receipt_spec(repo: Path) -> tuple[Path, str]:
    token = secrets.token_hex(32)
    path = git_private_path(
        repo, f"hard-eng-terminal-{os.getpid()}-{secrets.token_hex(8)}.json"
    )
    return path, token


def terminal_receipt_valid(path: Path, token: str) -> bool:
    try:
        payload = _read_json(path)
    except (FileNotFoundError, CoordinationError):
        return False
    return payload.get("terminal") is True and secrets.compare_digest(
        str(payload.get("token", "")), token
    )


def consume_terminal_receipt(path: Path, token: str) -> None:
    if not terminal_receipt_valid(path, token):
        raise CoordinationError("bounded command lacks terminal process-group proof")
    path.unlink()
    _fsync_directory(path.parent)


def _poison_path(lock_path: Path) -> Path:
    return lock_path.with_name(POISON_NAME)


def begin_react_doctor(
    lock_path: Path,
    expected: str,
    receipt_path: Path,
    receipt_token: str,
) -> None:
    atomic_json(
        _poison_path(lock_path),
        {
            "boot_id": boot_identity(),
            "expected": expected,
            "receipt": receipt_path.name,
            "receipt_token": receipt_token,
        },
    )


def _poison_payload(path: Path) -> dict[str, str]:
    payload = _read_json(path)
    values = {
        key: payload.get(key)
        for key in ("boot_id", "expected", "receipt", "receipt_token")
    }
    if (
        not all(isinstance(value, str) for value in values.values())
        or not re.fullmatch(r"[0-9a-f]{64}", values["expected"])
        or not re.fullmatch(r"hard-eng-terminal-[0-9]+-[0-9a-f]+\.json", values["receipt"])
        or not re.fullmatch(r"[0-9a-f]{64}", values["receipt_token"])
    ):
        raise CoordinationError("source-tree quarantine is invalid")
    return values


def clear_react_doctor_quarantine(
    repo: Path,
    lock_path: Path,
    *,
    expected: str,
    receipt_path: Path,
    receipt_token: str,
    deadline: float,
) -> None:
    poison = _poison_payload(_poison_path(lock_path))
    if poison != {
        "boot_id": boot_identity(),
        "expected": expected,
        "receipt": receipt_path.name,
        "receipt_token": receipt_token,
    }:
        raise CoordinationError("React Doctor quarantine ownership changed")
    if not terminal_receipt_valid(receipt_path, receipt_token):
        raise CoordinationError("React Doctor lacks terminal process-group proof")
    if tree_fingerprint(repo, deadline=deadline) != expected:
        raise CoordinationError("React Doctor did not restore the exact source tree")
    consume_terminal_receipt(receipt_path, receipt_token)
    _poison_path(lock_path).unlink()
    _fsync_directory(lock_path.parent)


def rollback_react_doctor_launch(
    repo: Path,
    lock_path: Path,
    *,
    expected: str,
    receipt_path: Path,
    receipt_token: str,
    deadline: float,
) -> None:
    poison = _poison_payload(_poison_path(lock_path))
    if poison != {
        "boot_id": boot_identity(),
        "expected": expected,
        "receipt": receipt_path.name,
        "receipt_token": receipt_token,
    }:
        raise CoordinationError("React Doctor launch quarantine ownership changed")
    if receipt_path.exists() or receipt_path.is_symlink():
        raise CoordinationError(
            "React Doctor launch produced terminal metadata unexpectedly"
        )
    if tree_fingerprint(repo, deadline=deadline) != expected:
        raise CoordinationError(
            "React Doctor launch failure coincided with a source-tree change"
        )
    _poison_path(lock_path).unlink()
    _fsync_directory(lock_path.parent)


def _reject_poisoned_tree(repo: Path, lock_path: Path, deadline: float) -> None:
    path = _poison_path(lock_path)
    try:
        payload = _poison_payload(path)
    except FileNotFoundError:
        return
    receipt = lock_path.parent / payload["receipt"]
    terminal = payload["boot_id"] != boot_identity() or terminal_receipt_valid(
        receipt, payload["receipt_token"]
    )
    if not terminal:
        raise CoordinationError(
            "source tree is quarantined until React Doctor process-group terminality "
            "is proven"
        )
    if tree_fingerprint(repo, deadline=deadline) != payload["expected"]:
        raise CoordinationError(
            "source tree is quarantined after interrupted React Doctor; "
            "restore the exact worktree before any gate"
        )
    if receipt.exists():
        if payload["boot_id"] == boot_identity():
            consume_terminal_receipt(receipt, payload["receipt_token"])
        else:
            metadata = receipt.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise CoordinationError("stale terminal receipt is unsafe")
            receipt.unlink()
            _fsync_directory(receipt.parent)
    path.unlink()
    _fsync_directory(lock_path.parent)


def _cleanup_torn_temps(lock_path: Path) -> None:
    changed = False
    for pattern in (
        f".{POISON_NAME}.*.tmp",
        ".hard-eng-terminal-*.json.*.tmp",
    ):
        for path in lock_path.parent.glob(pattern):
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise CoordinationError(
                    "coordination temporary must be a current-user regular file"
                )
            path.unlink()
            changed = True
    if changed:
        _fsync_directory(lock_path.parent)


def _cleanup_orphan_receipts(lock_path: Path) -> None:
    referenced: set[str] = set()
    try:
        referenced.add(_poison_payload(_poison_path(lock_path))["receipt"])
    except FileNotFoundError:
        pass
    except CoordinationError:
        return
    changed = False
    for path in lock_path.parent.glob("hard-eng-terminal-*-*.json"):
        if path.name in referenced:
            continue
        match = re.fullmatch(
            r"hard-eng-terminal-([0-9]+)-[0-9a-f]+\.json",
            path.name,
        )
        if not match:
            continue
        try:
            os.kill(int(match.group(1)), 0)
        except PermissionError:
            continue
        except ProcessLookupError:
            metadata = path.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                raise CoordinationError("orphan terminal receipt is unsafe")
            path.unlink()
            changed = True
        else:
            continue
    if changed:
        _fsync_directory(lock_path.parent)


@contextlib.contextmanager
def source_tree_lock(
    repo: Path,
    *,
    exclusive: bool,
    deadline: float,
    allow_poison: bool = False,
):
    lock_path = git_private_path(repo, LOCK_NAME)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    locked = False
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise CoordinationError(
                "source-tree lock must be a current-user regular file"
            )
        operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        while True:
            wait = remaining(deadline, "waiting for source-tree coordination")
            try:
                fcntl.flock(descriptor, operation | fcntl.LOCK_NB)
                locked = True
                break
            except BlockingIOError:
                time.sleep(min(0.05, wait))
        _cleanup_torn_temps(lock_path)
        _cleanup_orphan_receipts(lock_path)
        if not allow_poison:
            _reject_poisoned_tree(repo, lock_path, deadline)
        yield lock_path
    finally:
        if locked:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def validate_external_npx(
    repo: Path,
    *,
    deadline: float | None = None,
) -> Path:
    executable = shutil.which("npx")
    if not executable:
        raise CoordinationError("npx is required")
    resolved = Path(executable).resolve()
    try:
        resolved.relative_to(repo.resolve())
    except ValueError:
        pass
    else:
        raise CoordinationError("npx must resolve outside the project repository")
    node_modules = repo / "node_modules"
    try:
        node_modules_metadata = node_modules.lstat()
    except FileNotFoundError:
        node_modules_metadata = None
    if node_modules_metadata is not None:
        if not (
            stat.S_ISDIR(node_modules_metadata.st_mode)
            or (
                stat.S_ISLNK(node_modules_metadata.st_mode)
                and node_modules.is_dir()
            )
        ):
            raise CoordinationError(
                "project-local node_modules must not redirect scanner resolution"
            )
        for package in sorted(SCANNER_PACKAGES):
            scanner = node_modules / package
            try:
                scanner.lstat()
            except FileNotFoundError:
                pass
            else:
                raise CoordinationError(
                    f"project-local scanner runtime is forbidden: {scanner.relative_to(repo)}"
                )
        binary_root = node_modules / ".bin"
        for name in sorted(SCANNER_BIN_NAMES):
            binary = binary_root / name
            try:
                binary.lstat()
            except FileNotFoundError:
                pass
            else:
                raise CoordinationError(
                    f"project-local scanner binary is forbidden: {binary.relative_to(repo)}"
                )
    manifests = _git_bytes(
        repo,
        [
            "ls-files",
            "-z",
            "-c",
            "-o",
            "--exclude-standard",
            "--",
            "package.json",
            ":(glob)**/package.json",
        ],
        deadline,
    )
    manifest_paths = {
        path for path in manifests.split(b"\0") if path
    }
    root_manifest = repo / "package.json"
    if root_manifest.exists() or root_manifest.is_symlink():
        manifest_paths.add(b"package.json")
    for raw in sorted(manifest_paths):
        path = repo / os.fsdecode(raw)
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or path.is_symlink()
            or metadata.st_size > 1_048_576
        ):
            raise CoordinationError(
                f"cannot validate unsafe {path.relative_to(repo)}"
            )
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise CoordinationError(f"cannot validate {path.relative_to(repo)}") from error
        if not isinstance(payload, dict):
            continue
        for field in (
            "dependencies",
            "devDependencies",
            "optionalDependencies",
            "peerDependencies",
        ):
            values = payload.get(field, {})
            if isinstance(values, dict) and SCANNER_PACKAGES & set(values):
                found = ", ".join(sorted(SCANNER_PACKAGES & set(values)))
                raise CoordinationError(
                    f"project-local scanner dependencies are forbidden: {found}"
                )
        if deadline:
            remaining(deadline, "while validating scanner dependencies")
    return resolved
