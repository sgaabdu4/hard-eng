#!/usr/bin/env python3
"""Descriptor-relative repository I/O with no symlink traversal."""

from __future__ import annotations

import errno
import os
import secrets
import stat
from pathlib import Path
from typing import Callable

from plan_contract import PlanStateError


DIRECTORY_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
FILE_FLAGS = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def clean_relative(relative: Path) -> Path:
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise PlanStateError(f"unsafe repository path: {relative}")
    return relative


def parent_descriptor(
    root: Path, relative: Path, *, create: bool = False, created: list[Path] | None = None
) -> tuple[int, str]:
    relative = clean_relative(relative)
    descriptor = os.open(root, DIRECTORY_FLAGS)
    traversed = Path()
    try:
        for part in relative.parts[:-1]:
            traversed /= part
            try:
                child = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o755, dir_fd=descriptor)
                if created is not None:
                    created.append(traversed)
                child = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, relative.name
    except BaseException:
        os.close(descriptor)
        raise


def snapshot(root: Path, relative: Path, label: str) -> tuple[bytes, int]:
    parent, name = parent_descriptor(root, relative)
    descriptor = -1
    try:
        descriptor = os.open(name, FILE_FLAGS, dir_fd=parent)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise PlanStateError(f"{label} must be a regular file")
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks), stat.S_IMODE(metadata.st_mode)
    except OSError as exc:
        raise PlanStateError(f"unsafe repository file: {label}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent)


def snapshot_optional(root: Path, relative: Path, label: str) -> tuple[bytes, int] | None:
    try:
        return snapshot(root, relative, label)
    except (OSError, PlanStateError) as exc:
        try:
            parent, name = parent_descriptor(root, relative)
        except FileNotFoundError:
            return None
        try:
            try:
                os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return None
        finally:
            os.close(parent)
        raise PlanStateError(f"unsafe repository file: {label}") from exc


def atomic_write(
    root: Path, relative: Path, content: bytes, mode: int, *, created: list[Path] | None = None,
    on_replace: Callable[[], None] | None = None,
) -> None:
    parent, name = parent_descriptor(root, relative, create=True, created=created)
    temporary = f".{name}.{secrets.token_hex(12)}"
    descriptor = -1
    try:
        try:
            metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode):
                raise PlanStateError(f"destination path is not a regular file: {relative}")
        except FileNotFoundError:
            pass
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            mode,
            dir_fd=parent,
        )
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(errno.EIO, "short repository write")
            view = view[written:]
        os.fsync(descriptor)
        os.fchmod(descriptor, mode)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        if on_replace is not None:
            on_replace()
        os.fsync(parent)
    except OSError as exc:
        raise PlanStateError(f"unsafe repository write: {relative}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=parent)
        except FileNotFoundError:
            pass
        os.close(parent)


def unlink(root: Path, relative: Path) -> None:
    parent, name = parent_descriptor(root, relative)
    try:
        try:
            metadata = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        if not stat.S_ISREG(metadata.st_mode):
            raise PlanStateError(f"unsafe repository removal: {relative}")
        os.unlink(name, dir_fd=parent)
        os.fsync(parent)
    finally:
        os.close(parent)


def rmdir(root: Path, relative: Path) -> None:
    parent, name = parent_descriptor(root, relative)
    try:
        os.rmdir(name, dir_fd=parent)
    finally:
        os.close(parent)
