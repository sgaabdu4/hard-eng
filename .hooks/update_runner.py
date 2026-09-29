"""Run the scaffold update detached from agent startup, one per repository."""

import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

RESULT_FILE = ".hard-eng/update-result.txt"
LOG_FILE = ".hard-eng/update.log"


class UpdateRunning(ValueError):
    pass


def update_blocker(root: Path) -> str | None:
    from update import SOURCE_FILE

    marker = root / SOURCE_FILE
    if not marker.exists():
        return "Automatic update unavailable: this checkout has no installed source revision."
    metadata = json.loads(marker.read_text())
    if not isinstance(metadata, dict):
        raise TypeError("Installed source metadata must be an object")
    previous = metadata.get("revision")
    if not isinstance(previous, str) or not re.fullmatch(r"[0-9a-f]{40}", previous):
        return "Installed from an uncommitted working copy; publish a verified source revision before automatic updates."
    return None


def lock_file(root: Path) -> Path:
    """One lock per repository, because every worktree shares its registered worktrees."""
    common = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=root,
        text=True,
    )
    return Path(common.strip()) / "hard-eng-update.lock"


def update_running(root: Path) -> bool:
    lock = lock_file(root)
    if not lock.is_file():
        return False
    with lock.open() as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def stale_message(root: Path, revision: str) -> str:
    if update_running(root):
        return (
            f"Hard Eng update to newer verified revision {revision} is still running in the "
            f"background ({LOG_FILE}). Wait for it to finish without starting another update, "
            "then reverify before shipping or claiming completion."
        )
    return (
        f"Hard Eng freshness check found newer verified revision {revision}. "
        "Use the supported updater, preserve local edits, then reverify before shipping or claiming completion."
    )


def rebase_sessions(root: Path) -> None:
    """Sessions based on the parent of a just-made update commit must not count it as their work."""
    found = subprocess.run(
        ["git", "rev-parse", "HEAD", "HEAD^"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if found.returncode != 0:
        return
    head, parent = found.stdout.split()
    for state in (root / ".hard-eng/sessions").glob("*.json"):
        try:
            saved = json.loads(state.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(saved, dict) and saved.get("base") == parent:
            state.write_text(json.dumps({**saved, "base": head}))


def remove_stale_candidates(root: Path) -> None:
    """Remove candidates left by an update that was killed; the caller holds the lock."""
    listing = subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"], cwd=root, text=True
    )
    for line in listing.splitlines():
        path = Path(line.removeprefix("worktree "))
        if (
            line.startswith("worktree ")
            and path.name == "candidate"
            and path.parent.name.startswith("hard-eng-update-")
        ):
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(path)],
                cwd=root,
                check=False,
                timeout=120,
            )
            shutil.rmtree(path.parent, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=root, check=True, timeout=60)


def locked_update(root: Path, repair: bool = False) -> str:
    from update import update

    if (blocker := update_blocker(root)) is not None:
        return blocker
    with lock_file(root).open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise UpdateRunning(
                "Another Hard Eng update is already running for this repository; "
                "wait for its result instead of starting another"
            ) from error
        remove_stale_candidates(root)
        return update(root, repair)


def failed_update(error: Exception) -> str:
    return f"Hard Eng update failed: {error}. Continue with the existing scaffold; its gates remain required."


def stop_children() -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.killpg(0, signal.SIGTERM)


def interrupt_update(signum: int, _frame: object) -> None:
    stop_children()
    raise subprocess.SubprocessError(f"interrupted by signal {signum}")


def run_update(root: Path) -> int:
    """Run one update and record its outcome; a detached worker also stops everything it started."""
    detached = os.getsid(0) == os.getpid()
    if detached:
        signal.signal(signal.SIGTERM, interrupt_update)
    try:
        try:
            outcome = locked_update(root)
        except UpdateRunning:
            return 0
        except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
            outcome = failed_update(error)
        result = root / RESULT_FILE
        result.parent.mkdir(parents=True, exist_ok=True)
        pending = result.with_suffix(".tmp")
        pending.write_text(f"{time.strftime('%Y-%m-%d %H:%M %Z')}: {outcome}\n")
        pending.replace(result)
        return 0
    finally:
        if detached:
            stop_children()


def start_update(root: Path) -> str:
    """Report the last update and start the next one detached, so session start never waits on it."""
    if (blocker := update_blocker(root)) is not None:
        return "Hard Eng update result: " + blocker
    if update_running(root):
        status = "A Hard Eng update is already running in the background"
    else:
        log = root / LOG_FILE
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("w") as output:
            subprocess.Popen(
                [
                    sys.executable,
                    str(Path(__file__).with_name("hard-eng.py")),
                    "update",
                ],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        status = "Hard Eng update started in the background"
    result = root / RESULT_FILE
    last = result.read_text().strip() if result.is_file() else "none recorded yet"
    return (
        f"{status} ({LOG_FILE}); this session keeps the installed scaffold and its gates until "
        "it finishes, and the next session start reports its result. Do not run setup meanwhile. "
        f"Last update result: {last}"
    )
