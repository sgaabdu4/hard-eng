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
from contextlib import suppress
from pathlib import Path
from typing import TextIO

RESULT_FILE = ".hard-eng/update-result.txt"
LOG_FILE = ".hard-eng/update.log"
OWNER = re.compile(r"hard-eng-update (\d+)")


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


def current_head(root: Path) -> str:
    found = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return found.stdout.strip()


def landed_commit(root: Path, head: str, message: str) -> tuple[str, str] | None:
    """The updater's own commit since head, found by its message because the agent may commit too."""
    span = head + "..HEAD" if head else "-1"
    found = subprocess.run(
        ["git", "log", "--format=%H %P%x1f%s", span],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    for line in found.stdout.splitlines():
        identities, _, subject = line.partition("\x1f")
        commit, *parents = identities.split()
        if subject == message:
            return commit, parents[0] if parents else ""
    return None


def rebase_sessions(root: Path, head: str, message: str) -> bool:
    """Sessions based on the update commit's parent must not count that commit as their work."""
    landed = landed_commit(root, head, message)
    if landed is None:
        return False
    commit, parent = landed
    for state in (root / ".hard-eng/sessions").glob("*.json"):
        try:
            saved = json.loads(state.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(saved, dict) and parent and saved.get("base") == parent:
            state.write_text(json.dumps({**saved, "base": commit}))
    return True


def written(root: Path, name: str, content: str | None, link: bool) -> bool:
    """Whether a path still holds what the updater wrote, so rollback cannot erase a later edit."""
    target = root / name
    if content is None:
        return not target.exists() and not target.is_symlink()
    if link:
        return target.is_symlink() and str(target.readlink()) == content
    return (
        target.is_file()
        and not target.is_symlink()
        and target.read_text(errors="replace") == content
    )


def roll_back(
    root: Path,
    changes: dict[str, str | None],
    links: dict[str, str | None],
    before: dict[str, bytes | None],
    before_links: dict[str, str | None],
) -> list[str]:
    """Restore each path only while it still holds the updater's write, checked just before."""
    from update import replace_file

    kept = []
    for name, content in before.items():
        target = root / name
        if not written(root, name, changes[name], False):
            kept.append(name)
        elif content is None:
            target.unlink(missing_ok=True)
        else:
            replace_file(target, content)
    for name, target in before_links.items():
        if not written(root, name, links[name], True):
            kept.append(name)
            continue
        if (root / name).is_dir() and not (root / name).is_symlink():
            shutil.rmtree(root / name)
        else:
            (root / name).unlink(missing_ok=True)
        if target is not None:
            (root / name).symlink_to(target, target_is_directory=True)
    return kept


def index_entries(root: Path, names: list[str]) -> dict[str, str]:
    listing = subprocess.check_output(
        ["git", "ls-files", "--stage", "-z", "--", *names], cwd=root, text=True
    )
    return {
        path: entry
        for entry, _, path in (
            line.partition("\t") for line in listing.split("\0") if line
        )
    }


def unstage_own(
    root: Path, names: list[str], staging: tuple[dict[str, str], dict[str, str]]
) -> None:
    """Unstage only index entries the updater changed and that still hold its staging."""
    before, staged = staging
    current = index_entries(root, names)
    own = [
        path
        for path in {*before, *staged, *current}
        if current.get(path) == staged.get(path) != before.get(path)
    ]
    if own:
        subprocess.run(
            ["git", "reset", "--quiet", "HEAD", "--", *own], cwd=root, check=True
        )


def commit_update(
    root: Path,
    changes: dict[str, str | None],
    links: dict[str, str | None],
    revision: str,
) -> None:
    from update import write_changes, write_links

    names = sorted({*changes, *links})
    before = {
        name: (root / name).read_bytes() if (root / name).exists() else None
        for name in changes
    }
    before_links = {
        name: str((root / name).readlink()) if (root / name).is_symlink() else None
        for name in links
    }
    head = current_head(root)
    message = f"Update Hard Eng to {revision}"
    staging: tuple[dict[str, str], dict[str, str]] | None = None
    try:
        write_links(root, links)
        write_changes(root, changes)
        # A SIGTERM mid-staging waits until the staging it must undo is recorded.
        mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM})
        try:
            index = index_entries(root, names)
            subprocess.run(
                ["git", "add", "--force", "--", *names], cwd=root, check=True
            )
            staging = (index, index_entries(root, names))
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, mask)
        result = subprocess.run(
            [
                "git",
                "commit",
                "--only",
                "-m",
                message,
                "--",
                *(
                    name
                    for name in names
                    if not any(other.startswith(f"{name}/") for other in changes)
                ),
            ],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=3500,
        )
        sys.stderr.write(result.stdout)
        if result.returncode != 0:
            # SessionStart stderr never reaches the agent, so the error carries the reason.
            tail = " | ".join(result.stdout.strip().splitlines()[-5:])
            raise subprocess.SubprocessError(
                f"git commit exited {result.returncode}: {tail}".removesuffix(": ")
            )
    except (OSError, subprocess.SubprocessError) as error:
        if rebase_sessions(root, head, message):
            raise
        kept = roll_back(root, changes, links, before, before_links)
        if staging is not None:
            unstage_own(root, names, staging)
        if kept:
            raise subprocess.SubprocessError(
                f"{error}; kept later edits to {', '.join(kept)} instead of rolling them back"
            ) from error
        raise
    rebase_sessions(root, head, message)


def alive(process: int) -> bool:
    try:
        os.kill(process, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def remove_stale_candidates(root: Path) -> None:
    """Remove candidates whose owning update has exited; the caller holds the lock."""
    listing = subprocess.check_output(
        ["git", "worktree", "list", "--porcelain"], cwd=root, text=True
    )
    for block in listing.split("\n\n"):
        fields = {
            key: value
            for key, _, value in (line.partition(" ") for line in block.splitlines())
        }
        path = Path(fields.get("worktree", ""))
        owner = OWNER.fullmatch(fields.get("locked", ""))
        if (
            path.name != "candidate"
            or not path.parent.name.startswith("hard-eng-update-")
            or owner is None
            or alive(int(owner[1]))
        ):
            continue
        if not path.exists():
            subprocess.run(
                ["git", "worktree", "unlock", str(path)], cwd=root, check=True
            )
        elif not subprocess.run(
            ["git", "worktree", "remove", "--force", "--force", str(path)],
            cwd=root,
            check=False,
            timeout=120,
        ).returncode:
            shutil.rmtree(path.parent, ignore_errors=True)
    subprocess.run(["git", "worktree", "prune"], cwd=root, check=True, timeout=60)


def exclusive(handle: TextIO) -> bool:
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def locked_update(root: Path, repair: bool = False) -> str:
    from update import update

    if (blocker := update_blocker(root)) is not None:
        return blocker
    with lock_file(root).open("a") as handle:
        if not exclusive(handle):
            raise UpdateRunning(
                "Another Hard Eng update is already running for this repository; "
                "wait for its result instead of starting another"
            )
        remove_stale_candidates(root)
        return update(root, repair)


def failed_update(error: Exception | str) -> str:
    return f"Hard Eng update failed: {error}. Continue with the existing scaffold; its gates remain required."


def record_result(root: Path, outcome: str) -> None:
    result = root / RESULT_FILE
    result.parent.mkdir(parents=True, exist_ok=True)
    pending = result.with_suffix(".tmp")
    pending.write_text(f"{time.strftime('%Y-%m-%d %H:%M %Z')}: {outcome}\n")
    pending.replace(result)


def interrupt_update(signum: int, _frame: object) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    raise subprocess.SubprocessError(f"interrupted by signal {signum}")


def installed_revision(root: Path) -> object:
    from update import SOURCE_FILE

    try:
        return json.loads((root / SOURCE_FILE).read_text()).get("revision")
    except (OSError, ValueError, AttributeError):
        return None


def apply_update(root: Path) -> int:
    """Install the update and record its outcome; the supervising process holds the lock."""
    from update import update

    signal.signal(signal.SIGTERM, interrupt_update)
    previous = installed_revision(root)
    try:
        outcome = update(root)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        outcome = failed_update(error)
        if (revision := installed_revision(root)) != previous:
            outcome = (
                f"Updated Hard Eng to {revision} with a local commit, but it stopped before "
                f"its final steps ({error}); the next update finishes them."
            )
    record_result(root, outcome)
    return 0


def update_command(*options: str) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).with_name("hard-eng.py")),
        "update",
        *options,
    ]


def group_exists(group: int) -> bool:
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # macOS refuses signals to a group holding only unreaped zombies.
        return True
    return True


def stop_group(update: "subprocess.Popen[bytes]") -> None:
    """Stop the update's whole process group, killing anything that ignores SIGTERM."""
    for signum in (signal.SIGTERM, signal.SIGKILL):
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(update.pid, signum)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            update.poll()
            if not group_exists(update.pid):
                return
            time.sleep(0.1)


def run_update(root: Path) -> int:
    """Hold the repository's update lock while one update runs in its own process group."""
    with lock_file(root).open("a") as handle:
        if not exclusive(handle):
            return 0
        try:
            remove_stale_candidates(root)
            update = subprocess.Popen(
                update_command("--apply"),
                cwd=root,
                process_group=0,
                pass_fds=(handle.fileno(),),
            )
        except (OSError, subprocess.SubprocessError) as error:
            record_result(root, failed_update(error))
            return 0
        signal.signal(signal.SIGTERM, interrupt_update)
        with suppress(subprocess.SubprocessError):
            try:
                update.wait()
            finally:
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
        stop_group(update)
        if update.returncode != 0:
            record_result(root, failed_update(f"update exited {update.returncode}"))
        with suppress(OSError, subprocess.SubprocessError):
            remove_stale_candidates(root)
    return 0


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
                update_command(),
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
