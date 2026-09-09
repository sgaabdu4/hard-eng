"""Safe descriptor-relative file replacement for setup and lifecycle state.

The public operations in this module keep every path component under an
already-open directory descriptor.  They never follow a symlink while
opening a parent or the final file, and they publish a complete file only
after the temporary file and its containing directory are durable.
"""

from __future__ import annotations

import contextlib
import ctypes
import fcntl
import os
import platform
import secrets
import stat
from collections.abc import Callable, Iterator
from pathlib import Path


class SafeFileError(OSError):
    """A path or immutable file precondition failed."""


def _flags(base: int) -> int:
    return base | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)


def _validate_component(component: str) -> None:
    if component in {"", ".", ".."} or "/" in component or "\\" in component:
        raise SafeFileError("unsafe descriptor-relative path component")


def _validate_directory(descriptor: int) -> None:
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        raise SafeFileError("safe file ancestor must be a directory")
    mode = stat.S_IMODE(metadata.st_mode)
    owner_is_trusted = metadata.st_uid in {0, os.getuid()}
    sticky_system_directory = metadata.st_uid == 0 and bool(mode & stat.S_ISVTX)
    if not owner_is_trusted or ((mode & 0o022) and not sticky_system_directory):
        raise SafeFileError("safe file ancestor has unsafe owner or mode")


def _normalize_os_alias(path: Path) -> Path:
    """Map macOS's fixed /var and /tmp aliases before no-follow walking."""
    if not path.is_absolute() or len(path.parts) < 2:
        return path
    alias = Path(os.sep) / path.parts[1]
    if alias not in {Path("/var"), Path("/tmp")} or not alias.is_symlink():
        return path
    target = alias.resolve(strict=True)
    expected = Path("/private") / alias.name
    if target != expected:
        raise SafeFileError("unexpected system path alias")
    return expected.joinpath(*path.parts[2:])


def _path_parts(path: Path) -> tuple[int, tuple[str, ...]]:
    """Open a stable root and return the unconsumed path components."""
    path = _normalize_os_alias(path)
    if not path.parts:
        raise SafeFileError("empty safe file path")
    if path.is_absolute():
        descriptor = os.open(os.sep, _flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)))
        components = tuple(path.parts[1:])
    else:
        descriptor = os.open(".", _flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)))
        components = tuple(path.parts)
    if not components:
        os.close(descriptor)
        raise SafeFileError("safe file path names a directory")
    _validate_directory(descriptor)
    try:
        for component in components:
            _validate_component(component)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor, components


@contextlib.contextmanager
def parent_fd(target_or_root: Path, relative: Path | None = None, *, create: bool = False) -> Iterator[tuple[int, str]]:
    """Yield ``(parent_fd, leaf)`` after opening every ancestor safely.

    Passing ``relative`` preserves the historic ``repo, relative`` API.
    Passing one path is useful for setup files outside the repository.
    """
    target = Path(target_or_root) if relative is None else Path(target_or_root) / Path(relative)
    if relative is not None and (Path(relative).is_absolute() or ".." in Path(relative).parts):
        raise SafeFileError("unsafe descriptor-relative path")
    descriptor, components = _path_parts(target)
    try:
        for component in components[:-1]:
            try:
                child = os.open(component, _flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)), dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, 0o700, dir_fd=descriptor)
                child = os.open(component, _flags(os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)), dir_fd=descriptor)
            except OSError as error:
                raise SafeFileError(f"unsafe intermediate safe-file component: {component}") from error
            try:
                _validate_directory(child)
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        yield descriptor, components[-1]
    finally:
        os.close(descriptor)


def _read_at(directory: int, name: str) -> tuple[bytes, int]:
    try:
        descriptor = os.open(name, _flags(os.O_RDONLY), dir_fd=directory)
    except FileNotFoundError:
        raise
    except OSError as error:
        raise SafeFileError(f"unsafe final safe-file component: {name}") from error
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise SafeFileError("safe file must be a regular file")
        if metadata.st_uid != os.getuid():
            raise SafeFileError("safe file is not owned by the current user")
        if metadata.st_mode & (stat.S_ISUID | stat.S_ISGID) or metadata.st_mode & 0o022:
            raise SafeFileError("safe file has unsafe mode bits")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks), stat.S_IMODE(metadata.st_mode)
    finally:
        os.close(descriptor)


def read_snapshot(target_or_root: Path, relative: Path | None = None) -> tuple[bytes, int]:
    with parent_fd(target_or_root, relative) as (directory, name):
        return _read_at(directory, name)


def _write_temp(directory: int, data: bytes, mode: int) -> str:
    if mode & ~0o7777 or mode & (stat.S_ISUID | stat.S_ISGID):
        raise SafeFileError("safe file mode is invalid")
    name = f".hard-eng-{secrets.token_hex(24)}"
    try:
        descriptor = os.open(name, _flags(os.O_WRONLY | os.O_CREAT | os.O_EXCL), mode, dir_fd=directory)
    except FileExistsError as error:
        raise SafeFileError("hostile precreated safe-file temporary") from error
    try:
        os.fchmod(descriptor, mode)
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise SafeFileError("zero-byte safe file write")
            view = view[written:]
        os.fsync(descriptor)
    except BaseException:
        try:
            os.close(descriptor)
        finally:
            try:
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
            except FileNotFoundError:
                pass
        raise
    os.close(descriptor)
    return name


def _exchange(directory: int, left: str, right: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    encoded_left = os.fsencode(left)
    encoded_right = os.fsencode(right)
    if platform.system() == "Darwin" and hasattr(libc, "renameatx_np"):
        result = libc.renameatx_np(directory, encoded_left, directory, encoded_right, 0x00000002)
    elif platform.system() == "Linux" and hasattr(libc, "renameat2"):
        result = libc.renameat2(directory, encoded_left, directory, encoded_right, 0x00000002)
    else:
        raise SafeFileError("atomic safe-file exchange is unsupported on this platform")
    if result != 0:
        error = ctypes.get_errno()
        raise SafeFileError(error, os.strerror(error))


def _replace_at_locked(
    directory: int,
    name: str,
    expected: bytes,
    expected_mode: int,
    replacement: bytes,
    *,
    replacement_mode: int | None = None,
    read_at: Callable[[int, str], tuple[bytes, int]] = _read_at,
    write_temp: Callable[[int, bytes, int], str] = _write_temp,
    exchange: Callable[[int, str, str], None] = _exchange,
) -> None:
    current, mode = read_at(directory, name)
    if current != expected or mode != expected_mode:
        raise SafeFileError("safe file byte or mode preimage changed")
    installed_mode_expected = expected_mode if replacement_mode is None else replacement_mode
    temporary = write_temp(directory, replacement, installed_mode_expected)
    exchanged = False
    verified = False
    try:
        exchange(directory, temporary, name)
        exchanged = True
        os.chmod(temporary, 0o600, dir_fd=directory, follow_symlinks=False)
        os.fsync(directory)
        installed, installed_mode = read_at(directory, name)
        backup, backup_mode = read_at(directory, temporary)
        if (
            installed != replacement
            or installed_mode != installed_mode_expected
            or backup != expected
            or backup_mode != 0o600
        ):
            raise SafeFileError("safe file byte or mode preimage changed before exchange")
        verified = True
        os.fsync(directory)
        os.unlink(temporary, dir_fd=directory)
        exchanged = False
        os.fsync(directory)
    except BaseException:
        if exchanged and not verified:
            try:
                exchange(directory, temporary, name)
            except BaseException as rollback_error:
                try:
                    os.chmod(temporary, 0o600, dir_fd=directory, follow_symlinks=False)
                except OSError:
                    pass
                os.fsync(directory)
                raise SafeFileError(
                    "safe file preimage changed and atomic rollback failed; "
                    f"recover concurrent PLAN bytes from sibling {temporary}"
                ) from rollback_error
            try:
                os.chmod(name, expected_mode, dir_fd=directory, follow_symlinks=False)
                os.unlink(temporary, dir_fd=directory)
            finally:
                os.fsync(directory)
            exchanged = False
        elif exchanged:
            try:
                os.chmod(temporary, 0o600, dir_fd=directory, follow_symlinks=False)
                os.fsync(directory)
            except OSError:
                pass
        if not exchanged:
            try:
                os.unlink(temporary, dir_fd=directory)
                os.fsync(directory)
            except FileNotFoundError:
                pass
        raise


def _replace_at(
    directory: int,
    name: str,
    expected: bytes,
    expected_mode: int,
    replacement: bytes,
    *,
    replacement_mode: int | None = None,
    read_at: Callable[[int, str], tuple[bytes, int]] = _read_at,
    write_temp: Callable[[int, bytes, int], str] = _write_temp,
    exchange: Callable[[int, str, str], None] = _exchange,
) -> None:
    fcntl.flock(directory, fcntl.LOCK_EX)
    try:
        _replace_at_locked(
            directory,
            name,
            expected,
            expected_mode,
            replacement,
            replacement_mode=replacement_mode,
            read_at=read_at,
            write_temp=write_temp,
            exchange=exchange,
        )
    finally:
        fcntl.flock(directory, fcntl.LOCK_UN)


def replace_if_unchanged(
    target_or_root: Path,
    relative_or_expected: Path | bytes,
    expected_or_mode: bytes | int,
    mode_or_replacement: int | bytes,
    replacement: bytes | None = None,
    *,
    replacement_mode: int | None = None,
    read_at: Callable[[int, str], tuple[bytes, int]] = _read_at,
    write_temp: Callable[[int, bytes, int], str] = _write_temp,
    exchange: Callable[[int, str, str], None] = _exchange,
) -> None:
    """Replace a complete file after an exact byte and mode preimage check."""
    if isinstance(relative_or_expected, Path):
        relative = relative_or_expected
        expected = expected_or_mode
        expected_mode = mode_or_replacement
        if replacement is None or not isinstance(expected, bytes) or not isinstance(expected_mode, int):
            raise TypeError("invalid safe-file replacement arguments")
        with parent_fd(target_or_root, relative) as (directory, name):
            _replace_at(
                directory,
                name,
                expected,
                expected_mode,
                replacement,
                replacement_mode=replacement_mode,
                read_at=read_at,
                write_temp=write_temp,
                exchange=exchange,
            )
        return
    raise TypeError("safe-file replacement requires a Path relative argument")


def create_new(
    target_or_root: Path,
    relative: Path,
    data: bytes,
    mode: int,
    *,
    read_at: Callable[[int, str], tuple[bytes, int]] = _read_at,
    write_temp: Callable[[int, bytes, int], str] = _write_temp,
) -> None:
    with parent_fd(target_or_root, relative, create=True) as (directory, name):
        temporary = write_temp(directory, data, mode)
        try:
            os.link(temporary, name, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            created, created_mode = read_at(directory, name)
            if created != data or created_mode != mode:
                raise SafeFileError("safe file changed during creation")
            os.unlink(temporary, dir_fd=directory)
            os.fsync(directory)
        except BaseException:
            try:
                os.unlink(temporary, dir_fd=directory)
                os.fsync(directory)
            except FileNotFoundError:
                pass
            raise


def replace_path_if_unchanged(
    path: Path,
    expected: bytes,
    expected_mode: int,
    replacement: bytes,
    *,
    replacement_mode: int | None = None,
    read_at: Callable[[int, str], tuple[bytes, int]] = _read_at,
    write_temp: Callable[[int, bytes, int], str] = _write_temp,
    exchange: Callable[[int, str, str], None] = _exchange,
) -> None:
    parent = path.parent
    relative = Path(path.name)
    replace_if_unchanged(
        parent,
        relative,
        expected,
        expected_mode,
        replacement,
        replacement_mode=replacement_mode,
        read_at=read_at,
        write_temp=write_temp,
        exchange=exchange,
    )


def create_path(path: Path, data: bytes, mode: int) -> None:
    create_new(path.parent, Path(path.name), data, mode)


def consume_if_unchanged(target_or_root: Path, relative: Path, expected: bytes, expected_mode: int) -> None:
    """Atomically claim and remove one exact regular file."""
    with parent_fd(target_or_root, relative) as (directory, name):
        fcntl.flock(directory, fcntl.LOCK_EX)
        try:
            current, mode = _read_at(directory, name)
            if current != expected or mode != expected_mode:
                raise SafeFileError("safe file byte or mode preimage changed")
            claimed = f".hard-eng-consumed-{secrets.token_hex(24)}"
            try:
                os.link(name, claimed, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
            except FileExistsError as error:
                raise SafeFileError("hostile precreated consume claim") from error
            try:
                claimed_data, claimed_mode = _read_at(directory, claimed)
                if claimed_data != expected or claimed_mode != expected_mode:
                    raise SafeFileError("safe file changed while it was claimed")
                os.unlink(name, dir_fd=directory)
                os.fsync(directory)
            finally:
                os.unlink(claimed, dir_fd=directory)
                os.fsync(directory)
        finally:
            fcntl.flock(directory, fcntl.LOCK_UN)
