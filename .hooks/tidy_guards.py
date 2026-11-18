"""The checks the tidy runs before it removes anything, and the commands they use."""

import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path


def idle(stamp: float) -> bool:
    """Nothing touched the thing for a day."""
    return time.time() - stamp > 24 * 3600


GENERATED_FOLDERS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
CARGO_SIGNATURE = "Signature: 8a477f597d28d172789f06886806bc55"
REFLOG_SELECTOR = re.compile(r"@\{(\d+)\}$")
OPERATIONS = (
    "rebase-merge",
    "rebase-apply",
    "BISECT_LOG",
    "MERGE_HEAD",
    "CHERRY_PICK_HEAD",
    "REVERT_HEAD",
)
SUBMODULE_LINE = re.compile(r"(.)[0-9a-f]+ (.+?)(?: \(.*\))?")


class TidyStop(Exception):
    pass


ITEM_ERRORS = (TidyStop, ValueError, OSError, subprocess.SubprocessError)


def note(text: str) -> None:
    print(f"Tidy {text}", file=sys.stderr, flush=True)


def tidy_run(
    cwd: Path,
    limit: float,
    *command: str,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=limit,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise TidyStop(f"`{' '.join(command[:3])}` did not run: {error}") from error


def tidy_git(cwd: Path, *arguments: str) -> str:
    done = tidy_run(cwd, 120, "git", *arguments)
    if done.returncode:
        raise TidyStop(f"`git {' '.join(arguments[:3])}` exited {done.returncode}")
    return done.stdout


def reflog_time(cwd: Path, ref: str) -> float | None:
    """When the ref last moved; None when it has no log."""
    selector = tidy_git(
        cwd, "log", "-g", "-1", "--date=unix", "--format=%gd", ref
    ).strip()
    found = REFLOG_SELECTOR.search(selector)
    return float(found[1]) if found else None


def foreign_user(process: Path) -> bool:
    """A person's account other than ours owns the process; system accounts cannot sit in a worktree."""
    try:
        owner = process.stat().st_uid
    except OSError:
        return False
    return owner != os.getuid() and owner >= 1000


def process_links(process: Path) -> set[str] | None:
    """Where one process stands; None when a foreign user's process cannot be read."""
    found: set[str] = set()
    try:
        names = [process / "cwd"]
        with suppress(FileNotFoundError):
            names += [Path(entry.path) for entry in os.scandir(process / "fd")]
    except PermissionError:
        return None if foreign_user(process) else found
    for link in names:
        try:
            found.add(os.readlink(link))
        except PermissionError:
            if foreign_user(process):
                return None
        except OSError:
            continue
    return found


def proc_paths(proc: Path = Path("/proc")) -> set[str] | None:
    found: set[str] = set()
    for process in proc.iterdir():
        if process.name.isdigit() and int(process.name) != os.getpid():
            links = process_links(process)
            if links is None:
                return None
            found |= links
    return found


def open_paths() -> set[str] | None:
    """Every path a process has as its folder or open file; None when the host cannot say."""
    if os.name != "posix":
        return None
    if Path("/proc/self/cwd").exists():
        return proc_paths()
    if shutil.which("lsof") is None:
        return None
    done = tidy_run(Path("/"), 60, "lsof", "-n", "-P", "-w", "-F", "pn")
    if done.returncode not in {0, 1}:
        raise TidyStop(f"`lsof` exited {done.returncode}")
    names: set[str] = set()
    mine = False
    for line in done.stdout.splitlines():
        if line.startswith("p"):
            mine = line[1:] == str(os.getpid())
        elif line.startswith("n/") and not mine:
            names.add(line[1:])
    return names or None


def inside(path: Path, names: set[str]) -> bool:
    prefixes = {str(path), str(path.resolve())}
    return any(
        name == prefix or name.startswith(prefix + os.sep)
        for name in names
        for prefix in prefixes
    )


def codex_folder() -> Path:
    home = os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
    return (Path(home) / "worktrees").resolve()


def generated(worktree: Path) -> Callable[[str], bool]:
    """Names of ignored entries that only a tool run leaves behind."""

    def known(name: str) -> bool:
        from process_group import INSTALL_FOLDERS

        parts = name.rstrip("/").split("/")
        if parts[0] == ".hard-eng":
            browser = worktree / ".hard-eng/browser"
            return not (browser.is_dir() and any(browser.iterdir()))
        if name == "target/":
            return cargo_target(worktree)
        return name.endswith("/") and (
            parts[-1] in GENERATED_FOLDERS or parts[-1] in INSTALL_FOLDERS
        )

    return known


def cargo_target(worktree: Path) -> bool:
    tag = worktree / "target/CACHEDIR.TAG"
    with suppress(OSError):
        return tag.read_text().startswith(CARGO_SIGNATURE)
    return False


def quiet_folders(target: Path) -> bool:
    """No folder in the top two levels of a build folder changed within a day."""
    try:
        level, seen = [target], [target]
        for _ in range(2):
            level = [
                Path(entry.path)
                for folder in level
                for entry in os.scandir(folder)
                if entry.is_dir(follow_symlinks=False)
            ]
            seen += level
        return all(idle(folder.stat().st_mtime) for folder in seen)
    except OSError:
        return False


def hidden_edits(path: Path) -> bool:
    listing = tidy_git(path, "ls-files", "-v")
    return any(not line.startswith("H ") for line in listing.splitlines())


def operation_pending(path: Path) -> bool:
    folder = Path(
        tidy_git(path, "rev-parse", "--path-format=absolute", "--git-dir").strip()
    )
    return any((folder / name).exists() for name in OPERATIONS)


def idle_worktree(path: Path) -> bool:
    """The HEAD log, the top level and every tracked file, submodules too, are a day old; status, fetch and this tidy touch none of them."""
    logged = reflog_time(path, "HEAD")
    listing = tidy_git(path, "ls-files", "-z", "-v", "--recurse-submodules")
    entries = [(r[0], path / r[2:]) for r in listing.split("\0") if r]
    entries += [("H", path / e.name) for e in os.scandir(path) if e.name != ".git"]
    times = []
    for tag, name in entries:
        try:
            times.append(os.lstat(name).st_mtime)
        except FileNotFoundError:
            if tag not in "Ss":
                return False
    return logged is not None and idle(max(times, default=0)) and idle(logged)


def submodules_hold_nothing(path: Path) -> bool:
    listing = tidy_git(path, "submodule", "status", "--recursive")
    for line in listing.splitlines():
        found = SUBMODULE_LINE.fullmatch(line)
        if found is None or found[1] in "+U":
            return False
        if found[1] == "-":
            continue
        inner = path / found[2]
        if (
            tidy_git(
                inner,
                "--no-optional-locks",
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--ignored=matching",
            )
            or tidy_git(inner, "stash", "list")
            or tidy_git(inner, "rev-list", "HEAD", "--branches", "--not", "--remotes")
        ):
            return False
    return True
