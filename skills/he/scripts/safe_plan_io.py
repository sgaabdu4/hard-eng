"""Descriptor-relative no-follow PLAN I/O and product artifact binding."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import struct
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GIT_ENV_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from bounded_run import run_captured
from git_env import git_env

REPOSITORY_ROOT = SCRIPT_DIR.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup import safe_file


SafePlanIOError = safe_file.SafeFileError
_flags = safe_file._flags
parent_fd = safe_file.parent_fd
_read_at = safe_file._read_at
_write_temp = safe_file._write_temp
_exchange = safe_file._exchange


def _git(
    repo: Path,
    *arguments: str,
    timeout: float = 30,
    check: bool = True,
    input_data: bytes | None = None,
    stdin_fd: int | None = None,
):
    try:
        result = run_captured(
            ["git", "-C", str(repo), *arguments],
            timeout,
            grace=1,
            env=git_env(),
            input_data=input_data,
            stdin_fd=stdin_fd,
        )
    except OSError as error:
        raise SafePlanIOError(f"cannot run bounded Git {arguments[0]}") from error
    if check and result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()[:1000]
        raise SafePlanIOError(detail or f"bounded Git {arguments[0]} failed")
    return result


def read_snapshot(repo: Path, relative: Path) -> tuple[bytes, int]:
    return safe_file.read_snapshot(repo, relative)


def replace_if_unchanged(
    repo: Path, relative: Path, expected: bytes, expected_mode: int, replacement: bytes
) -> None:
    safe_file.replace_if_unchanged(
        repo,
        relative,
        expected,
        expected_mode,
        replacement,
        read_at=_read_at,
        write_temp=_write_temp,
        exchange=_exchange,
    )


def create_new(repo: Path, relative: Path, data: bytes, mode: int) -> None:
    safe_file.create_new(
        repo,
        relative,
        data,
        mode,
        read_at=_read_at,
        write_temp=_write_temp,
    )


def consume_if_unchanged(
    repo: Path, relative: Path, expected: bytes, expected_mode: int
) -> None:
    safe_file.consume_if_unchanged(repo, relative, expected, expected_mode)


def repo_root(value: str) -> Path:
    supplied = Path(value)
    if not supplied.exists() or not supplied.is_dir():
        raise SafePlanIOError("repository root must be an existing directory")
    resolved = supplied.resolve()
    result = _git(resolved, "rev-parse", "--show-toplevel", check=False, timeout=10)
    if (
        result.returncode != 0
        or Path(result.stdout.decode("utf-8", "replace").strip()).resolve() != resolved
    ):
        raise SafePlanIOError("repository root must be the Git worktree root")
    return resolved


def _frame(digest, value: bytes) -> None:
    digest.update(struct.pack(">Q", len(value)))
    digest.update(value)


def lifecycle_excluded(relative: Path) -> bool:
    parts = relative.parts
    if len(parts) == 3 and parts[0] == "features" and parts[2] == "PLAN.md":
        return True
    if len(parts) >= 4 and parts[0] == "features" and parts[2] == "receipts":
        return True
    return len(parts) == 3 and parts[:2] == (".agents", "learning") and parts[2].endswith(".json")


def _git_blob_id(
    repo: Path, relative: Path | None, *, descriptor: int | None = None,
    data: bytes | None = None,
) -> bytes:
    command = ["hash-object"]
    if relative is not None:
        command.append(f"--path={relative}")
    command.append("--stdin")
    result = _git(
        repo,
        *command,
        timeout=30,
        check=False,
        stdin_fd=descriptor,
        input_data=None if descriptor is not None else data or b"",
    )
    output = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(b"[0-9a-f]{40}|[0-9a-f]{64}", output):
        raise SafePlanIOError(
            "cannot compute Git blob identity: "
            + result.stderr.decode(errors="replace")[:1000]
        )
    return output


def repository_artifact(repo: Path) -> str:
    listed = _git(repo, "ls-files", "-c", "-o", "--exclude-standard", "-z").stdout
    modified = {
        Path(os.fsdecode(encoded))
        for encoded in filter(
            None,
            _git(repo, "ls-files", "--modified", "-z").stdout.split(b"\0"),
        )
    }
    hidden_from_worktree_scan = {
        Path(os.fsdecode(row[2:]))
        for row in filter(
            None,
            _git(repo, "ls-files", "--cached", "-v", "-z").stdout.split(b"\0"),
        )
        if not row.startswith(b"H ")
    }
    staged = _git(repo, "ls-files", "--stage", "-z").stdout
    git_entries: dict[Path, tuple[bytes, bytes]] = {}
    for row in filter(None, staged.split(b"\0")):
        metadata, encoded_path = row.split(b"\t", 1)
        mode, object_id, stage = metadata.split(b" ", 2)
        relative = Path(os.fsdecode(encoded_path))
        if stage != b"0" or relative in git_entries:
            raise SafePlanIOError(f"unmerged or duplicate index entry: {relative}")
        git_entries[relative] = (mode, object_id)
    digest = hashlib.sha256()
    for encoded in sorted(filter(None, listed.split(b"\0"))):
        relative = Path(os.fsdecode(encoded))
        if lifecycle_excluded(relative):
            continue
        mode, object_id = git_entries.get(relative, (b"untracked", b""))
        if mode == b"160000":
            try:
                with parent_fd(repo, relative) as (directory, name):
                    metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(metadata.st_mode):
                raise SafePlanIOError("gitlink working entry is not a directory")
            head = _git(repo / relative, "rev-parse", "HEAD", check=False, timeout=10)
            dirty = _git(
                repo / relative, "status", "--porcelain", "-z", check=False, timeout=10
            )
            if (
                head.returncode != 0 or dirty.returncode != 0
                or head.stdout.strip() != object_id or dirty.stdout
            ):
                raise SafePlanIOError(
                    f"gitlink must be initialized, clean, and match index: {relative}"
                )
            kind, work_mode, content = b"gitlink", b"160000", object_id
        else:
            reuse_index = bool(
                object_id
                and relative not in modified
                and relative not in hidden_from_worktree_scan
            )
            try:
                with parent_fd(repo, relative) as (directory, name):
                    metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if stat.S_ISLNK(metadata.st_mode):
                        kind, work_mode = b"symlink", b"120000"
                        content = (
                            object_id
                            if reuse_index
                            else _git_blob_id(
                                repo, None,
                                data=os.fsencode(os.readlink(name, dir_fd=directory)),
                            )
                        )
                    elif stat.S_ISREG(metadata.st_mode):
                        kind = b"file"
                        work_mode = (
                            b"100755" if metadata.st_mode & 0o111 else b"100644"
                        )
                        if reuse_index:
                            content = object_id
                        else:
                            descriptor = os.open(
                                name, _flags(os.O_RDONLY), dir_fd=directory
                            )
                            try:
                                opened = os.fstat(descriptor)
                                if not stat.S_ISREG(opened.st_mode):
                                    raise SafePlanIOError("artifact entry changed type")
                                content = _git_blob_id(
                                    repo, relative, descriptor=descriptor
                                )
                            finally:
                                os.close(descriptor)
                    else:
                        raise SafePlanIOError(
                            f"unsupported worktree entry type: {relative}"
                        )
            except FileNotFoundError:
                continue
        for value in (encoded, work_mode, kind, content):
            _frame(digest, value)
    return "sha256:" + digest.hexdigest()


def committed_head_artifact(repo: Path, revision: str = "HEAD") -> str:
    tree = _git(repo, "ls-tree", "-r", "-z", revision).stdout
    digest = hashlib.sha256()
    for row in filter(None, tree.split(b"\0")):
        metadata, encoded = row.split(b"\t", 1)
        mode, object_type, object_id = metadata.split(b" ", 2)
        relative = Path(os.fsdecode(encoded))
        if lifecycle_excluded(relative):
            continue
        if mode == b"160000":
            kind = b"gitlink"
        elif mode == b"120000":
            kind = b"symlink"
        elif object_type == b"blob" and mode in {b"100644", b"100755"}:
            kind = b"file"
        else:
            raise SafePlanIOError(f"unsupported committed entry: {relative}")
        for value in (encoded, mode, kind, object_id):
            _frame(digest, value)
    return "sha256:" + digest.hexdigest()


def delivered_head_artifact(repo: Path, expected: str) -> str:
    actual = repository_artifact(repo)
    if actual != expected:
        raise SafePlanIOError("delivered worktree artifact differs from green")
    head = _git(repo, "rev-parse", "--verify", "HEAD^{commit}").stdout.decode().strip()
    committed = committed_head_artifact(repo, head)
    if committed != expected:
        raise SafePlanIOError("committed HEAD artifact differs from green")
    tracked = _git(
        repo,
        "diff",
        "--name-only",
        "-z",
        "--ignore-submodules=none",
        head,
        "--",
    ).stdout
    untracked = _git(repo, "ls-files", "--others", "--exclude-standard", "-z").stdout
    dirty = [
        relative
        for encoded in (*filter(None, tracked.split(b"\0")), *filter(None, untracked.split(b"\0")))
        if not lifecycle_excluded(relative := Path(os.fsdecode(encoded)))
    ]
    if dirty:
        raise SafePlanIOError(
            "delivered HEAD differs from non-lifecycle worktree: "
            + ",".join(map(str, dirty))
        )
    if repository_artifact(repo) != expected:
        raise SafePlanIOError("delivered worktree changed during assertion")
    current_head = _git(
        repo, "rev-parse", "--verify", "HEAD^{commit}"
    ).stdout.decode().strip()
    if current_head != head:
        raise SafePlanIOError("committed HEAD changed during assertion")
    return actual
