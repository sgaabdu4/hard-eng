"""The repository copy of Hard Eng: a shallow clone of newest main under .agents/hard-eng.

This file also runs standalone inside the generated .hard-eng/bootstrap.sh, so it uses only the standard library.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

try:
    import fcntl
except ImportError:
    fcntl = None

DEFAULT_SOURCE_URL = "https://github.com/sgaabdu4/hard-eng"
SOURCE_BRANCH = "main"
AGENTS = ("claude", "codex", "copilot")
COMMIT_ID = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_FILES = ("AGENTS.md", "bin/hard-eng", "scripts/hooks/agent-hook.sh")
LEGACY_ENTRIES = ("releases", "last-check.json")
CLONE_TIMEOUT_SECONDS = 600
REMOTE_TIMEOUT_SECONDS = 60


class SourceError(RuntimeError):
    """The repository copy of Hard Eng could not be fetched or is unusable."""


@dataclass(frozen=True)
class Checkout:
    root: Path
    commit: str


def log(message: str) -> None:
    print(f"hard-eng bootstrap: {message}", file=sys.stderr, flush=True)


def source_url() -> str:
    return os.environ.get("HARD_ENG_SOURCE_URL") or DEFAULT_SOURCE_URL


def local_root(root: Path) -> Path:
    return root / ".agents" / "hard-eng"


def _git(*arguments: str, timeout: float) -> subprocess.CompletedProcess[str]:
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ["git", *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            stdin=subprocess.DEVNULL,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SourceError(f"git could not run: {error}") from error


def read_checkout(local: Path) -> Checkout | None:
    """The usable copy behind .agents/hard-eng/current, or None when it must be cloned."""
    current = local / "current"
    if not current.is_symlink():
        return None
    try:
        resolved = current.resolve(strict=True)
    except OSError:
        return None
    if resolved.parent != (local / "checkouts").resolve() or not resolved.is_dir():
        return None
    if any(not (resolved / name).is_file() for name in REQUIRED_FILES):
        return None
    head = _git("-C", str(resolved), "rev-parse", "HEAD", timeout=15).stdout.strip()
    if not COMMIT_ID.fullmatch(head):
        return None
    return Checkout(resolved, head)


def remote_commit(url: str) -> str | None:
    result = _git("ls-remote", url, f"refs/heads/{SOURCE_BRANCH}", timeout=REMOTE_TIMEOUT_SECONDS)
    if result.returncode != 0:
        return None
    head = result.stdout.split("\t", 1)[0].strip()
    if not COMMIT_ID.fullmatch(head):
        raise SourceError(f"{url} has no {SOURCE_BRANCH} branch")
    return head


@contextmanager
def _update_lock(local: Path) -> Iterator[None]:
    if fcntl is None:
        raise SourceError("the repository copy of Hard Eng is supported only on macOS and Linux")
    for directory in (local.parent, local):
        directory.mkdir(mode=0o700, exist_ok=True)
    handle = os.open(local / ".update.lock", os.O_CREAT | os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)


def _clone(url: str, checkouts: Path) -> Checkout:
    checkouts.mkdir(mode=0o700, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=checkouts))
    try:
        result = _git(
            "clone",
            "--quiet",
            "--depth",
            "1",
            "--branch",
            SOURCE_BRANCH,
            "--single-branch",
            url,
            str(stage / "tree"),
            timeout=CLONE_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "git clone failed"
            raise SourceError(f"could not clone {url}: {detail}")
        head = _git("-C", str(stage / "tree"), "rev-parse", "HEAD", timeout=15).stdout.strip()
        if not COMMIT_ID.fullmatch(head):
            raise SourceError(f"the clone of {url} has no readable commit")
        target = checkouts / head
        if not target.is_dir():
            os.rename(stage / "tree", target)
        return Checkout(target, head)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _activate(local: Path, checkout: Checkout) -> None:
    link = local / "current"
    temporary = local / f".current.{os.getpid()}"
    temporary.symlink_to(Path("checkouts") / checkout.commit)
    os.replace(temporary, link)
    for entry in (local / "checkouts").iterdir():
        if entry.name != checkout.commit:
            shutil.rmtree(entry, ignore_errors=True)
    for name in LEGACY_ENTRIES:
        path = local / name
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)


def refresh(root: Path) -> Checkout:
    """Make .agents/hard-eng/current the newest main; keep the existing copy when the source is unreachable."""
    local = local_root(root)
    if local.is_symlink() or (local.exists() and not local.is_dir()):
        raise SourceError(f"{local} is not a directory")
    url = source_url()
    have = read_checkout(local)
    wanted = remote_commit(url)
    if wanted is None:
        if have is None:
            raise SourceError(f"could not reach {url} and no Hard Eng copy exists yet")
        log(f"could not reach {url}; keeping Hard Eng {have.commit[:12]}")
        return have
    if have is not None and have.commit == wanted:
        return have
    with _update_lock(local):
        have = read_checkout(local)
        if have is not None and have.commit == wanted:
            return have
        checkout = _clone(url, local / "checkouts")
        _activate(local, checkout)
    log(f"Hard Eng is now at {checkout.commit[:12]}")
    return checkout


def session(root: Path, agent: str) -> None:
    checkout = read_checkout(local_root(root))
    if checkout is None:
        raise SourceError("no Hard Eng copy exists yet")
    first_claude_session = agent == "claude" and not (root / "CLAUDE.local.md").exists()
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    result = subprocess.run(
        [sys.executable, str(checkout.root / "bin" / "hard-eng"), "prepare", "--repo", str(root), "--agent", agent],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        stdin=subprocess.DEVNULL,
        timeout=600,
    )
    if result.returncode != 0:
        raise SourceError(result.stderr.strip() or result.stdout.strip() or "hard-eng prepare failed")
    if first_claude_session:
        rules = (checkout.root / "AGENTS.md").read_text(encoding="utf-8")
        output = {"hookEventName": "SessionStart", "additionalContext": rules, "reloadSkills": True}
        print(json.dumps({"hookSpecificOutput": output}))


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in (*AGENTS, "download"):
        log("usage: bootstrap.sh <claude|codex|copilot|download>")
        return 1
    root, mode = Path(argv[0]), argv[1]
    try:
        refresh(root)
        if mode != "download":
            session(root, mode)
    except SourceError as error:
        log(str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
