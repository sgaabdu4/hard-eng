"""Focused UX-reference target and linked-worktree regression checks."""

from __future__ import annotations

import base64
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env

VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "/x8AAusB9Wl2nS8AAAAASUVORK5CYII="
)


def check_targets(state, git_repo: Callable[[Path], None], fail: Callable[[str], None]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        base = _filled(state.template("lean-loop", "lean-loop-test"))
        (repo / "docs").mkdir()
        (repo / "src").mkdir()
        (repo / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
        (repo / "src/theme.css").write_text(
            ":root { --surface: white; }\n", encoding="utf-8"
        )
        (repo / "docs/mock.txt").write_text("not an image", encoding="utf-8")
        (repo / "docs/fake-mock.png").write_bytes(b"\x89PNG mock")
        (repo / "docs/real-mock.png").write_bytes(VALID_PNG)
        cases = (
            ("docs/mock.png", "DESIGN.md + src/theme.css", False),
            ("accepted modal layout per chat", "DESIGN.md + src/theme.css", False),
            ("docs/mock.txt", "DESIGN.md + src/theme.css", False),
            ("docs/fake-mock.png", "DESIGN.md + src/theme.css", False),
            ("https://example.invalid/mock", "DESIGN.md + src/theme.css", False),
            ("https://example.invalid/mock.png", "DESIGN.md + src/theme.css", True),
            ("docs/real-mock.png", "n/a", False),
            ("docs/real-mock.png", "DESIGN.md", False),
            (
                "docs/real-mock.png",
                f"DESIGN.md + {repo / 'src/theme.css'}",
                False,
            ),
            ("docs/real-mock.png", "DESIGN.md + docs/real-mock.png", False),
            ("docs/real-mock.png", "DESIGN.md + src/missing.css", False),
            ("docs/real-mock.png", "DESIGN.md + src/theme.css", True),
        )
        for value, sources, expected in cases:
            text = base.replace(
                "- ux_reference = n/a", f"- ux_reference = {value}"
            ).replace(
                "- ux_reference_sources = n/a",
                f"- ux_reference_sources = {sources}",
            )
            plan.write_text(text, encoding="utf-8")
            approved = subprocess.run(
                [
                    sys.executable, str(STATE_PATH), "approve",
                    "--repo", str(repo), "--plan", str(plan),
                    "--expect-token", state.token_for(text),
                    "--approval-reply", "yes",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            if (approved.returncode == 0) != expected:
                fail(
                    "ux_reference target rule failed for: "
                    f"{value} from {sources}: {approved.stderr}"
                )
            if not expected and not approved.stderr:
                fail(f"ux_reference rejection lacks guidance: {value}")


def check_linked_worktree(
    state, git_repo: Callable[[Path], None], fail: Callable[[str], None]
) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        repo = root / "project"
        worktree = root / "project-worktree"
        git_repo(repo)
        (repo / "DESIGN.md").write_text("# Design\n", encoding="utf-8")
        (repo / "src").mkdir()
        (repo / "src/theme.css").write_text(
            ":root { --surface: white; }\n", encoding="utf-8"
        )
        (repo / "docs").mkdir()
        (repo / "docs/ux-reference.png").write_bytes(VALID_PNG)
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        brief = _filled(
            state.template("lean-loop", "linked-worktree-test")
        ).replace(
            "- ux_reference = n/a",
            "- ux_reference = docs/ux-reference.png",
        ).replace(
            "- ux_reference_sources = n/a",
            "- ux_reference_sources = DESIGN.md + src/theme.css",
        )
        plan.write_text(brief, encoding="utf-8")
        subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), "add", "."],
            check=True,
            env=git_env(),
        )
        subprocess.run(
            [
                "git", "-c", "core.hooksPath=/dev/null", "-C", str(repo),
                "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                "commit", "-qm", "fixture",
            ],
            check=True,
            env=git_env(),
        )
        subprocess.run(
            [
                "git", "-c", "core.hooksPath=/dev/null", "-C", str(repo),
                "worktree", "add", "-qb", "fixture/ux-reference", str(worktree),
            ],
            check=True,
            env=git_env(),
        )
        worktree_plan = worktree / "features/lean-loop/PLAN.md"
        validated = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "validate",
                "--repo", str(worktree), "--plan", str(worktree_plan),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        expected_markdown = (
            f"ux_reference_markdown=![UX reference]"
            f"(<{worktree / 'docs/ux-reference.png'}>)"
        )
        if validated.returncode != 0 or expected_markdown not in validated.stdout:
            fail(
                "fresh linked-worktree validation did not emit renderable absolute "
                f"Markdown: {validated.stdout} {validated.stderr}"
            )
        worktree_alias = root / "project-worktree-alias"
        worktree_alias.symlink_to(worktree, target_is_directory=True)
        aliased = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "validate",
                "--repo", str(worktree_alias),
                "--plan", str(worktree_alias / "features/lean-loop/PLAN.md"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if aliased.returncode != 0:
            fail(f"aliased worktree root rejected its absolute PLAN path: {aliased.stderr}")
        approved = subprocess.run(
            [
                sys.executable, str(STATE_PATH), "approve",
                "--repo", str(worktree), "--plan", str(worktree_plan),
                "--expect-token", state.token_for(brief),
                "--approval-reply", "yes",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if approved.returncode != 0:
            fail(f"fresh linked-worktree approval failed: {approved.stderr}")


def _filled(text: str) -> str:
    replacements = {
        "## Outcome\n- TBD": "## Outcome\n- A user receives one observable result.",
        "## Non-goals\n- TBD": "## Non-goals\n- Adjacent workflow changes are excluded.",
        "## Material decisions\n- TBD": (
            "## Material decisions\n- Existing policy remains canonical."
        ),
        "- ux_reference = TBD": "- ux_reference = n/a",
        "- ux_reference_sources = TBD": "- ux_reference_sources = n/a",
        "## Acceptance examples\n- TBD": (
            "## Acceptance examples\n"
            "- Given an eligible user, when they act, then the result is visible."
        ),
        "## Affected canonical areas\n- TBD": (
            "## Affected canonical areas\n- Existing command owner and route."
        ),
        "- rollback = TBD": "- rollback = disable the route and preserve stored state.",
        "## First vertical slice\n- S-1 = TBD\n- proof = TBD": (
            "## First vertical slice\n"
            "- S-1 = command to stored result to visible response.\n"
            "- proof = focused behavior test."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text
