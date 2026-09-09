#!/usr/bin/env python3
"""Regression checks that kill the surviving mutants of git_env.py."""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_fixture import checker


def make_checker(name: str) -> tuple[Callable[[str], NoReturn], Callable[[bool, str], None]]:
    return checker(name)


fail, require = make_checker("git-env-survivors")

import git_env


@contextlib.contextmanager
def temporary_cache():
    with tempfile.TemporaryDirectory(prefix="git-env-cached-") as workspace:
        cache = Path(workspace) / "cache.json"
        original = git_env._CACHE
        git_env._CACHE = cache
        try:
            yield cache
        finally:
            git_env._CACHE = original


@contextlib.contextmanager
def patched_path(value):
    original = os.environ.get("PATH")
    if value is None:
        os.environ.pop("PATH", None)
    else:
        os.environ["PATH"] = value
    try:
        yield
    finally:
        if original is not None:
            os.environ["PATH"] = original
        else:
            os.environ.pop("PATH", None)


def make_executable_git(directory: Path) -> Path:
    git_path = directory / "git"
    git_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    git_path.chmod(0o755)
    return git_path


def check_cached_none_fingerprint() -> None:
    require(git_env._cached(None) is None, "a missing fingerprint must never consult the disk cache")


def check_cached_missing_file() -> None:
    with temporary_cache():
        require(git_env._cached("fp") is None, "a missing cache file must read as a clean miss")


def check_cached_wrong_mode() -> None:
    with temporary_cache() as cache:
        cache.write_text(json.dumps({"fingerprint": "fp", "variables": ["A", "B"]}), encoding="utf-8")
        cache.chmod(0o644)
        require(git_env._cached("fp") is None, "a cache file with a non-0600 mode must never be trusted")


def check_cached_valid_record() -> None:
    with temporary_cache() as cache:
        cache.write_text(json.dumps({"fingerprint": "fp", "variables": ["A", "B"]}), encoding="utf-8")
        cache.chmod(0o600)
        result = git_env._cached("fp")
        require(result == frozenset({"A", "B"}), f"a valid matching cache must return its variables, got {result!r}")


def check_cached_fingerprint_mismatch() -> None:
    with temporary_cache() as cache:
        cache.write_text(json.dumps({"fingerprint": "other", "variables": ["A"]}), encoding="utf-8")
        cache.chmod(0o600)
        require(git_env._cached("fp") is None, "a cache written for a different git binary must be rejected")


def check_cached_invalid_variable_types() -> None:
    with temporary_cache() as cache:
        cache.write_text(json.dumps({"fingerprint": "fp", "variables": [1, 2]}), encoding="utf-8")
        cache.chmod(0o600)
        require(git_env._cached("fp") is None, "non-string cached variable names must be rejected")


def check_git_fingerprint_finds_match_after_skipping_a_bad_directory() -> None:
    with tempfile.TemporaryDirectory(prefix="git-fp-") as workspace:
        real_dir = Path(workspace) / "real"
        real_dir.mkdir()
        git_path = make_executable_git(real_dir)
        bogus = str(Path(workspace) / "does-not-exist")
        with patched_path(f"{bogus}{os.pathsep}{real_dir}"):
            result = git_env._git_fingerprint()
        info = git_path.stat()
        expected = f"{git_path}:{info.st_mtime_ns}:{info.st_size}"
        require(result == expected, f"expected {expected!r}, got {result!r}")


def check_git_fingerprint_missing_path_is_none() -> None:
    with patched_path(None):
        require(git_env._git_fingerprint() is None, "a process with no PATH at all must report no git")


def check_git_fingerprint_default_is_not_a_literal_directory() -> None:
    with tempfile.TemporaryDirectory(prefix="git-fp-default-") as workspace:
        cwd = Path(workspace)
        weird = cwd / "XXXX"
        weird.mkdir()
        make_executable_git(weird)
        previous_cwd = Path.cwd()
        os.chdir(cwd)
        try:
            with patched_path(None):
                require(
                    git_env._git_fingerprint() is None,
                    "a missing PATH must never fall back to a literal 'XXXX' directory",
                )
        finally:
            os.chdir(previous_cwd)


def check_git_fingerprint_skips_leading_empty_path_component() -> None:
    with tempfile.TemporaryDirectory(prefix="git-fp-empty-") as workspace:
        real_dir = Path(workspace)
        git_path = make_executable_git(real_dir)
        with patched_path(f"{os.pathsep}{real_dir}"):
            result = git_env._git_fingerprint()
        info = git_path.stat()
        expected = f"{git_path}:{info.st_mtime_ns}:{info.st_size}"
        require(result == expected, f"a leading empty PATH entry must not abort the search, got {result!r}")


def check_git_fingerprint_rejects_directory_named_git() -> None:
    with tempfile.TemporaryDirectory(prefix="git-fp-dir-") as workspace:
        fake = Path(workspace) / "git"
        fake.mkdir()
        fake.chmod(0o755)
        with patched_path(str(workspace)):
            require(
                git_env._git_fingerprint() is None,
                "a directory literally named 'git' must never be treated as the executable",
            )


def main() -> int:
    check_cached_none_fingerprint()
    check_cached_missing_file()
    check_cached_wrong_mode()
    check_cached_valid_record()
    check_cached_fingerprint_mismatch()
    check_cached_invalid_variable_types()
    check_git_fingerprint_finds_match_after_skipping_a_bad_directory()
    check_git_fingerprint_missing_path_is_none()
    check_git_fingerprint_default_is_not_a_literal_directory()
    check_git_fingerprint_skips_leading_empty_path_component()
    check_git_fingerprint_rejects_directory_named_git()
    print("git-env-survivors: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
