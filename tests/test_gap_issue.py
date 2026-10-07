"""Gap issues name only a generic missing check and are filed once."""

import json
from pathlib import Path

import gap_issue
import pytest


class FakeGh:
    def __init__(self, existing: list[dict[str, str]]) -> None:
        self.existing = existing
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, _root: Path, *args: str) -> str:
        self.calls.append(args)
        if args[:2] == ("issue", "list"):
            return json.dumps(self.existing)
        return "https://github.com/sgaabdu4/hard-eng/issues/9\n"


@pytest.fixture
def project(repository: Path) -> Path:
    (repository / "hard-eng.gates.json").write_text('{"packages": [], "shared": []}')
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng-source.json").write_text('{"revision": "abc123"}')
    (repository / "main.go").write_text("package main\n")
    return repository


def fake(monkeypatch: pytest.MonkeyPatch, existing: list[dict[str, str]]) -> FakeGh:
    gh = FakeGh(existing)
    monkeypatch.setattr(gap_issue, "gh", gh)
    return gh


def test_new_gap_is_filed_with_the_fixed_title_and_body(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gh = fake(monkeypatch, [{"title": "Unrelated", "url": "u"}])
    assert gap_issue.file_gap(project, "No built-in checks for Go") == 0
    searched = gh.calls[0]
    assert searched[searched.index("--repo") + 1] == "sgaabdu4/hard-eng"
    assert searched[searched.index("--state") + 1] == "all"
    create = gh.calls[1]
    assert create[:2] == ("issue", "create")
    assert (
        create[create.index("--title") + 1]
        == "Missing check: No built-in checks for Go"
    )
    assert create[create.index("--body") + 1] == (
        "Missing check: No built-in checks for Go\n\n"
        "Language: Go\nHard Eng revision: abc123\n\n"
        "Filed by `python3 .hooks/hard-eng.py gap-issue`. It names only the missing check."
    )
    assert "issues/9" in capsys.readouterr().out


def test_gap_already_filed_open_or_closed_is_not_filed_again(
    project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    gh = fake(
        monkeypatch,
        [{"title": "missing check: no built-in checks for go", "url": "https://x/1"}],
    )
    assert gap_issue.file_gap(project, "No built-in checks for Go") == 0
    assert [call[:2] for call in gh.calls] == [("issue", "list")]
    assert "Already filed: https://x/1" in capsys.readouterr().out


@pytest.mark.parametrize(
    "text",
    [
        "lint src/app/main.py",
        "run scripts\\build",
        "check app.config.ts",
        "check apps/web/package.json",
        "check package.json.bak",
        "scan https://internal.example",
        "notify owner@example.com",
        "x" * 121,
        "  ",
    ],
)
def test_project_detail_is_refused_before_any_github_call(
    project: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    gh = fake(monkeypatch, [])
    with pytest.raises(ValueError, match="Describe the missing check generically"):
        gap_issue.file_gap(project, text)
    assert gh.calls == []


@pytest.mark.parametrize(
    "text",
    ["go.sum drift", "package.json scripts", "Dockerfile base image pinning"],
)
def test_common_manifest_names_are_accepted(
    project: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    fake(monkeypatch, [])
    assert gap_issue.file_gap(project, text) == 0


def test_language_labels_with_a_slash_are_accepted(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake(monkeypatch, [])
    assert gap_issue.file_gap(project, "No built-in checks for Java/Kotlin") == 0
