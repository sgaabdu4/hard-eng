"""Gap issues name only a generic missing check and are filed once."""

import json
from pathlib import Path

import gap_issue
import pytest
from conftest import git


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
    [
        "no lint for acme-shop",
        "Acme Shop has no dependency audit",
        "missing audit in acme_shop",
        "owner globex lacks secret scanning",
        "shop-checkout needs a license check",
        "apps/storefront has no lint",
        "storefront lacks a license check",
        "billing has no schema check",
    ],
)
def test_text_that_names_the_project_is_refused_before_any_github_call(
    project: Path, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    git(project, "remote", "add", "origin", "https://github.com/globex/acme-shop.git")
    (project / "hard-eng.gates.json").write_text(
        '{"packages": [{"name": ".", "path": "."},'
        ' {"name": "apps/storefront", "path": "apps/storefront"},'
        ' {"name": "services/billing", "path": "services/billing"}], "shared": []}'
    )
    named = project.rename(project.with_name("shop-checkout"))
    gh = fake(monkeypatch, [])
    with pytest.raises(ValueError, match="Describe the missing check generically"):
        gap_issue.file_gap(named, text)
    assert gh.calls == []
    assert gap_issue.file_gap(named, "Go dependency audit for shopping carts") == 0


@pytest.mark.parametrize(
    ("origin", "text"),
    [
        ("https://github.com/globex/acme-shop.git", "AcmeShop has no lint"),
        ("https://github.com/globex/acme-shop.git", "acmeshop lacks audit"),
        ("git@github-work:globex/acme-shop.git", "owner globex lacks scanning"),
        ("git@github-work:globex/acme-shop.git", "acme shop lacks lint"),
        ("https://gitlab.example.test/globex/acme-shop", "globex lacks lint"),
        ("ssh://git@bitbucket.example.test/globex/acme-shop.git", "acme-shop lint"),
        ("https://dev.azure.com/contoso/shop/_git/storefront", "contoso lacks lint"),
        ("https://gitlab.example.test/acme/team/shop", "acme has no audit"),
        ("https://github.com/globex/acme-shop.git/", "acme shop lacks lint"),
        ("https://git.example.test:8443/globex/acme-shop", "globex lacks lint"),
    ],
)
def test_joined_spellings_and_any_remote_host_are_refused(
    project: Path, monkeypatch: pytest.MonkeyPatch, origin: str, text: str
) -> None:
    git(project, "remote", "add", "origin", origin)
    gh = fake(monkeypatch, [])
    with pytest.raises(ValueError, match="Describe the missing check generically"):
        gap_issue.file_gap(project, text)
    assert gh.calls == []


@pytest.mark.parametrize(
    ("origin", "text"),
    [
        (
            "https://dev.azure.com/contoso/shop/_git/storefront",
            "git hooks have no lint check",
        ),
        ("/srv/git/x.git", "git hooks have no lint check"),
        ("/Users/me/projects/x", "projects lack a license check"),
        ("https://git.example.test:8443/globex/acme-shop", "8443 has no lint check"),
    ],
)
def test_words_from_a_remote_that_are_not_names_are_accepted(
    project: Path, monkeypatch: pytest.MonkeyPatch, origin: str, text: str
) -> None:
    git(project, "remote", "add", "origin", origin)
    fake(monkeypatch, [])
    assert gap_issue.file_gap(project, text) == 0


def test_the_refusal_says_which_name_matched(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (project / "hard-eng.gates.json").write_text(
        '{"packages": [{"name": "web", "path": "web"}], "shared": []}'
    )
    fake(monkeypatch, [])
    with pytest.raises(ValueError, match="one of its packages: web"):
        gap_issue.file_gap(project, "web has no lint check")


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
