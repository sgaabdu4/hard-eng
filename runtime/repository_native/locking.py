"""One exclusive advisory lock per mutable Hard Eng owner."""

from __future__ import annotations

import os
import stat
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

from .errors import ConfigurationError


@contextmanager
def exclusive_lock(path: Path, *, timeout: float, holder: str) -> Iterator[None]:
    if fcntl is None:
        raise ConfigurationError("Hard Eng locking is supported only on macOS and Linux")
    flags = os.O_CREAT | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    handle: int | None = None
    try:
        handle = os.open(path, flags, 0o600)
        metadata = os.fstat(handle)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise ConfigurationError(f"lock file is unsafe: {path}")
    except ConfigurationError:
        if handle is not None:
            os.close(handle)
        raise
    except OSError as error:
        if handle is not None:
            os.close(handle)
        raise ConfigurationError(f"lock file could not be opened: {path}: {error}") from error
    assert handle is not None
    deadline = time.monotonic() + timeout
    waited = False
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.monotonic() >= deadline:
                os.close(handle)
                raise ConfigurationError(f"{holder} did not finish within {int(timeout)} seconds: {path}")
            if not waited:
                waited = True
                print(f"hard-eng: waiting for {holder} to finish", file=sys.stderr, flush=True)
            time.sleep(0.1)
        except OSError as error:
            os.close(handle)
            raise ConfigurationError(f"lock failed: {path}: {error}") from error
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)
