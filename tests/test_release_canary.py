"""`release_canary.py`: which releases need a try on installed projects, and what it publishes."""

import sys
from pathlib import Path

import pytest

import release_canary


def test_only_changes_to_installed_files_need_a_canary_run() -> None:
    assert not release_canary.needs_canary(
        ["README.md", "tests/test_setup.py", "features/x/PLAN.md", "docs/a.md"]
    )
    for installed in (
        ".hooks/update.py",
        "setup.py",
        "AGENTS.md",
        ".agents/skill-sources/building-flutter-apps",
        ".github/workflows/hard-eng.yml",
    ):
        assert release_canary.needs_canary(["README.md", installed])


def test_published_status_names_no_project() -> None:
    """The source repository is public; most installed projects are private."""
    results = {
        "owner/private-app": (True, "update and check passed"),
        "owner/other-app": (False, "check failed; log /cache/owner__other-app.log"),
    }
    text = release_canary.status_text(results)
    assert text == "1 of 2 installed projects passed"
    assert "owner" not in text


def test_a_run_that_finds_no_project_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty search must not certify a release."""
    posted: list[str] = []
    replies = {"rev-parse": "a" * 40, "diff": ".hooks/update.py"}

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        return replies.get(command[1], "")

    def post_status(revision: str, state: str, description: str) -> None:
        posted.append(state)

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary, "installed_projects", list)
    monkeypatch.setattr(release_canary, "post_status", post_status)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD", "--post-status"])
    assert release_canary.main() == 1
    assert posted == ["pending", "failure"]
