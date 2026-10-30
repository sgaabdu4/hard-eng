"""The generated workflow asks setup-bun for an exact version a runner can reuse."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import ci_jobs
import pytest
import yaml
from ci_jobs import bootstrap_bun
from conftest import SOURCE
from gate_config import JsonObject
from test_apple_jobs import generated, migrate
from test_swift import app_config, impact_module

EXPRESSION = "${{ steps.impact.outputs.bun || 'latest' }}"
WORKFLOW = ".github/workflows/hard-eng.yml"


def release(tag: str, age: float, **flags: bool) -> JsonObject:
    stamp = (datetime.now(UTC) - timedelta(days=age)).isoformat()
    return {
        "tag_name": tag,
        "published_at": stamp,
        "draft": False,
        "prerelease": False,
        **flags,
    }


@pytest.fixture
def actions(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")


def test_a_pinned_bun_needs_no_lookup() -> None:
    def unexpected() -> list[JsonObject]:
        raise AssertionError("A pinned version must not query releases")

    assert bootstrap_bun(["uv@latest", "bun@1.3.1"], unexpected) == "1.3.1"


def test_the_newest_release_two_days_old_is_chosen(actions: None) -> None:
    releases = [
        release("bun-v1.5.0", 0.5),
        release("bun-v1.4.9-canary.1", 3),
        release("bun-v1.4.8", 3, prerelease=True),
        release("bun-v1.4.7", 3, draft=True),
        release("bun-v1.4.4", 2.5),
        release("bun-v1.4.10", 9),
        release("bun-v1.3.14", 60),
        {"tag_name": "other", "published_at": "2026-01-01T00:00:00Z"},
    ]
    assert bootstrap_bun(["uv@latest", "bun@latest"], lambda: releases) == "1.4.10"


def test_outside_actions_the_version_is_left_to_setup_bun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert bootstrap_bun([], lambda: [release("bun-v1.4.4", 5)]) is None


@pytest.mark.parametrize("failure", [OSError("offline"), ValueError("bad date")])
def test_a_failed_lookup_leaves_latest(actions: None, failure: Exception) -> None:
    def broken() -> list[JsonObject]:
        raise failure

    assert bootstrap_bun([], broken) is None


def test_only_releases_under_two_days_old_leave_latest(actions: None) -> None:
    assert bootstrap_bun([], lambda: [release("bun-v1.4.4", 0.1)]) is None


def test_impact_prints_the_version(
    installer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    actions: None,
) -> None:
    monkeypatch.setattr(ci_jobs, "bun_releases", lambda: [release("bun-v1.4.4", 5)])
    module = impact_module(installer, tmp_path, "ios/Runner/Box.swift")
    module.__dict__["proven_elsewhere"] = lambda _base: False
    assert module.impact("HEAD") == 0
    assert "bun=1.4.4" in capsys.readouterr().out.splitlines()
    module.__dict__["proven_elsewhere"] = lambda _base: True
    assert module.impact("HEAD") == 0
    assert capsys.readouterr().out.splitlines()[-1] == "bun=1.4.4"


def bun_versions(workflow: str) -> list[str]:
    jobs = yaml.safe_load(workflow)["jobs"]
    return [
        step["with"]["bun-version"]
        for job in jobs.values()
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("oven-sh/setup-bun@")
    ]


def test_generated_workflows_ask_for_the_resolved_version(
    installer: ModuleType, tmp_path: Path
) -> None:
    _, plain, swift = generated(installer, tmp_path)
    template = (SOURCE / WORKFLOW).read_text()
    assert bun_versions(template) == [EXPRESSION]
    assert bun_versions(plain) == [EXPRESSION]
    assert bun_versions(swift) == [EXPRESSION, EXPRESSION]


def test_older_workflows_move_to_the_resolved_version_once(
    installer: ModuleType, tmp_path: Path
) -> None:
    root, _, swift = generated(installer, tmp_path)
    older = swift.replace(EXPRESSION, "latest")
    config = app_config(installer, root)
    assert migrate(root, older, config) == {WORKFLOW: swift}
    assert migrate(root, swift, config) == {}


def test_a_chosen_version_stays(installer: ModuleType, tmp_path: Path) -> None:
    root, plain, _ = generated(installer, tmp_path)
    chosen = plain.replace(EXPRESSION, "1.2.3")
    assert migrate(root, chosen, installer.gate_config(root)) == {}
