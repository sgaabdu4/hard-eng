#!/usr/bin/env python3
"""Crash-resumable transfer for one Hard Eng PLAN bundle."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator

from plan_contract import PlanStateError
from safe_repo_io import (
    atomic_write as repo_write,
    rmdir as repo_rmdir,
    snapshot as repo_snapshot,
    snapshot_optional as repo_snapshot_optional,
    unlink as repo_unlink,
)


State = dict[str, str]
GitIdentity = Callable[[Path], tuple[Path, str, str]]
MANIFEST_NAME = "hard-eng-plan-transfer.json"
MANIFEST_KEYS = {
    "version", "source_root", "source_branch", "source_head", "destination_root",
    "destination_branch", "destination_head", "plan_relative", "source_token",
    "candidate_token", "candidate_sha256", "updated_at_utc", "includes",
}


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def git_location(root: Path, flag: str) -> Path:
    return Path(git(root, "rev-parse", "--path-format=absolute", flag)).resolve()


def path_status(root: Path, relative: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all", "--", str(relative)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def exact_path(root: Path, raw: str) -> tuple[Path, Path]:
    relative = Path(raw)
    invalid_part = not relative.parts or any(part in {"", ".", "..", ".git"} for part in relative.parts)
    if relative.is_absolute() or invalid_part:
        raise PlanStateError(f"invalid include path: {raw}")
    if any(character in raw for character in "*?["):
        raise PlanStateError(f"include path must be exact: {raw}")
    candidate = root
    for part in relative.parts:
        candidate /= part
        if candidate.is_symlink():
            raise PlanStateError(f"symlink include path forbidden: {raw}")
    try:
        candidate.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise PlanStateError(f"include path escapes repository: {raw}") from exc
    return relative, candidate


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary_path.unlink(missing_ok=True)


def manifest_path(common_dir: Path) -> Path:
    return common_dir / MANIFEST_NAME


def pending_manifest(common_dir: Path) -> bool:
    return os.path.lexists(manifest_path(common_dir))


@contextmanager
def plan_writer_lock(common_dir: Path) -> Iterator[None]:
    with repository_lock(common_dir):
        if pending_manifest(common_dir):
            raise PlanStateError("pending PLAN transfer requires exact transfer resume")
        yield


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_manifest(common_dir: Path) -> dict[str, Any] | None:
    path = manifest_path(common_dir)
    if not os.path.lexists(path):
        return None
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise PlanStateError("transfer manifest must be an owner-only regular file")
    raw = path.read_bytes()
    if len(raw) > 65536:
        raise PlanStateError("transfer manifest is oversized")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlanStateError("transfer manifest is invalid") from exc
    if not isinstance(value, dict) or set(value) != MANIFEST_KEYS or value.get("version") != 1:
        raise PlanStateError("transfer manifest schema is invalid")
    string_keys = MANIFEST_KEYS - {"version", "includes"}
    if any(not isinstance(value.get(key), str) or not value[key] for key in string_keys):
        raise PlanStateError("transfer manifest scalar schema is invalid")
    if any(
        not re.fullmatch(r"[0-9a-f]{64}", value[key])
        for key in ("source_token", "candidate_token", "candidate_sha256")
    ) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value["updated_at_utc"]):
        raise PlanStateError("transfer manifest identity schema is invalid")
    includes = value.get("includes")
    if not isinstance(includes, list) or any(
        not isinstance(item, dict)
        or set(item) != {"path", "sha256", "mode"}
        or not isinstance(item["path"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", str(item["sha256"]))
        or type(item["mode"]) is not int
        for item in includes
    ):
        raise PlanStateError("transfer manifest include schema is invalid")
    return value


def write_manifest(common_dir: Path, value: dict[str, Any]) -> None:
    atomic_write(
        manifest_path(common_dir),
        (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"),
        0o600,
    )


def remove_manifest(common_dir: Path) -> None:
    path = manifest_path(common_dir)
    path.unlink()
    directory = os.open(common_dir, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


@contextmanager
def repository_lock(common_dir: Path) -> Iterator[None]:
    lock_path = common_dir / "hard-eng-plan-transfer.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        os.chmod(lock_path, 0o600)
        with os.fdopen(descriptor, "a+b", closefd=True) as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


@contextmanager
def repository_transaction(common_dir: Path, rollback: Callable[[], list[str]]) -> Iterator[None]:
    with repository_lock(common_dir):
        try:
            yield
        except BaseException as exc:
            errors = rollback()
            if errors:
                raise PlanStateError(f"{exc}; rollback failed: " + " | ".join(errors)) from exc
            if not isinstance(exc, Exception):
                raise PlanStateError(f"transfer interrupted: {type(exc).__name__}") from exc
            raise


def transfer_plan(
    repo_arg: str,
    destination_arg: str,
    plan_arg: str,
    expected_token: str,
    includes: list[str],
    *,
    git_identity: GitIdentity,
    canonical_plan: Callable[[Path, Path], Path],
    checkpoint_token: Callable[[str], str],
    document_token: Callable[[str], str],
    validate_document: Callable[[Path, str], State],
    freshness_errors: Callable[[State, Path, str, str, Path], list[str]],
    replace_state: Callable[[str, dict[str, str]], str],
    emit: Callable[[str, str], None],
    write: Callable[[Path, bytes, int], None] | None = None,
) -> int:
    destination_originals: dict[Path, tuple[bytes, int] | None] = {}
    created_directories: list[Path] = []
    source_original: tuple[bytes, int] | None = None
    source_relative: Path | None = None
    source_plan: Path | None = None
    destination_plan: Path | None = None
    candidate = ""
    updated = ""
    included: dict[Path, tuple[Path, bytes, int]] = {}
    common_dir: Path | None = None
    normal_transfer = False
    resume = False
    source_written = False

    def rollback() -> list[str]:
        errors: list[str] = []
        if source_written and source_root is not None and source_relative is not None and source_original is not None:
            try:
                repo_write(source_root, source_relative, *source_original)
            except (OSError, PlanStateError) as error:
                errors.append(f"source:{error}")
        for relative, original in reversed(tuple(destination_originals.items())):
            try:
                if original is None:
                    repo_unlink(destination_root, relative)
                else:
                    repo_write(destination_root, relative, *original)
            except (OSError, PlanStateError) as error:
                errors.append(f"{relative}:{error}")
        for directory in reversed(created_directories):
            try:
                repo_rmdir(destination_root, directory)
            except (OSError, PlanStateError):
                pass
        if not errors and normal_transfer and common_dir is not None and pending_manifest(common_dir):
            try:
                remove_manifest(common_dir)
            except OSError as error:
                errors.append(f"manifest:{error}")
        return errors

    try:
        source_root, source_branch, source_head = git_identity(Path(repo_arg).expanduser().resolve())
        destination_root, destination_branch, destination_head = git_identity(
            Path(destination_arg).expanduser().resolve()
        )
        if source_root == destination_root:
            raise PlanStateError("source and destination worktrees must differ")
        common_dir = git_location(source_root, "--git-common-dir")
        if common_dir != git_location(destination_root, "--git-common-dir"):
            raise PlanStateError("source and destination must share one Git common directory")
        if git_location(destination_root, "--git-dir") == common_dir:
            raise PlanStateError("destination must be a linked worktree")
        if source_head != destination_head:
            raise PlanStateError("source and destination HEAD must match")

        with repository_transaction(common_dir, rollback):
            source_plan = canonical_plan(Path(plan_arg).expanduser(), source_root)
            source_relative = source_plan.relative_to(source_root)
            source_original = repo_snapshot(source_root, source_relative, "source PLAN")
            source_text = source_original[0].decode("utf-8")
            if not re.fullmatch(r"[0-9a-f]{64}", expected_token):
                raise PlanStateError("invalid checkpoint token")
            source_state = validate_document(source_plan, source_text)
            recorded_root = Path(source_state["repository_root"]).expanduser().resolve()
            normal_transfer = recorded_root == source_root
            resume = (
                recorded_root == destination_root
                and source_state["branch"] == destination_branch
                and source_state["head_sha"] == destination_head
            )
            if normal_transfer:
                stale = freshness_errors(source_state, source_root, source_branch, source_head, source_plan)
                if stale:
                    raise PlanStateError("stale source state fields: " + ",".join(stale))
            elif not resume:
                raise PlanStateError("source PLAN is owned by another worktree")

            manifest = load_manifest(common_dir)
            current_token = checkpoint_token(source_text)
            if manifest is None:
                if not normal_transfer:
                    raise PlanStateError("pending transfer manifest is missing")
                if current_token != expected_token:
                    raise PlanStateError("stale checkpoint token; inspect again")
            else:
                required_token = manifest["source_token"] if normal_transfer else manifest["candidate_token"]
                if current_token != required_token or expected_token != required_token:
                    raise PlanStateError("stale checkpoint token for pending transfer")

            plan_relative = source_plan.relative_to(source_root)
            destination_plan = exact_path(destination_root, str(plan_relative))[1]
            updated = (
                str(manifest["updated_at_utc"])
                if manifest is not None
                else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            )
            candidate = (
                replace_state(
                    source_text,
                    {
                        "repository_root": str(destination_root),
                        "branch": destination_branch,
                        "head_sha": destination_head,
                        "updated_at_utc": updated,
                    },
                )
                if normal_transfer
                else source_text
            )
            updated = validate_document(destination_plan, candidate)["updated_at_utc"]
            candidate_bytes = candidate.encode("utf-8")
            if freshness_errors(
                validate_document(destination_plan, candidate),
                destination_root,
                destination_branch,
                destination_head,
                destination_plan,
            ):
                raise PlanStateError("transferred state would be stale")

            for raw in includes:
                relative, source_path = exact_path(source_root, raw)
                if relative == plan_relative:
                    raise PlanStateError("PLAN is transferred automatically; do not include it")
                if relative in included:
                    raise PlanStateError(f"duplicate include path: {relative}")
                if not path_status(source_root, relative):
                    raise PlanStateError(f"include path is not changed at source: {relative}")
                content, mode = repo_snapshot(source_root, relative, f"include {relative}")
                destination_path = exact_path(destination_root, str(relative))[1]
                status = path_status(destination_root, relative)
                applied = repo_snapshot_optional(destination_root, relative, f"destination {relative}")
                if status and not (manifest is not None and applied == (content, mode)):
                    raise PlanStateError(f"destination path is dirty or colliding: {relative}")
                included[relative] = (destination_path, content, mode)

            destination_plan_status = path_status(destination_root, plan_relative)
            plan_expected = (candidate_bytes, source_original[1])
            destination_plan_original = repo_snapshot_optional(
                destination_root, plan_relative, "destination PLAN"
            )
            if destination_plan_status and not (manifest is not None and destination_plan_original == plan_expected):
                raise PlanStateError("destination PLAN path is dirty or colliding")

            source_document_token = document_token(source_text)
            current_source = repo_snapshot(source_root, source_relative, "source PLAN")[0].decode("utf-8")
            if document_token(current_source) != source_document_token:
                raise PlanStateError("source PLAN changed during transfer; inspect again")
            if git_identity(source_root)[1:] != (source_branch, source_head):
                raise PlanStateError("source Git identity changed during transfer")
            if git_identity(destination_root)[1:] != (destination_branch, destination_head):
                raise PlanStateError("destination Git identity changed during transfer")
            for relative, (destination_path, content, mode) in included.items():
                if repo_snapshot(source_root, relative, f"include {relative}") != (content, mode):
                    raise PlanStateError(f"source include changed during transfer: {relative}")
                destination_originals[relative] = repo_snapshot_optional(
                    destination_root, relative, f"destination {relative}"
                )
            destination_originals[plan_relative] = destination_plan_original

            expected_manifest = {
                "version": 1,
                "source_root": str(source_root),
                "source_branch": source_branch,
                "source_head": source_head,
                "destination_root": str(destination_root),
                "destination_branch": destination_branch,
                "destination_head": destination_head,
                "plan_relative": plan_relative.as_posix(),
                "source_token": current_token if normal_transfer else manifest["source_token"],
                "candidate_token": checkpoint_token(candidate),
                "candidate_sha256": content_sha256(candidate_bytes),
                "updated_at_utc": updated,
                "includes": [
                    {"path": relative.as_posix(), "sha256": content_sha256(content), "mode": mode}
                    for relative, (_, content, mode) in included.items()
                ],
            }
            if manifest is not None and manifest != expected_manifest:
                raise PlanStateError("pending transfer arguments or bundle differ from manifest")
            if manifest is None:
                write_manifest(common_dir, expected_manifest)
                manifest = expected_manifest

            if normal_transfer:
                source_written = True
                repo_write(source_root, source_relative, candidate_bytes, source_original[1])
                if write is not None:
                    write(source_plan, candidate_bytes, source_original[1])
            for relative, (destination_path, content, mode) in included.items():
                if repo_snapshot_optional(destination_root, relative, f"destination {relative}") != (content, mode):
                    repo_write(destination_root, relative, content, mode, created=created_directories)
                    if write is not None:
                        write(destination_path, content, mode)
            if repo_snapshot_optional(destination_root, plan_relative, "destination PLAN") != plan_expected:
                repo_write(destination_root, plan_relative, *plan_expected, created=created_directories)
                if write is not None:
                    write(destination_plan, *plan_expected)

            destination_result = validate_document(
                destination_plan,
                repo_snapshot(destination_root, plan_relative, "destination PLAN")[0].decode("utf-8"),
            )
            if freshness_errors(
                destination_result, destination_root, destination_branch, destination_head, destination_plan
            ):
                raise PlanStateError("destination PLAN failed post-transfer freshness")
            source_result = validate_document(
                source_plan, repo_snapshot(source_root, source_relative, "source PLAN")[0].decode("utf-8")
            )
            if not freshness_errors(source_result, source_root, source_branch, source_head, source_plan):
                raise PlanStateError("source PLAN remained a fresh writer")
            remove_manifest(common_dir)
    except (OSError, UnicodeError, subprocess.CalledProcessError, PlanStateError) as exc:
        emit("result", "invalid")
        emit("error", str(exc))
        return 4

    emit("result", "transferred")
    emit("source_plan", str(source_plan))
    emit("plan", str(destination_plan))
    emit("repository_root", str(destination_root))
    emit("branch", destination_branch)
    emit("head_sha", destination_head)
    emit("updated_at_utc", updated)
    emit("checkpoint_token", checkpoint_token(candidate))
    emit("included_paths", ",".join(str(path) for path in included) or "none")
    emit("resumed", "no" if normal_transfer else "yes")
    return 0
