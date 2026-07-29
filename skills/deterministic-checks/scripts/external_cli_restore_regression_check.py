#!/usr/bin/env python3
"""Behavioral fixture for fail-closed external-CLI checkout restoration."""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from git_env import git_env, scrub_environ


scrub_environ(ceiling=tempfile.gettempdir())


class RestoreBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutState:
    content: bytes | None
    mode: int | None
    index: bytes
    index_mode: int
    status: bytes


def fail(message: str) -> None:
    raise SystemExit(f"external-cli-restore-regressions: FAIL: {message}")


def run_git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        env=git_env(),
    )
    if result.returncode:
        fail(result.stderr.decode(errors="replace").strip() or "fixture Git failed")
    return result.stdout


def index_path(repo: Path) -> Path:
    value = run_git(repo, "rev-parse", "--git-path", "index").decode().strip()
    path = Path(value)
    return path if path.is_absolute() else repo / path


def snapshot(repo: Path, target: Path) -> CheckoutState:
    if target.exists():
        metadata = target.stat()
        content = target.read_bytes()
        mode = stat.S_IMODE(metadata.st_mode)
    else:
        content = None
        mode = None
    index = index_path(repo)
    return CheckoutState(
        content=content,
        mode=mode,
        index=index.read_bytes(),
        index_mode=stat.S_IMODE(index.stat().st_mode),
        status=run_git(
            repo,
            "status",
            "--porcelain=v2",
            "-z",
            "--untracked-files=all",
        ),
    )


def restore_incidental(
    repo: Path,
    target: Path,
    preimage: CheckoutState,
    cli_postimage: CheckoutState,
    *,
    approved_output: bool,
    exclusive_owner: bool,
) -> str:
    if approved_output:
        return "preserve"
    if not exclusive_owner:
        raise RestoreBlocked("exclusive single-writer ownership is required")
    if snapshot(repo, target) != cli_postimage:
        raise RestoreBlocked("current state drifted after the CLI")

    if preimage.content is None:
        target.unlink(missing_ok=True)
    else:
        target.write_bytes(preimage.content)
        os.chmod(target, preimage.mode or 0o600)
    index = index_path(repo)
    index.write_bytes(preimage.index)
    os.chmod(index, preimage.index_mode)
    if snapshot(repo, target) != preimage:
        raise RestoreBlocked("exact preimage restoration failed")
    return "restored"


def fixture(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.name", "Contract Fixture")
    run_git(repo, "config", "user.email", "fixture@example.invalid")
    target = repo / "config.json"
    target.write_text('{"mode":"base"}\n', encoding="utf-8")
    os.chmod(target, 0o644)
    run_git(repo, "add", "config.json")
    run_git(repo, "commit", "-qm", "fixture")
    return repo, target


def mutate_cli(repo: Path, target: Path, value: str, mode: int) -> None:
    target.write_text(value, encoding="utf-8")
    os.chmod(target, mode)
    run_git(repo, "add", "config.json")


def check_approved_output() -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        before = snapshot(repo, target)
        mutate_cli(repo, target, '{"mode":"approved"}\n', 0o755)
        after = snapshot(repo, target)
        result = restore_incidental(
            repo,
            target,
            before,
            after,
            approved_output=True,
            exclusive_owner=True,
        )
        if result != "preserve" or snapshot(repo, target) != after:
            fail("approved CLI output was overwritten")


def check_incidental_restore() -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        before = snapshot(repo, target)
        mutate_cli(repo, target, '{"mode":"incidental"}\n', 0o755)
        after = snapshot(repo, target)
        result = restore_incidental(
            repo,
            target,
            before,
            after,
            approved_output=False,
            exclusive_owner=True,
        )
        if result != "restored" or snapshot(repo, target) != before:
            fail("incidental CLI mutation did not restore the exact preimage")


def check_exclusive_owner_required() -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        before = snapshot(repo, target)
        mutate_cli(repo, target, '{"mode":"incidental"}\n', 0o755)
        after = snapshot(repo, target)
        try:
            restore_incidental(
                repo,
                target,
                before,
                after,
                approved_output=False,
                exclusive_owner=False,
            )
        except RestoreBlocked:
            pass
        else:
            fail("restore ran without exclusive ownership")
        if snapshot(repo, target) != after:
            fail("failed ownership check overwrote CLI state")


def check_concurrent_drift() -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        before = snapshot(repo, target)
        mutate_cli(repo, target, '{"mode":"incidental"}\n', 0o755)
        cli_postimage = snapshot(repo, target)
        mutate_cli(repo, target, '{"mode":"concurrent"}\n', 0o700)
        concurrent = snapshot(repo, target)
        try:
            restore_incidental(
                repo,
                target,
                before,
                cli_postimage,
                approved_output=False,
                exclusive_owner=True,
            )
        except RestoreBlocked:
            pass
        else:
            fail("concurrent drift was overwritten")
        if snapshot(repo, target) != concurrent:
            fail("drift rejection changed current state")


def main() -> None:
    check_approved_output()
    check_incidental_restore()
    check_exclusive_owner_required()
    check_concurrent_drift()
    print("external-cli-restore-regressions: PASS")


if __name__ == "__main__":
    main()
