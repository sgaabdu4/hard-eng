"""The checks the tidy runs before it removes anything, and the commands they use."""

import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
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
PAUSED_BRANCH_FILES = (
    "rebase-merge/head-name",
    "rebase-apply/head-name",
    "BISECT_START",
)
PRIVATE_FILES = {
    "HEAD",
    "ORIG_HEAD",
    "FETCH_HEAD",
    "COMMIT_EDITMSG",
    "AUTO_MERGE",
    "index",
    "gitdir",
    "commondir",
    "config.worktree",
}
PRIVATE_FOLDERS = {"logs", "refs", "modules", "info"}
PRIVATE_PREFIXES = ("hard-eng", "fsmonitor--daemon", "sharedindex.")
INFO_FILES = {"exclude", "sparse-checkout"}
MODULE_ENTRIES = (
    PRIVATE_FILES
    | PRIVATE_FOLDERS
    | {"config", "description", "hooks", "objects", "packed-refs", "shallow"}
)
OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
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


def fold(path: str | Path) -> str:
    """A path as text that ignores letter case and Unicode form, as macOS volumes do."""
    return unicodedata.normalize("NFC", str(path)).casefold()


def same_place(first: Path, second: Path) -> bool:
    return fold(first) == fold(second)


def under(name: str, folder: str | Path) -> bool:
    place, prefix = fold(name), fold(folder)
    return place == prefix or place.startswith(prefix + os.sep)


def inside(path: Path, names: set[str]) -> bool:
    prefixes = {fold(path), fold(path.resolve())}
    return any(
        folded == prefix or folded.startswith(prefix + os.sep)
        for folded in map(fold, names)
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
    """Assume-unchanged and skip-worktree files can hide edits; a skip-worktree file that is absent is sparse, with nothing to lose."""
    for row in tidy_git(path, "ls-files", "-z", "-v").split("\0"):
        if (
            row
            and row[0] != "H"
            and not (row[0] == "S" and not os.path.lexists(path / row[2:]))
        ):
            return True
    return False


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


def paused_branches(common: Path) -> set[str]:
    """Branches that a rebase or bisect in any worktree will return to, though HEAD is detached now."""
    folders = [common, *sorted((common / "worktrees").glob("*"))]
    found: set[str] = set()
    for folder in folders:
        for name in PAUSED_BRANCH_FILES:
            with suppress(FileNotFoundError, NotADirectoryError):
                found.add(
                    (folder / name).read_text().strip().removeprefix("refs/heads/")
                )
    return found


@dataclass
class Private:
    """What a worktree removal deletes from its own git folder: ref tips, logged refs and submodule git folders."""

    tips: list[str]
    logged: list[str]
    modules: list[Path]


def relative_files(folder: Path) -> list[str]:
    return [
        str((Path(here) / name).relative_to(folder))
        for here, _, names in os.walk(folder)
        for name in names
    ]


def module_folders(modules: Path) -> list[Path]:
    """Git folders below a modules folder, nested ones too; a submodule name may hold slashes."""
    found: list[Path] = []
    for here, names, _ in os.walk(modules):
        if (Path(here) / "HEAD").is_file():
            found.append(Path(here))
            names[:] = [name for name in names if name == "modules"]
    return found


def read_private(gitdir: Path) -> Private | None:
    """None when the folder holds anything that is not known to hold no work."""
    tips: list[str] = []
    for entry in os.scandir(gitdir):
        known = entry.name in PRIVATE_FILES | PRIVATE_FOLDERS
        if not known and not entry.name.startswith(PRIVATE_PREFIXES):
            return None
    if not INFO_FILES >= set(relative_files(gitdir / "info")):
        return None
    files = [gitdir / "ORIG_HEAD"] if (gitdir / "ORIG_HEAD").exists() else []
    files += [gitdir / "refs" / name for name in relative_files(gitdir / "refs")]
    for file in files:
        tip = file.read_text().strip()
        if OBJECT_ID.fullmatch(tip) is None:
            return None
        tips.append(tip)
    logged = [
        name.removeprefix("logs/")
        for name in relative_files(gitdir)
        if name.startswith("logs/")
    ]
    return Private(tips, logged, module_folders(gitdir / "modules"))


def module_holds_work(folder: Path) -> bool:
    """A submodule git folder keeps a commit that no remote branch holds, in a ref, a log or the stash."""
    names = {entry.name for entry in os.scandir(folder)}
    if not names <= MODULE_ENTRIES or any(
        not name.endswith(".sample") for name in relative_files(folder / "hooks")
    ):
        return True
    git_dir = f"--git-dir={folder}"
    commits = set(
        tidy_git(folder, git_dir, "for-each-ref", "--format=%(objectname)").split()
    )
    for name in relative_files(folder / "logs"):
        commits |= set(
            tidy_git(folder, git_dir, "log", "-g", "--format=%H", name).split()
        )
    return bool(
        commits
        and tidy_git(
            folder, git_dir, "rev-list", "--no-walk", *commits, "--not", "--remotes"
        ).split()
    )
