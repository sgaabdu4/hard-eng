"""Only a successful upstream hard-eng check makes a revision installable."""

import io
import urllib.error
import urllib.request
from email.message import Message
from unittest.mock import Mock

import pytest
import update


@pytest.mark.parametrize(
    "conclusion,expected",
    [("success", True), ("failure", False), ("skipped", False), ("neutral", False)],
)
def test_only_successful_aggregate_is_a_verified_release(
    monkeypatch: pytest.MonkeyPatch, conclusion: str, expected: bool
) -> None:
    revision = "a" * 40

    def response(endpoint: str) -> object:
        assert revision in endpoint
        return {
            "check_runs": [
                {
                    "id": 1,
                    "name": "hard-eng",
                    "app": {"slug": "github-actions"},
                    "head_sha": revision,
                    "status": "completed",
                    "conclusion": conclusion,
                }
            ]
        }

    monkeypatch.setattr(update, "github_json", response)
    assert update.verified_revision(revision) is expected


def test_failed_rerun_supersedes_earlier_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "a" * 40

    def response(_endpoint: str) -> object:
        return {
            "check_runs": [
                {
                    "id": identifier,
                    "name": "hard-eng",
                    "app": {"slug": "github-actions"},
                    "head_sha": revision,
                    "status": "completed",
                    "conclusion": conclusion,
                }
                for identifier, conclusion in [(1, "success"), (2, "failure")]
            ]
        }

    monkeypatch.setattr(update, "github_json", response)
    assert update.verified_revision(revision) is False


def test_update_selection_skips_failed_newer_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revisions = ["a" * 40, "b" * 40, "c" * 40]

    def response(endpoint: str) -> object:
        assert "sha=main" in endpoint
        return [{"sha": revision} for revision in revisions]

    def verified(revision: str) -> bool:
        return revision == revisions[1]

    monkeypatch.setattr(update, "upstream_moved", Mock(return_value=True))
    monkeypatch.setattr(update, "github_json", response)
    monkeypatch.setattr(update, "verified_revision", verified)
    assert update.latest_verified(revisions[2]) == revisions[1]
    assert update.latest_verified(revisions[1]) is None


@pytest.mark.parametrize(
    ("answer", "walks"),
    [(304, False), ("a" * 40, False), ("b" * 40, True)],
    ids=["not-modified", "same-head", "moved"],
)
def test_freshness_walks_commits_only_after_upstream_moves(
    monkeypatch: pytest.MonkeyPatch, answer: int | str, walks: bool
) -> None:
    monkeypatch.setenv("GH_TOKEN", "fixture-token")

    def respond(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        assert request.get_header("Accept") == "application/vnd.github.sha"
        assert request.get_header("If-none-match") == f'"{"a" * 40}"'
        if answer == 304:
            raise urllib.error.HTTPError(request.full_url, 304, "", Message(), None)
        return io.BytesIO(str(answer).encode())

    walk = Mock(return_value=[{"sha": "a" * 40}])
    monkeypatch.setattr(urllib.request, "urlopen", respond)
    monkeypatch.setattr(update, "github_json", walk)
    assert update.latest_verified("a" * 40) is None
    assert walk.called is walks
