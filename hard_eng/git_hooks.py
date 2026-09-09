"""Check the committed trees named by Git's pre-push input."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from hard_eng.common import GateError, git, run


def revisions(text: str) -> list[str]:
    commits: list[str] = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 4 or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", fields[1]):
            raise GateError("Invalid Git pre-push input")
        commit = fields[1]
        if set(commit) != {"0"} and commit not in commits:
            commits.append(commit)
    return commits


def check_push(root: Path, text: str) -> None:
    for commit in revisions(text):
        git(root, "cat-file", "-e", f"{commit}^{{commit}}")
        with tempfile.TemporaryDirectory(prefix="hard-eng-push-") as temporary:
            checkout = Path(temporary) / "checkout"
            git(root, "worktree", "add", "--detach", str(checkout), commit)
            try:
                if (checkout / ".gitmodules").is_file():
                    git(checkout, "submodule", "update", "--init", "--recursive")
                launcher = checkout / ".hard-eng/bin/hard-eng"
                if not launcher.is_file():
                    launcher = checkout / "bin/hard-eng"
                if not launcher.is_file():
                    raise GateError(f"Pushed commit {commit[:12]} has no committed Hard Eng runner")
                result = run(["python3", str(launcher), "--repo", str(checkout), "check"], checkout, 3600)
                print(result.stdout, end="")
                if result.returncode:
                    print(result.stderr, end="")
                    raise GateError(f"Pushed commit {commit[:12]} failed its gates")
            finally:
                git(root, "worktree", "remove", "--force", "--force", str(checkout))


def install(root: Path, launcher: str) -> None:
    location = git(root, "rev-parse", "--git-path", "hooks/pre-push").strip()
    path = Path(location) if Path(location).is_absolute() else root / location
    common = Path(git(root, "rev-parse", "--git-common-dir").strip())
    common = common if common.is_absolute() else root / common
    if not path.resolve().is_relative_to(root.resolve()) and not path.resolve().is_relative_to(
        common.resolve()
    ):
        raise GateError(
            "The configured hooks directory is outside this repository; use a repository-local hook"
        )
    marker = "# Hard Eng pre-push"
    if path.exists() and marker not in path.read_text():
        raise GateError(f"Existing pre-push hook has another owner: {path}; integrate the CLI call there")
    from hard_eng.common import write_file

    write_file(
        path,
        f'#!/bin/sh\n{marker}\nexec python3 "$(git rev-parse --show-toplevel)/{launcher}" pre-push "$@"\n',
    )
    path.chmod(0o755)
