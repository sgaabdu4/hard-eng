"""`release_canary.py`: which releases need a try on installed projects, and what it publishes."""

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
