"""Remove what an ended update or push check left behind: candidate worktrees and temporary folders."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

OWNER = re.compile(r"hard-eng-update (\d+)")
TEMPORARY = re.compile(
    r"hard-eng-(?:update|push|gate|gitleaks|dart-parser|scaffold-check|mutation)-[a-z0-9_]{8}"
)
WORKTREE = re.compile(r"hard-eng-(?:update-.+/candidate|push-.+/project)")


def alive(process: int) -> bool:
    try:
        os.kill(process, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def abandoned(path: Path, owner: re.Match[str] | None) -> bool:
    """Updaters before the lock ran under a one-hour hook, and a push's checks end within a day."""
    if owner is not None:
        return not alive(int(owner[1]))
    hours = 6 if path.name == "candidate" else 24
    try:
        return time.time() - path.parent.stat().st_mtime > hours * 3600
    except FileNotFoundError:
        return False


def sweep_temporary() -> None:
    """Directories a killed Hard Eng process left behind; none of its runs lasts a day."""
    for path in Path(tempfile.gettempdir()).iterdir():
        with suppress(OSError):
            if (
                TEMPORARY.fullmatch(path.name)
                and path.is_dir()
                and not path.is_symlink()
                and time.time() - path.stat().st_mtime > 24 * 3600
            ):
                shutil.rmtree(path)


def idle(stamp: float) -> bool:
    """Nothing touched the thing for a day."""
    return time.time() - stamp > 24 * 3600


def stop_idle_watcher(worktree: Path) -> None:
    """Git restarts a file watcher on the next command, so stopping an idle one loses nothing."""
    with suppress(OSError, subprocess.SubprocessError):
        index = subprocess.check_output(
            ["git", "rev-parse", "--path-format=absolute", "--git-path", "index"],
            cwd=worktree,
            text=True,
            timeout=30,
        ).strip()
        if idle(Path(index).stat().st_mtime):
            subprocess.run(
                ["git", "fsmonitor--daemon", "stop"],
                cwd=worktree,
                capture_output=True,
                timeout=30,
                check=False,
            )


def remove_stale_candidates(root: Path) -> None:
    """Remove candidates whose update has exited; the caller holds the lock."""
    from ship_actions import worktrees

    for fields in worktrees(root):
        path = Path(fields.get("worktree", ""))
        owner = OWNER.fullmatch(fields.get("locked", ""))
        if not WORKTREE.fullmatch(f"{path.parent.name}/{path.name}"):
            if path.is_dir() and path.resolve() != root.resolve():
                stop_idle_watcher(path)
            continue
        if not abandoned(path, owner):
            continue
        if owner is not None and not path.exists():
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
    sweep_temporary()
    subprocess.run(["git", "worktree", "prune"], cwd=root, check=True, timeout=60)


PROTECTED_BRANCHES = {"main", "master", "develop", "hard-eng/update"}
GENERATED_FOLDERS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
CARGO_SIGNATURE = "Signature: 8a477f597d28d172789f06886806bc55"
STASH_SUBJECT = re.compile(r"(?:WIP on|On) ([^:]+):")
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
    cwd: Path, limit: float, *command: str
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
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


def tidy_gh(cwd: Path, *arguments: str) -> list[object] | None:
    """The JSON list gh printed, or None when gh gave no usable answer."""
    try:
        done = tidy_run(cwd, 60, "gh", *arguments)
        found = json.loads(done.stdout) if done.returncode == 0 else None
    except (TidyStop, ValueError):
        return None
    return found if isinstance(found, list) else None


def fetch_tip(root: Path, base: str) -> str:
    """The base tip that origin reported, once its objects are here; no shared FETCH_HEAD."""
    rows = tidy_git(root, "ls-remote", "origin", f"refs/heads/{base}").split()
    if len(rows) != 2:
        raise TidyStop(f"origin has no unique branch {base}")
    tidy_git(root, "fetch", "--quiet", "--no-tags", "origin", base)
    tidy_git(root, "cat-file", "-e", f"{rows[0]}^{{commit}}")
    return rows[0]


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


@dataclass
class Tidy:
    root: Path
    session: Path
    base: str
    tip: str
    repository: str | None
    on_origin: set[str]
    protected: set[str]
    removed: Counter[str]

    @classmethod
    def open(cls, root: Path, removed: Counter[str]) -> "Tidy":
        from shipping import ShippingError, origin_repository
        from update_runner import update_base

        try:
            base = update_base(root)
            tip = fetch_tip(root, base)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise TidyStop(f"fetch of the base branch failed: {error}") from error
        try:
            repository = origin_repository(
                tidy_git(root, "config", "--get", "remote.origin.url").strip()
            )
        except ShippingError:
            repository = None
        heads = tidy_git(root, "ls-remote", "--heads", "origin")
        on_origin = {
            line.split("\t")[1].removeprefix("refs/heads/")
            for line in heads.splitlines()
            if "\t" in line
        }
        default = tidy_run(
            root, 120, "git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"
        )
        named = default.stdout.strip().removeprefix("origin/")
        return cls(
            root,
            root.resolve(),
            base,
            tip,
            repository,
            on_origin,
            {*PROTECTED_BRANCHES, base, named},
            removed,
        )

    def content_merged(self, head: str) -> bool:
        """Merging the head into the base tip changes nothing, so the base holds every change."""
        done = tidy_run(
            self.root, 120, "git", "merge-tree", "--write-tree", self.tip, head
        )
        if done.returncode == 1:
            return False
        if done.returncode:
            raise TidyStop(f"`git merge-tree` exited {done.returncode}")
        tree = tidy_git(self.root, "rev-parse", f"{self.tip}^{{tree}}").strip()
        return done.stdout.split()[0] == tree

    def reflog_holds_work(self, cwd: Path, head: str, *refs: str) -> bool:
        """A removal drops the logs; keep an item whose log names a commit that is merged nowhere."""
        commits: set[str] = set()
        for ref in refs:
            commits |= set(tidy_git(cwd, "log", "-g", "--format=%H", ref).split())
        if not commits:
            return False
        unmerged = tidy_git(
            self.root,
            "rev-list",
            "--no-walk",
            *commits,
            "--not",
            self.tip,
            head,
            "--remotes",
        ).split()
        return not all(self.content_merged(commit) for commit in unmerged)

    def hidden_edits(self, path: Path) -> bool:
        listing = tidy_git(path, "ls-files", "-v")
        return any(not line.startswith("H ") for line in listing.splitlines())

    def operation_pending(self, path: Path) -> bool:
        folder = Path(
            tidy_git(path, "rev-parse", "--path-format=absolute", "--git-dir").strip()
        )
        return any((folder / name).exists() for name in OPERATIONS)

    def merged(self, head: str, branch: str | None) -> bool:
        ancestor = tidy_run(
            self.root, 120, "git", "merge-base", "--is-ancestor", head, self.tip
        ).returncode
        if ancestor not in {0, 1}:
            raise TidyStop("`git merge-base` failed")
        if ancestor == 0:
            return True
        if self.content_merged(head):
            return True
        if branch is None or self.repository is None:
            return False
        pulls = tidy_gh(
            self.root,
            "pr",
            "list",
            "--repo",
            self.repository,
            "--state",
            "merged",
            "--head",
            branch,
            "--base",
            self.base,
            "--json",
            "headRefOid",
        )
        return any(
            isinstance(pull, dict) and pull.get("headRefOid") == head
            for pull in pulls or []
        )

    def open_pr(self, branch: str) -> bool:
        """True when the branch has an open PR, or when no answer can say that it has none."""
        if branch not in self.on_origin:
            return False
        if self.repository is None:
            return True
        pulls = tidy_gh(
            self.root,
            "pr",
            "list",
            "--repo",
            self.repository,
            "--state",
            "open",
            "--head",
            branch,
            "--json",
            "number",
        )
        return pulls is None or bool(pulls)

    def stashed(self, branch: str | None, head: str | None) -> bool:
        listing = tidy_git(self.root, "stash", "list", "--format=%P%x09%gs")
        for line in listing.splitlines():
            parents, _, subject = line.partition("\t")
            parent = parents.split(" ")[0]
            named = STASH_SUBJECT.match(subject)
            if (head is not None and parent == head) or (
                branch is not None and named is not None and named[1] == branch
            ):
                return True
        return False

    def idle_worktree(self, path: Path) -> bool:
        index = tidy_git(
            path, "rev-parse", "--path-format=absolute", "--git-path", "index"
        ).strip()
        logged = reflog_time(path, "HEAD")
        try:
            used = Path(index).stat().st_mtime
        except OSError:
            return False
        return logged is not None and idle(used) and idle(logged)

    def submodules_hold_nothing(self, path: Path) -> bool:
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
                or tidy_git(
                    inner, "rev-list", "HEAD", "--branches", "--not", "--remotes"
                )
            ):
                return False
        return True

    def worktree_busy(self, path: Path) -> bool:
        names = open_paths()
        return names is None or inside(path, names)

    def worktree_reason(
        self, record: dict[str, str], main: Path, first: bool
    ) -> str | None:
        from ship_actions import work_left

        path = Path(record.get("worktree", ""))
        branch = record.get("branch", "").removeprefix("refs/heads/") or None
        head = record.get("HEAD", "")
        if (
            first
            or "bare" in record
            or "locked" in record
            or "prunable" in record
            or not path.is_dir()
        ):
            return "primary, bare, locked or missing"
        if path.resolve() == self.session:
            return "the session's worktree"
        if path.resolve().is_relative_to(codex_folder()):
            return "kept by the Codex app"
        checks: list[tuple[str, Callable[[], bool]]] = [
            ("used in the last 24 hours", lambda: not self.idle_worktree(path)),
            ("not merged", lambda: not self.merged(head, branch)),
            ("a stash names it", lambda: self.stashed(branch, head)),
            (
                "its branch has an open PR or no PR answer",
                lambda: branch is not None and self.open_pr(branch),
            ),
            (
                "its log holds commits that are merged nowhere",
                lambda: self.reflog_holds_work(
                    path,
                    head,
                    "HEAD",
                    *([f"refs/heads/{branch}"] if branch else []),
                ),
            ),
            ("holds changes", lambda: bool(work_left(path, main, generated(path)))),
            (
                "hidden edits (assume-unchanged or skip-worktree)",
                lambda: self.hidden_edits(path),
            ),
            (
                "a rebase, merge, bisect, pick or revert is in progress",
                lambda: self.operation_pending(path),
            ),
            ("a submodule holds work", lambda: not self.submodules_hold_nothing(path)),
            ("a process is inside", lambda: self.worktree_busy(path)),
        ]
        return next((reason for reason, kept in checks if kept()), None)

    def remove_worktree(self, path: str, first: bool) -> None:
        from ship_actions import worktrees

        fresh = worktrees(self.root)
        main = Path(fresh[0]["worktree"])
        record = next((r for r in fresh if r.get("worktree") == path), None)
        if record is None:
            return
        reason = self.worktree_reason(record, main, first)
        if reason is not None:
            if not reason.startswith(("primary", "the session")):
                note(f"kept worktree {path}: {reason}")
            return
        now = next(
            (r for r in worktrees(self.root) if r.get("worktree") == path),
            dict[str, str](),
        )
        if (now.get("HEAD"), now.get("branch")) != (
            record.get("HEAD"),
            record.get("branch"),
        ):
            note(
                f"kept worktree {path}: its branch or commit changed during the checks"
            )
            return
        tidy_git(self.root, "worktree", "remove", "--force", path)
        note(f"removed worktree {path} at {record.get('HEAD')} (merged, idle, clean)")
        self.removed["worktrees"] += 1

    def remove_worktrees(self) -> None:
        """A failure on one worktree keeps it and goes on; a failed listing stops the repository."""
        from ship_actions import worktrees

        for index, first in enumerate(worktrees(self.root)):
            path = first.get("worktree", "")
            try:
                self.remove_worktree(path, index == 0)
            except ITEM_ERRORS as error:
                note(f"kept worktree {path}: {error}")

    def branch_reason(self, name: str, tip: str, checked_out: set[str]) -> str | None:
        logged = reflog_time(self.root, f"refs/heads/{name}")
        checks: list[tuple[str, Callable[[], bool]]] = [
            ("protected", lambda: name in self.protected),
            ("checked out", lambda: name in checked_out),
            (
                "used in the last 24 hours or no log",
                lambda: logged is None or not idle(logged),
            ),
            ("not merged", lambda: not self.merged(tip, name)),
            ("a stash names it", lambda: self.stashed(name, None)),
            (
                "its log holds commits that are merged nowhere",
                lambda: self.reflog_holds_work(self.root, tip, f"refs/heads/{name}"),
            ),
            ("open PR or no PR answer", lambda: self.open_pr(name)),
        ]
        return next((reason for reason, kept in checks if kept()), None)

    def checked_out(self) -> set[str]:
        from ship_actions import worktrees

        return {
            record.get("branch", "").removeprefix("refs/heads/")
            for record in worktrees(self.root)
        }

    def remove_branch(self, line: str) -> None:
        tip, _, ref = line.partition(" ")
        name = ref.removeprefix("refs/heads/")
        reason = self.branch_reason(name, tip, self.checked_out())
        if reason is None and name in self.checked_out():
            reason = "checked out"
        if reason is not None:
            if reason not in {"protected", "checked out"}:
                note(f"kept branch {name}: {reason}")
            return
        tidy_git(self.root, "update-ref", "-d", ref, tip)
        note(f"removed branch {name} at {tip} (merged, idle)")
        self.removed["branches"] += 1

    def remove_branches(self) -> None:
        """A failure on one branch keeps it and goes on; a failed listing stops the repository."""
        listing = tidy_git(
            self.root, "for-each-ref", "--format=%(objectname) %(refname)", "refs/heads"
        )
        for line in listing.splitlines():
            try:
                self.remove_branch(line)
            except ITEM_ERRORS as error:
                note(f"kept branch {line.partition(' ')[2]}: {error}")

    def target_reason(self, path: Path) -> str | None:
        target = path / "target"
        checks: list[tuple[str, Callable[[], bool]]] = [
            (
                "no cargo build folder",
                lambda: not (path / "Cargo.toml").is_file() or not cargo_target(path),
            ),
            (
                "git does not ignore it",
                lambda: (
                    tidy_run(
                        path, 120, "git", "check-ignore", "-q", "target"
                    ).returncode
                    != 0
                ),
            ),
            (
                "git tracks files in it",
                lambda: bool(tidy_git(path, "ls-files", "--", "target").strip()),
            ),
            (
                "worktree used in the last 24 hours",
                lambda: not self.idle_worktree(path),
            ),
            (
                "build folder changed in the last 24 hours",
                lambda: not quiet_folders(target),
            ),
            ("a process is inside", lambda: self.worktree_busy(path)),
        ]
        return next((reason for reason, kept in checks if kept()), None)

    def trim_target(self, record: dict[str, str]) -> None:
        path = Path(record.get("worktree", ""))
        if (
            "bare" in record
            or "prunable" in record
            or not path.is_dir()
            or path.resolve() == self.session
        ):
            return
        reason = self.target_reason(path)
        if reason is None:
            shutil.rmtree(path / "target")
            note(f"removed build folder {path / 'target'} (idle cargo target)")
            self.removed["build folders"] += 1
        elif not reason.startswith("no cargo"):
            note(f"kept build folder {path / 'target'}: {reason}")

    def trim_targets(self) -> None:
        """A failure on one build folder keeps it and goes on; a failed listing stops the repository."""
        from ship_actions import worktrees

        for record in worktrees(self.root):
            try:
                self.trim_target(record)
            except ITEM_ERRORS as error:
                note(f"kept build folder of {record.get('worktree')}: {error}")

    def run(self) -> None:
        self.remove_worktrees()
        self.remove_branches()
        self.trim_targets()


def tidy(root: Path) -> None:
    """Remove merged idle worktrees and branches and idle cargo build folders. One item that fails is kept and the next goes on; a failure for the whole repository stops it."""
    from update_runner import LOG_FILE, RESULT_FILE, exclusive

    removed: Counter[str] = Counter()
    with (common_dir(root) / "hard-eng-tidy.lock").open("a") as handle:
        if not exclusive(handle):
            note("skipped: another tidy is running")
            return
        try:
            Tidy.open(root, removed).run()
        except (TidyStop, OSError, ValueError, subprocess.SubprocessError) as error:
            note(
                f"stopped for this repository, what is not yet removed is kept: {error}"
            )
    if removed:
        result = root / RESULT_FILE
        result.parent.mkdir(parents=True, exist_ok=True)
        counts = ", ".join(
            f"{removed[kind]} {kind}"
            for kind in ("worktrees", "branches", "build folders")
        )
        with result.open("a") as out:
            out.write(f"Tidy: removed {counts} ({LOG_FILE}).\n")


MARKER = "# Hard Eng worktree launcher, local to this checkout"


def git_run(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, text=True, check=False
    )


def common_dir(root: Path) -> Path:
    found = git_run(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(found.stdout.strip()).resolve()


def worktree_place(root: Path, target: Path) -> tuple[str, str, Path]:
    """Where a hook file sits: in Git's folder, tracked, ignored or loose in the main checkout, or elsewhere."""
    common = common_dir(root)
    place = target.resolve()
    main = common.parent
    if place.is_relative_to(common):
        return "git", "", main
    folder = next(path for path in place.parents if path.is_dir())
    top = git_run(folder, "rev-parse", "--show-toplevel").stdout.strip()
    if common.name != ".git" or not top or Path(top).resolve() != main:
        return "elsewhere", "", main
    name = place.relative_to(main).as_posix()
    if git_run(main, "ls-files", "--error-unmatch", "--", name).returncode == 0:
        return "tracked", name, main
    if git_run(main, "check-ignore", "-q", "--", name).returncode == 0:
        return "ignored", name, main
    return "loose", name, main


def committed_bytes(root: Path, name: str) -> bytes | None:
    revision = "HEAD:" + name
    shown = subprocess.run(
        ["git", "show", revision], cwd=root, capture_output=True, check=False
    )
    return None if shown.returncode else shown.stdout


def exclude_file(root: Path) -> Path:
    found = git_run(
        root, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude"
    )
    return Path(found.stdout.strip())


def hide(root: Path, name: str) -> None:
    """Keep the loose launcher out of status once the install commit holds the source file."""
    from gate_config import SOURCE_FILE

    exclude = exclude_file(root)
    text = exclude.read_text() if exclude.is_file() else ""
    line = "/" + name
    if line in text.splitlines() or committed_bytes(root, SOURCE_FILE) is None:
        return
    exclude.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if not text or text.endswith("\n") else "\n"
    with exclude.open("a") as handle:
        handle.write(f"{separator}{MARKER}\n{line}\n")


def unhide(root: Path, name: str) -> None:
    """Remove the exclude line that hide wrote, and only that one."""
    exclude = exclude_file(root)
    if not exclude.is_file():
        return
    lines = exclude.read_text().splitlines(keepends=True)
    for index in range(1, len(lines)):
        if (
            lines[index].rstrip("\r\n") == "/" + name
            and lines[index - 1].rstrip("\r\n") == MARKER
        ):
            del lines[index - 1 : index + 1]
            exclude.write_text("".join(lines))
            return


def give_back(root: Path, target: Path, name: str) -> None:
    """Restore the tracked hook that a rerun replaced, when its kept copy still equals the committed hook."""
    import hook_chain

    copy = hook_chain.project_copy(target)
    committed = committed_bytes(root, name)
    mode = git_run(root, "ls-tree", "HEAD", "--", name).stdout.split(" ", 1)[0]
    if (
        committed is None
        or mode not in {"100644", "100755"}
        or copy.is_symlink()
        or not copy.is_file()
        or copy.read_bytes() != committed
        or git_run(
            root, "ls-files", "--error-unmatch", "--", copy.relative_to(root).as_posix()
        ).returncode
        == 0
        or not (hook_chain.is_own(root, target) or target.read_bytes() == committed)
    ):
        return
    target.unlink(missing_ok=True)
    target.write_bytes(committed)
    target.chmod(0o755 if mode == "100755" else 0o644)
    copy.unlink()


def without_launchers(
    root: Path, shared: list[dict[str, list[str]]], listed: set[str]
) -> None:
    """Take the launchers that the committed gates file does not list out of each shellcheck command."""
    import hook_chain

    for gate in list(shared):
        command = gate["command"]
        if Path(command[0]).name != "shellcheck" or "--" not in command:
            continue
        gate["command"] = [
            part
            for part in command
            if part in listed or not hook_chain.is_own(root, root / part)
        ]
        if gate["command"] != command and gate["command"][-1] == "--":
            shared.remove(gate)


def drop_launcher_entries(root: Path) -> None:
    """Undo a rerun that listed Hard Eng's launcher in the shell gate, when nothing else in the file changed."""
    import json

    gates = root / "hard-eng.gates.json"
    committed = committed_bytes(root, gates.name)
    if (
        committed is None
        or gates.is_symlink()
        or not gates.is_file()
        or gates.read_bytes() == committed
    ):
        return
    try:
        config, head = json.loads(gates.read_bytes()), json.loads(committed)
        listed = {part for gate in head["shared"] for part in gate["command"]}
        without_launchers(root, config["shared"], listed)
    except (ValueError, KeyError, TypeError, IndexError):
        return
    if config == head:
        gates.write_bytes(committed)


def settle_main(main: Path, own: bool) -> None:
    import hook_chain

    target = hook_chain.locate(main, "post-checkout")[1]
    place, name, _ = worktree_place(main, target)
    if place == "loose" and hook_chain.is_own(main, target):
        hide(main, name)
    elif (
        place == "ignored" and target.is_file() and not hook_chain.is_own(main, target)
    ):
        unhide(main, name)
    elif place == "tracked" and own:
        give_back(main, target, name)
    if own:
        drop_launcher_entries(main)


def settle_worktree_hook(root: Path) -> None:
    """Undo what an earlier setup rerun left in a hooks folder inside the main checkout."""
    common = common_dir(root)
    if common.name != ".git":
        return
    try:
        settle_main(common.parent, common.parent == root.resolve())
    except (ValueError, OSError, subprocess.SubprocessError):
        return
