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
from typing import NoReturn


scrub_environ(ceiling=tempfile.gettempdir())


class RestoreBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutState:
    content: bytes | None
    mode: int | None
    index_entries: bytes
    index_assume_skip_flags: bytes
    index_fsmonitor_flags: bytes
    status: bytes


@dataclass(frozen=True)
class Preimage:
    state: CheckoutState
    index: bytes
    index_mode: int


def fail(message: str) -> NoReturn:
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
    status = run_git(
        repo,
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
    )
    return CheckoutState(
        content=content,
        mode=mode,
        index_entries=run_git(repo, "ls-files", "--stage", "-z"),
        # Separate channels keep assume-unchanged distinct from fsmonitor-valid.
        index_assume_skip_flags=run_git(repo, "ls-files", "-v", "-z"),
        index_fsmonitor_flags=run_git(repo, "ls-files", "-f", "-z"),
        status=status,
    )


def capture_preimage(repo: Path, target: Path) -> Preimage:
    state = snapshot(repo, target)
    index = index_path(repo)
    return Preimage(
        state=state,
        index=index.read_bytes(),
        index_mode=stat.S_IMODE(index.stat().st_mode),
    )


def restore_incidental(
    repo: Path,
    target: Path,
    preimage: Preimage,
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

    if preimage.state.content is None:
        target.unlink(missing_ok=True)
    else:
        target.write_bytes(preimage.state.content)
        os.chmod(target, preimage.state.mode or 0o600)
    index = index_path(repo)
    index.write_bytes(preimage.index)
    os.chmod(index, preimage.index_mode)
    if snapshot(repo, target) != preimage.state:
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


def configure_fsmonitor(repo: Path) -> None:
    hook = repo / ".git/hooks/fsmonitor-fixture"
    hook.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        'if sys.argv[1] != "2":\n'
        "    raise SystemExit(1)\n"
        'os.write(1, b"fixture-token\\0")\n',
        encoding="utf-8",
    )
    os.chmod(hook, 0o755)
    run_git(repo, "config", "core.fsmonitor", str(hook))
    run_git(repo, "config", "core.fsmonitorHookVersion", "2")


def check_approved_output() -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        before = capture_preimage(repo, target)
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
        old_timestamp = 1_600_000_000_000_000_000
        os.utime(target, ns=(old_timestamp, old_timestamp))
        run_git(repo, "update-index", "--refresh")
        before = capture_preimage(repo, target)
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
        if result != "restored" or snapshot(repo, target) != before.state:
            fail("incidental CLI mutation did not restore the exact preimage")
        if index_path(repo).read_bytes() == before.index:
            fail("fixture did not exercise a Git index stat-cache rewrite")


def check_exclusive_owner_required() -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        before = capture_preimage(repo, target)
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
        before = capture_preimage(repo, target)
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


def check_concurrent_index_flag_drift(flag: str, expected_tag: bytes) -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        before = capture_preimage(repo, target)
        mutate_cli(repo, target, '{"mode":"incidental"}\n', 0o755)
        cli_postimage = snapshot(repo, target)
        run_git(repo, "update-index", flag, "config.json")
        concurrent = snapshot(repo, target)
        if concurrent == cli_postimage:
            fail(f"{flag} drift escaped the checkout snapshot")
        if not concurrent.index_assume_skip_flags.startswith(expected_tag):
            fail(f"{flag} drift did not reach the -v index flag channel")
        if flag == "--assume-unchanged" and not (
            concurrent.index_fsmonitor_flags.startswith(b"H ")
        ):
            fail("assume-unchanged was conflated with fsmonitor-valid")
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
            fail(f"{flag} drift was overwritten")
        if snapshot(repo, target) != concurrent:
            fail(f"{flag} drift rejection changed current state")


def check_fsmonitor_snapshot_idempotence() -> None:
    with tempfile.TemporaryDirectory() as name:
        repo, target = fixture(Path(name))
        configure_fsmonitor(repo)
        run_git(repo, "update-index", "--no-fsmonitor-valid", "config.json")
        first = snapshot(repo, target)
        second = snapshot(repo, target)
        if not first.index_fsmonitor_flags.startswith(b"h "):
            fail("protocol-v2 fsmonitor did not set the valid flag")
        if first != second:
            fail("consecutive fsmonitor snapshots were not idempotent")


def main() -> None:
    check_approved_output()
    check_incidental_restore()
    check_exclusive_owner_required()
    check_concurrent_drift()
    check_concurrent_index_flag_drift("--skip-worktree", b"S ")
    check_concurrent_index_flag_drift("--assume-unchanged", b"h ")
    check_fsmonitor_snapshot_idempotence()
    print("external-cli-restore-regressions: PASS")


if __name__ == "__main__":
    main()
