"""Shared helpers for regression checks: named failures and fixture git commands."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

from git_env import git_env

FIXTURE_IDENTITY = ("-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid")


def checker(prefix: str) -> tuple[Callable[[str], NoReturn], Callable[[bool, str], None]]:
    def fail(message: str) -> NoReturn:
        raise SystemExit(f"{prefix}: {message}")

    def require(condition: bool, message: str) -> None:
        if not condition:
            fail(message)

    return fail, require


def git(repo: Path, *args: str) -> str:
    base = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    command = ["git", "-C", str(repo), *FIXTURE_IDENTITY, *args]
    return subprocess.run(command, check=True, capture_output=True, text=True, env=git_env(base)).stdout
