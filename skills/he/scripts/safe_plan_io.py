"""Descriptor-relative no-follow PLAN I/O and product artifact binding."""

from __future__ import annotations

import contextlib
import ctypes
import hashlib
import os
import platform
import re
import secrets
import stat
import struct
import subprocess
from pathlib import Path


class SafePlanIOError(OSError):
    pass


def _flags(base: int) -> int:
    return base | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


@contextlib.contextmanager
def parent_fd(repo: Path, relative: Path, *, create: bool = False):
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise SafePlanIOError("invalid descriptor-relative PLAN path")
    descriptor = os.open(repo, _flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)))
    try:
        for part in relative.parts[:-1]:
            try:
                child = os.open(
                    part, _flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)),
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=descriptor)
                child = os.open(
                    part, _flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)),
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = child
        yield descriptor, relative.name
    finally:
        os.close(descriptor)


def _read_identity_at(
    directory: int, name: str
) -> tuple[bytes, int, tuple[int, int]]:
    descriptor = os.open(name, _flags(os.O_RDONLY), dir_fd=directory)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SafePlanIOError("PLAN/archive must be a regular file")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return (
            b"".join(chunks), stat.S_IMODE(metadata.st_mode),
            (metadata.st_dev, metadata.st_ino),
        )
    finally:
        os.close(descriptor)


def _read_at(directory: int, name: str) -> tuple[bytes, int]:
    data, mode, _ = _read_identity_at(directory, name)
    return data, mode


def read_snapshot(repo: Path, relative: Path) -> tuple[bytes, int]:
    with parent_fd(repo, relative) as (directory, name):
        return _read_at(directory, name)


def _write_temp(directory: int, data: bytes, mode: int) -> str:
    name = f".hard-eng-{secrets.token_hex(12)}"
    descriptor = os.open(
        name, _flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), mode, dir_fd=directory,
    )
    try:
        try:
            os.fchmod(descriptor, mode)
            view = memoryview(data)
            while view:
                written = os.write(descriptor, view)
                if written <= 0:
                    raise SafePlanIOError("zero-byte PLAN write")
                view = view[written:]
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        try:
            os.unlink(name, dir_fd=directory)
        except FileNotFoundError:
            pass
        raise
    return name


def _exchange(directory: int, left: str, right: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    encoded_left = os.fsencode(left)
    encoded_right = os.fsencode(right)
    system = platform.system()
    if system == "Darwin" and hasattr(libc, "renameatx_np"):
        result = libc.renameatx_np(
            directory, encoded_left, directory, encoded_right, 0x00000002
        )
    elif system == "Linux" and hasattr(libc, "renameat2"):
        result = libc.renameat2(
            directory, encoded_left, directory, encoded_right, 0x00000002
        )
    else:
        raise SafePlanIOError("atomic PLAN exchange is unsupported on this platform")
    if result != 0:
        error = ctypes.get_errno()
        raise SafePlanIOError(error, os.strerror(error))


def _replace_at(
    directory: int, name: str, expected: bytes, expected_mode: int, replacement: bytes
) -> None:
    current, mode = _read_at(directory, name)
    if current != expected or mode != expected_mode:
        raise SafePlanIOError("PLAN byte or mode preimage changed")
    temporary = _write_temp(directory, replacement, expected_mode)
    preserve_temporary = False
    try:
        _exchange(directory, temporary, name)
        preserve_temporary = True
        exchanged, exchanged_mode = _read_at(directory, temporary)
        if exchanged != expected or exchanged_mode != expected_mode:
            try:
                _exchange(directory, temporary, name)
            except BaseException as rollback_error:
                os.fsync(directory)
                raise SafePlanIOError(
                    "PLAN preimage changed and atomic rollback failed; recover "
                    f"concurrent PLAN bytes from sibling {temporary}"
                ) from rollback_error
            preserve_temporary = False
            raise SafePlanIOError("PLAN byte or mode preimage changed before exchange")
        os.unlink(temporary, dir_fd=directory)
        preserve_temporary = False
        os.fsync(directory)
    except BaseException:
        if not preserve_temporary:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
        raise


def replace_if_unchanged(
    repo: Path, relative: Path, expected: bytes, expected_mode: int, replacement: bytes
) -> None:
    with parent_fd(repo, relative) as (directory, name):
        _replace_at(directory, name, expected, expected_mode, replacement)


def create_new(repo: Path, relative: Path, data: bytes, mode: int) -> None:
    with parent_fd(repo, relative, create=True) as (directory, name):
        temporary = _write_temp(directory, data, mode)
        try:
            os.link(
                temporary, name, src_dir_fd=directory, dst_dir_fd=directory,
                follow_symlinks=False,
            )
            os.unlink(temporary, dir_fd=directory)
            os.fsync(directory)
        except BaseException:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
            raise


def archive_then_replace(
    repo: Path, relative: Path, expected: bytes, expected_mode: int,
    archive_name: str, replacement: bytes,
) -> None:
    with parent_fd(repo, relative) as (directory, name):
        current, mode = _read_at(directory, name)
        if current != expected or mode != expected_mode:
            raise SafePlanIOError("PLAN byte or mode preimage changed before archive")
        created_archive = False
        archive_identity: tuple[int, int] | None = None
        temporary: str | None = None
        try:
            archived, archive_mode, archive_identity = _read_identity_at(
                directory, archive_name
            )
        except FileNotFoundError:
            temporary = _write_temp(directory, expected, expected_mode)
            try:
                temporary_metadata = os.stat(
                    temporary, dir_fd=directory, follow_symlinks=False
                )
                archive_identity = (
                    temporary_metadata.st_dev, temporary_metadata.st_ino
                )
                os.link(
                    temporary, archive_name, src_dir_fd=directory, dst_dir_fd=directory,
                    follow_symlinks=False,
                )
                os.fsync(directory)
                created_archive = True
            except BaseException:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
                raise
        else:
            if archived != expected or archive_mode != expected_mode:
                raise SafePlanIOError("existing migration archive does not match source")
            temporary = _write_temp(directory, expected, expected_mode)
        try:
            _replace_at(directory, name, expected, expected_mode, replacement)
        except BaseException as plan_error:
            concurrent_recovery: str | None = None
            try:
                if created_archive and archive_identity is not None:
                    recovery = (
                        f".hard-eng-archive-recovery-{secrets.token_hex(12)}"
                    )
                    try:
                        os.rename(
                            archive_name, recovery,
                            src_dir_fd=directory, dst_dir_fd=directory,
                        )
                    except FileNotFoundError:
                        pass
                    else:
                        metadata = os.stat(
                            recovery, dir_fd=directory, follow_symlinks=False
                        )
                        if (metadata.st_dev, metadata.st_ino) == archive_identity:
                            os.unlink(recovery, dir_fd=directory)
                            os.fsync(directory)
                        else:
                            os.fsync(directory)
                            concurrent_recovery = recovery
            finally:
                try:
                    if temporary is not None:
                        os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass
            if concurrent_recovery is not None:
                raise SafePlanIOError(
                    "concurrent migration archive preserved at sibling "
                    f"{concurrent_recovery}"
                ) from plan_error
            raise
        assert archive_identity is not None and temporary is not None
        try:
            archived, archive_mode, identity = _read_identity_at(
                directory, archive_name
            )
        except (FileNotFoundError, SafePlanIOError):
            archived, archive_mode, identity = b"", -1, (-1, -1)
        if (
            identity == archive_identity
            and archived == expected
            and archive_mode == expected_mode
        ):
            os.unlink(temporary, dir_fd=directory)
            os.fsync(directory)
            return
        recovery = f".hard-eng-legacy-recovery-{secrets.token_hex(12)}"
        temporary_data, temporary_mode = _read_at(directory, temporary)
        if temporary_data != expected or temporary_mode != expected_mode:
            os.unlink(temporary, dir_fd=directory)
            temporary = _write_temp(directory, expected, expected_mode)
        os.rename(
            temporary, recovery, src_dir_fd=directory, dst_dir_fd=directory,
        )
        os.fsync(directory)
        try:
            _replace_at(
                directory, name, replacement, expected_mode, expected
            )
        except BaseException as rollback_error:
            raise SafePlanIOError(
                "migration archive changed after creation; legacy source preserved "
                f"at sibling {recovery}; migrated PLAN rollback failed"
            ) from rollback_error
        raise SafePlanIOError(
            "migration archive changed after creation; legacy source preserved "
            f"at sibling {recovery}; PLAN restored"
        )


def _frame(digest, value: bytes) -> None:
    digest.update(struct.pack(">Q", len(value)))
    digest.update(value)


def _excluded(relative: Path) -> bool:
    return (
        len(relative.parts) == 3 and relative.parts[0] == "features"
        and (
            relative.name == "PLAN.md"
            or relative.name.startswith("PLAN.legacy-v4.")
        )
    )


def _git_blob_id(
    repo: Path, relative: Path | None, *, descriptor: int | None = None,
    data: bytes | None = None,
) -> bytes:
    command = ["git", "-C", str(repo), "hash-object"]
    if relative is not None:
        command.append(f"--path={relative}")
    command.append("--stdin")
    try:
        if descriptor is not None:
            result = subprocess.run(
                command, stdin=descriptor, capture_output=True, timeout=30,
            )
        else:
            result = subprocess.run(
                command, input=data or b"", capture_output=True, timeout=30,
            )
    except subprocess.SubprocessError as error:
        raise SafePlanIOError("cannot compute bounded Git blob identity") from error
    output = result.stdout.strip()
    if result.returncode != 0 or not re.fullmatch(b"[0-9a-f]{40}|[0-9a-f]{64}", output):
        raise SafePlanIOError(
            "cannot compute Git blob identity: "
            + result.stderr.decode(errors="replace")[:1000]
        )
    return output


def repository_artifact(repo: Path) -> str:
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-c", "-o", "--exclude-standard", "-z"],
        check=True, capture_output=True, timeout=30,
    ).stdout
    staged = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--stage", "-z"],
        check=True, capture_output=True, timeout=30,
    ).stdout
    git_entries = {}
    for row in filter(None, staged.split(b"\0")):
        metadata, encoded_path = row.split(b"\t", 1)
        mode, object_id, _ = metadata.split(b" ", 2)
        git_entries[Path(os.fsdecode(encoded_path))] = (mode, object_id)
    digest = hashlib.sha256()
    for encoded in sorted(filter(None, listed.split(b"\0"))):
        relative = Path(os.fsdecode(encoded))
        if _excluded(relative):
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
            head = subprocess.run(
                ["git", "-C", str(repo / relative), "rev-parse", "HEAD"],
                check=False, capture_output=True, timeout=10,
            )
            dirty = subprocess.run(
                ["git", "-C", str(repo / relative), "status", "--porcelain", "-z"],
                check=False, capture_output=True, timeout=10,
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
            try:
                with parent_fd(repo, relative) as (directory, name):
                    metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
                    if stat.S_ISLNK(metadata.st_mode):
                        kind, work_mode = b"symlink", b"120000"
                        content = _git_blob_id(
                            repo, None,
                            data=os.fsencode(os.readlink(name, dir_fd=directory)),
                        )
                    elif stat.S_ISREG(metadata.st_mode):
                        kind = b"file"
                        work_mode = (
                            b"100755" if metadata.st_mode & 0o111 else b"100644"
                        )
                        descriptor = os.open(name, _flags(os.O_RDONLY), dir_fd=directory)
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
                        kind, content = b"other", b""
            except FileNotFoundError:
                continue
        for value in (encoded, work_mode, kind, content):
            _frame(digest, value)
    return "sha256:" + digest.hexdigest()


def committed_head_artifact(repo: Path, revision: str = "HEAD") -> str:
    tree = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", revision],
        check=True, capture_output=True, timeout=30,
    ).stdout
    digest = hashlib.sha256()
    for row in filter(None, tree.split(b"\0")):
        metadata, encoded = row.split(b"\t", 1)
        mode, object_type, object_id = metadata.split(b" ", 2)
        relative = Path(os.fsdecode(encoded))
        if _excluded(relative):
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
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    committed = committed_head_artifact(repo, head)
    if committed != expected:
        raise SafePlanIOError("committed HEAD artifact differs from green")
    tracked = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", "-z",
         "--ignore-submodules=none", head, "--"],
        check=True, capture_output=True, timeout=30,
    ).stdout
    untracked = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard", "-z"],
        check=True, capture_output=True, timeout=30,
    ).stdout
    dirty = [
        relative
        for encoded in (*filter(None, tracked.split(b"\0")), *filter(None, untracked.split(b"\0")))
        if not _excluded(relative := Path(os.fsdecode(encoded)))
    ]
    if dirty:
        raise SafePlanIOError(
            "delivered HEAD differs from non-lifecycle worktree: "
            + ",".join(map(str, dirty))
        )
    if repository_artifact(repo) != expected:
        raise SafePlanIOError("delivered worktree changed during assertion")
    current_head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD^{commit}"],
        check=True, capture_output=True, text=True, timeout=30,
    ).stdout.strip()
    if current_head != head:
        raise SafePlanIOError("committed HEAD changed during assertion")
    return actual
