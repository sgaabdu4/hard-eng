#!/usr/bin/env python3
"""Atomically stage one exact Hard Eng candidate patch after same-byte re-admission."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import audit
from audit_candidate import (
    CandidateError, canonical_worktree_patch, load_patch, patch_digest, patch_paths,
)


class ApplyError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FilePreimage:
    existed: bool
    content: bytes = b""
    mode: int = 0


@dataclass(frozen=True)
class RepositoryPreimage:
    index_path: Path
    index_content: bytes
    index_mode: int
    files: dict[str, FilePreimage]
    absent_directories: tuple[Path, ...]
    snapshot_id: str


def git_common_dir(root: Path) -> Path:
    raw = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--git-common-dir"], text=True
    ).strip()
    path = Path(raw)
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def git_index_path(root: Path) -> Path:
    raw = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--git-path", "index"], text=True
    ).strip()
    path = Path(raw)
    return (root / path).resolve() if not path.is_absolute() else path.resolve()


def capture_preimage(root: Path, paths: tuple[str, ...]) -> RepositoryPreimage:
    index_path = git_index_path(root)
    index_stat = index_path.stat()
    if not stat.S_ISREG(index_stat.st_mode):
        raise ApplyError("APPLY_CONFLICT", "Git index is not a regular file")
    files: dict[str, FilePreimage] = {}
    absent_directories: set[Path] = set()
    for relative in paths:
        target = root / relative
        if os.path.lexists(target):
            metadata = target.lstat()
            if not stat.S_ISREG(metadata.st_mode):
                raise ApplyError("APPLY_CONFLICT", "candidate target is not a regular file")
            files[relative] = FilePreimage(True, target.read_bytes(), stat.S_IMODE(metadata.st_mode))
        else:
            files[relative] = FilePreimage(False)
            parent = target.parent
            while parent != root and not parent.exists():
                absent_directories.add(parent)
                parent = parent.parent
    return RepositoryPreimage(
        index_path=index_path,
        index_content=index_path.read_bytes(),
        index_mode=stat.S_IMODE(index_stat.st_mode),
        files=files,
        absent_directories=tuple(sorted(absent_directories, key=lambda path: len(path.parts), reverse=True)),
        snapshot_id=audit.snapshot_id(root),
    )


def _replace_regular(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.restore-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        Path(temporary).unlink(missing_ok=True)
        raise


def restore_preimage(root: Path, preimage: RepositoryPreimage) -> None:
    _replace_regular(preimage.index_path, preimage.index_content, preimage.index_mode)
    for relative, saved in preimage.files.items():
        target = root / relative
        if saved.existed:
            _replace_regular(target, saved.content, saved.mode)
        elif os.path.lexists(target):
            if target.is_dir() and not target.is_symlink():
                raise ApplyError("ROLLBACK_FAILED", "rollback target became a directory")
            target.unlink()
    for directory in preimage.absent_directories:
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError:
            if directory.exists() and any(directory.iterdir()):
                raise ApplyError("ROLLBACK_FAILED", "rollback directory contains external state")
    if audit.snapshot_id(root) != preimage.snapshot_id:
        raise ApplyError("ROLLBACK_FAILED", "rollback snapshot verification failed")


def apply_bytes(root: Path, data: bytes) -> None:
    for args in (("apply", "--check", "--index", "-"), ("apply", "--index", "-")):
        result = subprocess.run(
            ["git", "-C", str(root), *args], input=data, capture_output=True, check=False
        )
        if result.returncode != 0:
            raise ApplyError("APPLY_CONFLICT", "Git rejected candidate apply")


def apply_candidate(
    *, root: Path, plan: Path, patch: Path,
    unit: str,
    expect_base: str, expect_patch: str, expect_candidate: str,
) -> dict[str, object]:
    root = audit.repository_root(root.expanduser().resolve())
    resolved_plan = audit.resolve_plan(root, plan.expanduser())
    data = load_patch(patch)
    if patch_digest(data) != expect_patch:
        raise ApplyError("INVALID_PATCH", "candidate patch digest mismatch")
    if audit.snapshot_id(root) != expect_base:
        raise ApplyError("STALE_SNAPSHOT", "delivery base snapshot mismatch")
    lock_path = git_common_dir(root) / "hard-eng-candidate-apply.lock"
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ApplyError("LOCKED", "candidate apply lock is held") from exc
        if audit.snapshot_id(root) != expect_base:
            raise ApplyError("STALE_SNAPSHOT", "delivery changed under apply lock")
        admitted = audit.candidate_admission_report(root, resolved_plan, data, unit)
        if admitted["result"] != "pass":
            code = admitted.get("error", {}).get("code", "INVALID_PATCH")
            raise ApplyError(str(code), "candidate re-admission failed")
        if admitted["baseSnapshotId"] != expect_base:
            raise ApplyError("STALE_SNAPSHOT", "re-admitted base mismatch")
        if admitted["candidateDigest"] != expect_patch:
            raise ApplyError("INVALID_PATCH", "re-admitted digest mismatch")
        if admitted["candidateSnapshotId"] != expect_candidate:
            raise ApplyError("INVALID_PATCH", "re-admitted candidate mismatch")
        if audit.snapshot_id(root) != expect_base:
            raise ApplyError("STALE_SNAPSHOT", "delivery changed before apply")
        plan_relative = resolved_plan.relative_to(root).as_posix()
        active_paths = patch_paths(data, plan_relative=plan_relative, sensitive=audit.sensitive_path)
        preimage = capture_preimage(root, active_paths)
        if preimage.snapshot_id != expect_base or audit.snapshot_id(root) != expect_base:
            raise ApplyError("STALE_SNAPSHOT", "delivery changed before preimage capture completed")
        try:
            if admitted["candidateState"] == "preserved-wip":
                if canonical_worktree_patch(root, active_paths) != data:
                    raise ApplyError("INVALID_PATCH", "preserved WIP bytes changed after admission")
                result = subprocess.run(
                    ["git", "-C", str(root), "add", "--", *active_paths],
                    capture_output=True, check=False,
                )
                if result.returncode != 0:
                    raise ApplyError("APPLY_CONFLICT", "Git rejected preserved WIP staging")
            else:
                apply_bytes(root, data)
            applied = audit.snapshot_id(root)
            if applied != expect_candidate:
                raise ApplyError("APPLY_CONFLICT", "applied snapshot differs from admitted candidate")
        except BaseException as error:
            failed_snapshot = audit.snapshot_id(root)
            if failed_snapshot == preimage.snapshot_id:
                raise error
            if failed_snapshot != expect_candidate:
                raise ApplyError(
                    "ROLLBACK_FAILED", "repository changed concurrently during candidate apply"
                ) from error
            try:
                restore_preimage(root, preimage)
            except BaseException as restore_error:
                raise ApplyError("ROLLBACK_FAILED", "exact preimage restoration failed") from restore_error
            raise error
        return {
            "result": "applied", "unitId": admitted["unitId"],
            "approvedPlanDigest": admitted["approvedPlanDigest"],
            "completedSlices": admitted["completedSlices"],
            "accumulatedPathCount": admitted["accumulatedPathCount"],
            "accumulatedStateDigest": admitted["accumulatedStateDigest"],
            "candidateState": admitted["candidateState"],
            "preservedWipPathCount": admitted["preservedWipPathCount"],
            "baseSnapshotId": expect_base,
            "candidateDigest": expect_patch, "candidateSnapshotId": expect_candidate,
            "appliedSnapshotId": applied, "changedPathCount": admitted["changedPathCount"],
            "reviewShardCount": admitted["reviewShardCount"],
        }
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--patch", required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument("--expect-base", required=True)
    parser.add_argument("--expect-patch", required=True)
    parser.add_argument("--expect-candidate", required=True)
    args = parser.parse_args()
    try:
        receipt = apply_candidate(
            root=Path(args.repo), plan=Path(args.plan), patch=Path(args.patch),
            unit=args.unit,
            expect_base=args.expect_base, expect_patch=args.expect_patch,
            expect_candidate=args.expect_candidate,
        )
    except ApplyError as exc:
        print(json.dumps({"result": "fail", "error": {"code": exc.code}}, separators=(",", ":")))
        return 1
    except (audit.AuditError, CandidateError, OSError, subprocess.SubprocessError):
        print(json.dumps({"result": "fail", "error": {"code": "INVALID_PATCH"}}, separators=(",", ":")))
        return 1
    print(json.dumps(receipt, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
