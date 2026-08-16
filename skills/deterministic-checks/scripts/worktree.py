#!/usr/bin/env python3
"""Validate Git checkout readiness, branch state, and copied local inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from checkout_policy import checkout_policy
from git_env import git_env


INTENTS = ("read", "repair", "write", "publish")
BROAD_INCLUDE_PATTERNS = {"*", "**", "/*", "/**", "**/*", "/**/*"}
GLOB_MARKERS = frozenset("*?[")
SETUP_INPUT_NAMES = frozenset(
    {
        "bun.lock",
        "bun.lockb",
        "npm-shrinkwrap.json",
        "package-lock.json",
        "pnpm-lock.yaml",
        "pubspec.lock",
        "pubspec.yaml",
        "yarn.lock",
    }
)
FETCH_TIMEOUT_SECONDS = 60
SETUP_RECEIPT_NAME = "hard-eng-worktree-setup-v1.json"
SETUP_RECEIPT_VERSION = 1
PROJECT_POST_CHECKOUT = """#!/bin/sh
set -eu

global_hooks=$(git config --global --get core.hooksPath)
dispatcher="$global_hooks/post-checkout"
exec "$dispatcher" "$@"
"""


def emit(key: str, value: object) -> None:
    print(f"{key}={str(value).replace(chr(10), ' ').replace(chr(13), ' ')}")


def git(
    repo: Path, *args: str, check: bool = True, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
        env=git_env(),
        timeout=timeout,
    )


def git_root(repo: str) -> Path:
    candidate = Path(repo).expanduser().resolve()
    return Path(git(candidate, "rev-parse", "--show-toplevel").stdout.strip()).resolve()


def git_path(root: Path, name: str) -> Path:
    value = Path(git(root, "rev-parse", name).stdout.strip())
    return (value if value.is_absolute() else root / value).resolve()


def branch(root: Path) -> str:
    result = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    return result.stdout.strip() if result.returncode == 0 else "DETACHED"


def include_entries(root: Path) -> tuple[str, ...]:
    path = root / ".worktreeinclude"
    if not path.is_file():
        return ()
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def literal_entry(entry: str) -> bool:
    return not entry.startswith("!") and not any(marker in entry for marker in GLOB_MARKERS)


def ignored_matches(root: Path, entry: str) -> tuple[str, ...]:
    result = git(root, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--", entry)
    return tuple(path for path in result.stdout.split("\0") if path)


def repository_hook_override(root: Path) -> tuple[Path, str] | None:
    result = git(root, "config", "--local", "--get", "core.hooksPath", check=False)
    value = result.stdout.strip()
    if result.returncode != 0 or not value:
        return None
    path = Path(value).expanduser()
    hooks = path if path.is_absolute() else root / path
    return hooks.resolve(), value


def changed_paths(root: Path) -> tuple[str, ...]:
    paths: set[str] = set()
    for arguments in (
        ("diff", "--name-only", "-z"),
        ("diff", "--cached", "--name-only", "-z"),
        ("ls-files", "--others", "--exclude-standard", "-z"),
    ):
        result = git(root, *arguments)
        paths.update(path for path in result.stdout.split("\0") if path)
    return tuple(sorted(paths))


def repair_paths(root: Path, hook_override: tuple[Path, str] | None) -> set[str]:
    allowed = {
        ".gitignore",
        ".worktreeinclude",
        "scripts/worktree-setup.sh",
        "scripts/worktree-setup.test.mjs",
        "scripts/worktree_setup_test.py",
    }
    if not hook_override:
        return allowed
    hooks, _ = hook_override
    candidates = {hooks / "post-checkout"}
    if hooks.name == "_":
        candidates.add(hooks.parent / "post-checkout")
    for candidate in candidates:
        try:
            allowed.add(candidate.relative_to(root).as_posix())
        except ValueError:
            continue
    return allowed


def canonical_project_post_checkout(path: Path) -> bool:
    try:
        if path.stat().st_size > len(PROJECT_POST_CHECKOUT.encode("utf-8")) + 2:
            return False
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    except (OSError, UnicodeError):
        return False
    return content == PROJECT_POST_CHECKOUT


def setup_input_fingerprint(root: Path) -> str:
    tracked = tuple(
        path
        for path in git(root, "ls-files", "-z").stdout.split("\0")
        if path
    )
    selected = sorted(
        path
        for path in tracked
        if path in {".worktreeinclude", "scripts/worktree-setup.sh"}
        or Path(path).name in SETUP_INPUT_NAMES
    )
    digest = hashlib.sha256()
    for relative in selected:
        path = root / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            mode = stat.S_IMODE(path.lstat().st_mode)
            content = path.read_bytes()
        except OSError:
            mode = 0
            content = b"<missing>"
        digest.update(f"{mode:o}".encode("ascii"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def setup_receipt_path(git_dir: Path) -> Path:
    return git_dir / SETUP_RECEIPT_NAME


def setup_receipt_current(receipt: Path, root: Path, fingerprint: str) -> bool:
    try:
        if receipt.is_symlink() or not receipt.is_file():
            return False
        if stat.S_IMODE(receipt.stat().st_mode) & 0o077:
            return False
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return payload == {
        "version": SETUP_RECEIPT_VERSION,
        "repository_root": str(root),
        "input_fingerprint": fingerprint,
    }


def write_setup_receipt(receipt: Path, root: Path, fingerprint: str) -> None:
    payload = {
        "version": SETUP_RECEIPT_VERSION,
        "repository_root": str(root),
        "input_fingerprint": fingerprint,
    }
    temporary = receipt.with_name(f".{receipt.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, receipt)
        receipt.chmod(0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def setup_path_dirty(root: Path) -> bool:
    for arguments in (
        ("diff", "--quiet", "--", "scripts/worktree-setup.sh"),
        ("diff", "--cached", "--quiet", "--", "scripts/worktree-setup.sh"),
    ):
        if git(root, *arguments, check=False).returncode != 0:
            return True
    return False


def ensure_setup_receipt(
    root: Path,
    git_dir: Path,
    setup_path: Path,
) -> tuple[str, str | None]:
    receipt = setup_receipt_path(git_dir)
    fingerprint = setup_input_fingerprint(root)
    if setup_receipt_current(receipt, root, fingerprint):
        return "current", None
    if setup_path_dirty(root):
        return "stale", "worktree setup changed; run its focused repair proof before provisioning"

    tracked_before = git(root, "status", "--short", "--untracked-files=no").stdout
    runner = SCRIPT_DIR / "bounded_run.py"
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(runner),
                "--timeout",
                "1200",
                "--cwd",
                str(root),
                "--",
                str(setup_path),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=1260,
            env=git_env(),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "failed", f"worktree setup could not complete: {type(exc).__name__}"
    if result.returncode != 0:
        return "failed", f"worktree setup failed with exit {result.returncode}"
    tracked_after = git(root, "status", "--short", "--untracked-files=no").stdout
    if tracked_after != tracked_before:
        return "failed", "worktree setup changed tracked files"

    fingerprint = setup_input_fingerprint(root)
    try:
        write_setup_receipt(receipt, root, fingerprint)
    except OSError as exc:
        return "failed", f"worktree setup receipt write failed: {type(exc).__name__}"
    if not setup_receipt_current(receipt, root, fingerprint):
        return "failed", "worktree setup receipt verification failed"
    return "provisioned", None


def non_private_include_modes(root: Path, entries: tuple[str, ...]) -> tuple[str, ...]:
    violations: list[str] = []
    for entry in entries:
        if not literal_entry(entry):
            continue
        path = root / entry.lstrip("/")
        try:
            if path.is_symlink() or not path.is_file():
                violations.append(entry)
                continue
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                violations.append(entry)
        except OSError:
            violations.append(entry)
    return tuple(violations)


def privatize_included_inputs(root: Path, entries: tuple[str, ...]) -> str | None:
    for entry in entries:
        if not literal_entry(entry):
            continue
        path = root / entry.lstrip("/")
        try:
            if path.is_symlink() or not path.is_file():
                return f"worktree included input is not a regular file: {entry}"
            if stat.S_IMODE(path.stat().st_mode) & 0o077:
                path.chmod(0o600)
        except OSError as exc:
            return (
                f"worktree included input could not be made private: "
                f"{entry}:{type(exc).__name__}"
            )
    return None


def behind_upstream(root: Path) -> str | None:
    """Whether this branch still trails what it is about to be pushed onto.

    A push that is not a fast-forward either fails or lands a merge nobody asked
    for, and only a fresh fetch can answer that: a remote-tracking ref answers the
    question the last fetch asked, not this one.
    """
    remotes = [name for name in git(root, "remote", check=False).stdout.split() if name]
    if not remotes:
        return "publish currency is unknown because no remote is configured"
    tracking = git(
        root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}", check=False
    )
    ref = tracking.stdout.strip() if tracking.returncode == 0 else ""
    remote = ref.split("/", 1)[0] if ref else ("origin" if "origin" in remotes else remotes[0])
    try:
        fetched = git(root, "fetch", "--quiet", remote, check=False, timeout=FETCH_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return f"git fetch {remote} did not finish, so being current with it is unproven"
    if fetched.returncode != 0:
        detail = (fetched.stderr or fetched.stdout).strip().splitlines()
        return (
            f"git fetch {remote} failed, so being current with it is unproven: "
            + (detail[-1] if detail else f"exit {fetched.returncode}")
        )
    if not ref:
        # No upstream yet: the branch is still going onto the remote's default.
        ref = git(
            root, "symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD", check=False
        ).stdout.strip()
    if not ref:
        return f"publish currency is unknown because {remote} has no default branch"
    counted = git(root, "rev-list", "--left-right", "--count", f"HEAD...{ref}", check=False)
    values = counted.stdout.split()
    if counted.returncode != 0 or len(values) != 2 or not all(value.isdigit() for value in values):
        return f"publish currency is unknown because comparison with {ref} failed"
    ahead, behind = (int(value) for value in values)
    if behind == 0:
        return None
    if ahead:
        return (
            f"branch has diverged from {ref}: rebase onto it before pushing "
            f"(git fetch {remote} && git rebase {ref})"
        )
    return (
        f"branch is {behind} commit(s) behind {ref}: "
        f"rebase onto it before pushing (git fetch {remote} && git rebase {ref})"
    )


def inspect(repo: str, intent: str, checkout_choice: str = "auto") -> int:
    try:
        root = git_root(repo)
        git_dir = git_path(root, "--git-dir")
        common_dir = git_path(root, "--git-common-dir")
        current_branch = branch(root)
        head_result = git(root, "rev-parse", "--verify", "HEAD", check=False)
        head = head_result.stdout.strip() if head_result.returncode == 0 else "UNBORN"
        dirty = tuple(
            record
            for record in git(
                root, "status", "--porcelain=v1", "-z", "--untracked-files=all"
            ).stdout.split("\0")
            if record
        )
        entries = include_entries(root)
        policy = checkout_policy(root)
        hook_override = repository_hook_override(root)
    except (FileNotFoundError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        emit("result", "invalid")
        emit("error_1", f"repository preflight failed: {exc}")
        return 4

    isolated = git_dir != common_dir
    errors: list[str] = []
    if policy == "primary-only" and isolated:
        errors.append("repository policy forbids linked worktrees")
    broad = tuple(entry for entry in entries if entry in BROAD_INCLUDE_PATTERNS)
    if broad:
        errors.append("broad .worktreeinclude pattern forbidden: " + ",".join(broad))
    unsafe = tuple(
        entry for entry in entries
        if entry.startswith(("!", "/", "./", ":"))
        or entry in ("..", ".")
        or entry.startswith("../")
        or "/../" in entry
        or entry.endswith(("/..", "/."))
        or "/./" in entry
    )
    if unsafe:
        errors.append("unsafe .worktreeinclude entry forbidden: " + ",".join(unsafe))
    include_path = root / ".worktreeinclude"
    if include_path.exists() and git(
        root, "ls-files", "--error-unmatch", "--", ".worktreeinclude", check=False
    ).returncode != 0:
        errors.append(".worktreeinclude must be tracked in the selected starting state")

    setup_path = root / "scripts/worktree-setup.sh"
    setup_exists = setup_path.exists() or setup_path.is_symlink()
    if setup_exists and (
        not setup_path.is_file()
        or setup_path.is_symlink()
        or not os.access(setup_path, os.X_OK)
        or git(
            root,
            "ls-files",
            "--error-unmatch",
            "--",
            "scripts/worktree-setup.sh",
            check=False,
        ).returncode
        != 0
    ):
        errors.append("worktree setup must be a tracked regular executable")

    missing = tuple(
        entry
        for entry in entries
        if literal_entry(entry) and not (root / entry.lstrip("/")).exists()
    )
    tracked = tuple(
        entry
        for entry in entries
        if literal_entry(entry)
        and git(root, "ls-files", "--error-unmatch", "--", entry.lstrip("/"), check=False).returncode == 0
    )
    unmatched_globs = tuple(
        entry for entry in entries
        if not literal_entry(entry) and entry not in unsafe and not ignored_matches(root, entry)
    )
    if hook_override and (entries or setup_exists):
        hooks, configured_hooks = hook_override
        post_checkout = hooks / "post-checkout"
        try:
            relative_hook = post_checkout.relative_to(root).as_posix()
        except ValueError:
            relative_hook = ""
        tracked_hook = bool(relative_hook) and git(
            root, "ls-files", "--error-unmatch", "--", relative_hook, check=False
        ).returncode == 0
        included_hook = bool(relative_hook) and any(
            relative_hook in ignored_matches(root, entry) for entry in entries
        )
        if included_hook and not tracked_hook:
            errors.append(
                "ignored hook-manager runtime must be rebuilt by worktree setup, "
                "not copied through .worktreeinclude"
            )
        delegation_owner = post_checkout
        if not tracked_hook:
            candidate_owner = hooks.parent / "post-checkout"
            try:
                candidate_relative = candidate_owner.relative_to(root).as_posix()
            except ValueError:
                candidate_relative = ""
            if bool(candidate_relative) and git(
                root,
                "ls-files",
                "--error-unmatch",
                "--",
                candidate_relative,
                check=False,
            ).returncode == 0:
                delegation_owner = candidate_owner
        try:
            relative_owner = delegation_owner.relative_to(root).as_posix()
        except ValueError:
            relative_owner = ""
        tracked_owner = bool(relative_owner) and git(
            root, "ls-files", "--error-unmatch", "--", relative_owner, check=False
        ).returncode == 0
        ignored_runtime = bool(relative_hook) and git(
            root, "check-ignore", "-q", "--", relative_hook, check=False
        ).returncode == 0
        managed_runtime = ignored_runtime and tracked_owner and setup_exists
        valid_hook_owner = (
            post_checkout.is_file()
            and not post_checkout.is_symlink()
            and os.access(post_checkout, os.X_OK)
            and (tracked_hook or managed_runtime)
            and (tracked_hook or tracked_owner)
        )
        if not valid_hook_owner:
            errors.append(
                "repository core.hooksPath override requires a tracked or included "
                f"executable post-checkout hook: {configured_hooks}"
            )
        elif not canonical_project_post_checkout(delegation_owner):
            errors.append(
                "repository post-checkout must delegate to the global post-checkout dispatcher"
            )
    choice_required = (
        intent == "write" and policy != "primary-only" and not isolated
        and bool(dirty) and checkout_choice != "current"
    )
    if missing:
        errors.append("required .worktreeinclude paths missing: " + ",".join(missing))
    if tracked:
        errors.append("tracked paths forbidden in .worktreeinclude: " + ",".join(tracked))
    if unmatched_globs:
        errors.append(".worktreeinclude patterns matched no ignored files: " + ",".join(unmatched_globs))

    setup_receipt = "not-required"
    if isolated and intent in {"write", "publish"} and not errors:
        private_error = privatize_included_inputs(root, entries)
        if private_error:
            errors.append(private_error)
    if isolated and intent in {"write", "publish"} and setup_exists and not errors:
        setup_receipt, setup_error = ensure_setup_receipt(root, git_dir, setup_path)
        if setup_error:
            errors.append(setup_error)
    if isolated and intent in {"write", "publish"} and not errors:
        insecure_inputs = non_private_include_modes(root, entries)
        if insecure_inputs:
            errors.append(
                "worktree included inputs must be private regular files: "
                + ",".join(insecure_inputs)
            )
    if intent == "publish" and current_branch == "DETACHED":
        errors.append("commit/push requires a dedicated named branch")
    if intent == "publish" and head == "UNBORN":
        errors.append("commit/push requires an existing starting commit")
    if intent == "publish" and not errors:
        stale = behind_upstream(root)
        if stale:
            errors.append(stale)

    repair_issues: tuple[str, ...] = ()
    if intent == "repair":
        repair_issues = tuple(errors)
        forbidden = tuple(
            path for path in changed_paths(root)
            if path not in repair_paths(root, hook_override)
        )
        errors = (
            ["worktree repair has out-of-scope changes: " + ",".join(forbidden)]
            if forbidden
            else []
        )
    result = "invalid" if errors else "choice-required" if choice_required else "valid"
    emit("result", result)
    emit("repository_root", root)
    emit("worktree", "isolated" if isolated else "primary")
    emit("checkout_policy", policy)
    emit("branch", current_branch)
    emit("head_sha", head)
    emit("dirty_count", len(dirty))
    emit("starting_state", "dirty" if dirty else "clean")
    emit("worktreeinclude", "present" if entries else "absent")
    emit("included_path_count", len(entries))
    emit("setup_receipt", setup_receipt)
    emit("codex_session", "yes" if os.environ.get("CODEX_THREAD_ID") else "no")
    if choice_required:
        emit("choice", "continue current checkout OR create new worktree")
    for index, issue in enumerate(repair_issues, start=1):
        emit(f"repair_issue_{index}", issue)
    for index, error in enumerate(errors, start=1):
        emit(f"error_{index}", error)
    return 4 if errors else 3 if choice_required else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--intent", choices=INTENTS, default="read")
    parser.add_argument("--checkout-choice", choices=("auto", "current"), default="auto")
    args = parser.parse_args()
    return inspect(args.repo, args.intent, args.checkout_choice)


if __name__ == "__main__":
    sys.exit(main())
