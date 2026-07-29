#!/usr/bin/env python3
"""Regression coverage for terminal lifecycle status exclusions."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
GIT_ENV_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env
from lifecycle_excludes import LifecycleExcludeError, exclude_terminal_artifacts

sys.dont_write_bytecode = True


def run(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=git_env(),
    )
    if check and result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def run_plan_state(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "plan_state.py"), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
        env=git_env(),
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def status(repo: Path) -> set[str]:
    return set(
        filter(
            None,
            run(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout.splitlines(),
        )
    )


def git_path(repo: Path, *arguments: str) -> Path:
    value = run(repo, "rev-parse", *arguments).stdout.strip()
    path = Path(value)
    return (path if path.is_absolute() else repo / path).resolve()


def main() -> int:
    parent = "/tmp" if sys.platform == "darwin" else None
    with tempfile.TemporaryDirectory(prefix="hard-eng-excludes-", dir=parent) as raw:
        root = Path(raw).resolve()
        primary = root / "primary"
        linked = root / "linked"
        alias = root / "linked-alias"
        primary.mkdir()
        run(primary, "init", "-q")
        run(primary, "config", "user.email", "hard-eng@example.invalid")
        run(primary, "config", "user.name", "Hard Eng")
        write(primary / "README.md", "fixture\n")
        write(primary / "features/tracked/PLAN.md", "tracked\n")
        run(primary, "add", ".")
        run(primary, "commit", "-qm", "fixture")
        run(primary, "worktree", "add", "-q", "-b", "linked", str(linked))
        alias.symlink_to(linked, target_is_directory=True)

        if (linked / ".git").is_dir() or not (linked / ".git").is_file():
            raise AssertionError("linked worktree .git must be handled as a file")
        primary_common = git_path(primary, "--git-common-dir")
        linked_common = git_path(alias, "--git-common-dir")
        primary_exclude = git_path(primary, "--git-path", "info/exclude")
        linked_exclude = git_path(alias, "--git-path", "info/exclude")
        if primary_common != linked_common or primary_exclude != linked_exclude:
            raise AssertionError(
                "linked worktree Git paths differ: "
                f"primary_common={primary_common}, linked_common={linked_common}, "
                f"primary_exclude={primary_exclude}, linked_exclude={linked_exclude}"
            )
        with primary_exclude.open("ab") as stream:
            stream.write(b"\xff\n")

        initialized = run_plan_state(
            "init",
            "--repo",
            str(alias),
            "--feature-slug",
            "cancelled-through-cli",
        )
        token = next(
            row.removeprefix("token=")
            for row in initialized.stdout.splitlines()
            if row.startswith("token=")
        )
        run_plan_state(
            "checkpoint",
            "--repo",
            str(alias),
            "--plan",
            "features/cancelled-through-cli/PLAN.md",
            "--expect-token",
            token,
            "--set",
            "lifecycle_status=cancelled",
            "--set",
            "next_action=User cancelled the fixture.",
            "--confirm-cancel",
        )
        run_plan_state(
            "sync-excludes",
            "--repo",
            str(alias),
            "--plan",
            "features/cancelled-through-cli/PLAN.md",
        )

        exclude_terminal_artifacts(
            alias, linked / "features/untracked-terminal/PLAN.md", "shipped"
        )
        exclude_terminal_artifacts(
            primary, primary / "features/tracked/PLAN.md", "cancelled"
        )
        exclude_terminal_artifacts(
            primary, primary / "features/tracked/PLAN.md", "cancelled"
        )
        for checkout in (primary, linked):
            write(checkout / "features/untracked-terminal/PLAN.md", "terminal\n")
            write(
                checkout / "features/untracked-terminal/receipts/proof.json",
                "{}\n",
            )
            write(
                checkout / "features/untracked-terminal/accepted-product.png",
                "product\n",
            )
            write(checkout / "features/active/PLAN.md", "active\n")
            write(checkout / "features/README.md", "product feature index\n")

        write(primary / "features/tracked/PLAN.md", "tracked modification\n")
        os.unlink(linked / "features/tracked/PLAN.md")
        run(linked, "add", "-u", "features/tracked/PLAN.md")

        primary_status = status(primary)
        linked_status = status(linked)
        required_primary = {
            " M features/tracked/PLAN.md",
            "?? features/README.md",
            "?? features/active/PLAN.md",
            "?? features/untracked-terminal/accepted-product.png",
        }
        required_linked = {
            "D  features/tracked/PLAN.md",
            "?? features/README.md",
            "?? features/active/PLAN.md",
            "?? features/untracked-terminal/accepted-product.png",
        }
        if not required_primary.issubset(primary_status):
            raise AssertionError(f"primary visible paths changed: {sorted(primary_status)}")
        if not required_linked.issubset(linked_status):
            raise AssertionError(f"linked visible paths changed: {sorted(linked_status)}")
        forbidden = ("untracked-terminal/PLAN.md", "untracked-terminal/receipts/")
        if any(value in row for row in (*primary_status, *linked_status) for value in forbidden):
            raise AssertionError("terminal lifecycle noise remained visible")

        contents = primary_exclude.read_bytes()
        expected = {
            b"/features/untracked-terminal/PLAN.md",
            b"/features/untracked-terminal/receipts/",
            b"/features/tracked/PLAN.md",
            b"/features/tracked/receipts/",
            b"/features/cancelled-through-cli/PLAN.md",
            b"/features/cancelled-through-cli/receipts/",
        }
        if not expected.issubset(set(contents.splitlines())):
            raise AssertionError("exact terminal patterns missing")
        if contents.count(b"/features/tracked/PLAN.md") != 1:
            raise AssertionError("terminal registration must be idempotent")
        if (
            b"/features/" in set(contents.splitlines())
            or b"/features/*/PLAN.md" in contents
        ):
            raise AssertionError("broad feature lifecycle pattern detected")
        if run(primary, "config", "--get", "extensions.worktreeConfig", check=False).returncode == 0:
            raise AssertionError("helper mutated extensions.worktreeConfig")
        if run(primary, "config", "--get", "core.excludesFile", check=False).returncode == 0:
            raise AssertionError("helper mutated core.excludesFile")

        try:
            exclude_terminal_artifacts(
                primary, primary / "features/active/PLAN.md", "building"
            )
        except LifecycleExcludeError:
            pass
        else:
            raise AssertionError("nonterminal lifecycle state was excluded")
        try:
            exclude_terminal_artifacts(
                primary, primary / "features/Bad-Slug/PLAN.md", "shipped"
            )
        except LifecycleExcludeError:
            pass
        else:
            raise AssertionError("invalid feature slug was excluded")

        run(primary, "config", "extensions.worktreeConfig", "true")
        primary_private = root / "primary.exclude"
        linked_private = root / "linked.exclude"
        write(primary_private, "/primary-only\n")
        write(linked_private, "/linked-only\n")
        run(
            primary,
            "config",
            "--worktree",
            "core.excludesFile",
            str(primary_private),
        )
        run(
            linked,
            "config",
            "--worktree",
            "core.excludesFile",
            str(linked_private),
        )
        configured_primary = run(
            primary, "config", "--worktree", "--get", "core.excludesFile"
        ).stdout.strip()
        configured_linked = run(
            linked, "config", "--worktree", "--get", "core.excludesFile"
        ).stdout.strip()
        primary_config = git_path(primary, "--git-path", "config.worktree")
        linked_config = git_path(linked, "--git-path", "config.worktree")
        if (
            configured_primary != str(primary_private)
            or configured_linked != str(linked_private)
            or primary_config == linked_config
        ):
            raise AssertionError("worktree-specific exclude mechanism was not isolated")

    print("lifecycle-excludes-regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
