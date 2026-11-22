"""Single source of truth for host model roles, local overlays, CLI flags and shipping."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock

import models
import pytest
import update
from conftest import SOURCE, commit, default_policy, git, init
from test_agent_hooks import session_start_context

if TYPE_CHECKING:
    from types import ModuleType


@pytest.fixture(autouse=True)
def isolated_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
    return xdg


def test_shipped_models_json_loads_with_expected_defaults_and_flags() -> None:
    loaded = models.load_models(SOURCE)
    assert loaded["hosts"]["claude"] == {
        "reasoning": {"model": "opus", "effort": "high"},
        "implementation": {"model": "sonnet", "effort": "high"},
        "lookup": {"model": "haiku", "effort": "medium"},
    }
    assert loaded["hosts"]["codex"] == {
        "reasoning": {
            "model": "gpt-6.2-sol",
            "effort": "high",
            "service_tier": "default",
        },
        "implementation": {
            "model": "gpt-6.2-sol",
            "effort": "high",
            "service_tier": "default",
        },
        "lookup": {
            "model": "gpt-6-luna",
            "effort": "low",
            "service_tier": "default",
        },
    }
    assert loaded["hosts"]["agy"] == {
        "reasoning": {"model": "gemini-4-neon", "effort": "xhigh"},
        "implementation": {"model": "gemini-4-neon", "effort": "high"},
        "lookup": {"model": "gemini-3.8-flash", "effort": "low"},
    }
    assert loaded["challenge_order"] == {
        "claude": ["codex", "agy"],
        "codex": ["claude", "agy"],
        "agy": ["codex", "claude"],
    }
    assert loaded["subagent_overflow"] == {
        "reasoning": ["claude", "agy", "codex"],
        "implementation": ["claude", "agy", "codex"],
    }
    assert models.cli_flags("codex", "reasoning", SOURCE) == [
        "-m",
        "gpt-6.2-sol",
        "-c",
        "model_reasoning_effort=high",
        "-c",
        "service_tier=default",
    ]
    assert models.cli_flags("claude", "reasoning", SOURCE) == [
        "--model",
        "opus",
        "--effort",
        "high",
    ]
    assert models.cli_flags("agy", "reasoning", SOURCE) == [
        "--model",
        "gemini-4-neon",
        "--effort",
        "xhigh",
    ]


def test_local_overlay_merges_partially_and_respects_xdg_config_home(
    isolated_xdg: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    overlay = isolated_xdg / "hard-eng/models.json"
    overlay.parent.mkdir(parents=True)
    overlay.write_text(
        json.dumps(
            {
                "hosts": {
                    "codex": {"reasoning": {"effort": "xhigh"}},
                    "agy": {"reasoning": {"model": "gemini-4.1-pro"}},
                },
                "challenge_order": {"claude": ["agy", "codex"]},
                "subagent_overflow": {"reasoning": ["agy", "claude", "codex"]},
            }
        )
    )
    assert models.cli_flags("codex", "reasoning", SOURCE) == [
        "-m",
        "gpt-6.2-sol",
        "-c",
        "model_reasoning_effort=xhigh",
        "-c",
        "service_tier=default",
    ]
    assert models.cli_flags("agy", "reasoning", SOURCE) == [
        "--model",
        "gemini-4.1-pro",
        "--effort",
        "xhigh",
    ]
    assert models.challenge_order_for("claude", SOURCE) == ("agy", "codex")
    assert models.challenge_order_for("codex", SOURCE) == ("claude", "agy")
    assert models.load_models(SOURCE)["subagent_overflow"] == {
        "reasoning": ["agy", "claude", "codex"],
        "implementation": ["claude", "agy", "codex"],
    }
    assert models.role_config("claude", "lookup", SOURCE) == {
        "model": "haiku",
        "effort": "medium",
    }

    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")
    assert models.local_override_path() == Path.home() / ".config/hard-eng/models.json"


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ("not-json", "unreadable JSON"),
        ("[]", "expected a JSON object"),
        (json.dumps({"extra": {}}), "unknown sections"),
        (json.dumps({"hosts": []}), "hosts: expected an object"),
        (json.dumps({"hosts": {"unknown": {}}}), "unknown hosts"),
        (json.dumps({"hosts": {"claude": []}}), r"hosts\.claude: expected an object"),
        (json.dumps({"hosts": {"claude": {"bad": {}}}}), "unknown roles"),
        (
            json.dumps({"hosts": {"claude": {"reasoning": []}}}),
            r"hosts\.claude\.reasoning: expected an object",
        ),
        (
            json.dumps({"hosts": {"claude": {"reasoning": {"extra": "x"}}}}),
            "unknown fields",
        ),
        (
            json.dumps(
                {"hosts": {"claude": {"reasoning": {"service_tier": "default"}}}}
            ),
            "only for codex",
        ),
        (
            json.dumps({"hosts": {"codex": {"reasoning": {"model": "--inject"}}}}),
            "invalid model identifier",
        ),
        (
            json.dumps({"hosts": {"codex": {"reasoning": {"effort": "turbo"}}}}),
            "effort: must be one of",
        ),
        (
            json.dumps({"hosts": {"codex": {"reasoning": {"service_tier": "true"}}}}),
            "invalid service tier",
        ),
        (
            json.dumps({"hosts": {"codex": {"reasoning": {"model": ""}}}}),
            "nonempty string",
        ),
        (json.dumps({"challenge_order": []}), "challenge_order: expected an object"),
        (json.dumps({"challenge_order": {"other": ["codex"]}}), "unknown keys"),
        (json.dumps({"challenge_order": {"claude": []}}), "nonempty list"),
        (json.dumps({"challenge_order": {"claude": ["other"]}}), "unknown host"),
        (json.dumps({"challenge_order": {"claude": ["claude"]}}), "cannot include"),
        (
            json.dumps({"challenge_order": {"claude": ["agy"]}}),
            "must include all other hosts",
        ),
        (
            json.dumps({"challenge_order": {"claude": ["codex", "codex"]}}),
            "duplicate host",
        ),
    ],
)
def test_invalid_overlay_payloads_are_rejected(
    isolated_xdg: Path, payload: str, match: str
) -> None:
    overlay = isolated_xdg / "hard-eng/models.json"
    overlay.parent.mkdir(parents=True)
    overlay.write_text(payload)
    with pytest.raises((ValueError, TypeError), match=match):
        models.load_models(SOURCE)


def test_invalid_base_models_json_and_unknown_accessors_raise(tmp_path: Path) -> None:
    target = tmp_path / ".agents/models.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"hosts": {}}))
    with pytest.raises(ValueError, match="missing sections"):
        models.load_models(tmp_path)

    full = json.loads((SOURCE / ".agents/models.json").read_text())
    del full["hosts"]["agy"]
    target.write_text(json.dumps(full))
    with pytest.raises(ValueError, match="missing hosts"):
        models.load_models(tmp_path)

    full = json.loads((SOURCE / ".agents/models.json").read_text())
    del full["hosts"]["agy"]["lookup"]
    target.write_text(json.dumps(full))
    with pytest.raises(ValueError, match="missing roles"):
        models.load_models(tmp_path)

    full = json.loads((SOURCE / ".agents/models.json").read_text())
    del full["hosts"]["agy"]["reasoning"]["effort"]
    target.write_text(json.dumps(full))
    with pytest.raises(ValueError, match="missing required fields"):
        models.load_models(tmp_path)

    full = json.loads((SOURCE / ".agents/models.json").read_text())
    del full["challenge_order"]["agy"]
    target.write_text(json.dumps(full))
    with pytest.raises(ValueError, match="missing keys"):
        models.load_models(tmp_path)

    with pytest.raises(ValueError, match="Unknown host"):
        models.challenge_order_for("other", SOURCE)
    with pytest.raises(ValueError, match="Unknown host"):
        models.role_config("other", "reasoning", SOURCE)
    with pytest.raises(ValueError, match="Unknown role"):
        models.role_config("claude", "other", SOURCE)


def test_models_json_is_shipped_installed_and_updated_by_scaffold(
    installer: ModuleType, tmp_path: Path
) -> None:
    assert ".agents/models.json" in update.scaffold_files(SOURCE)
    assert update.maybe_installed(".agents/models.json")
    assert update.install_paths([".agents/models.json"]) == ".agents/models.json"

    repo = tmp_path / "repo"
    init(repo)
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "app"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n'
    )
    (repo / "uv.lock").write_text("version = 1\n")
    (repo / "app.py").write_text("x = 1\n")
    commit(repo, "init")

    installer.install(repo)
    shipped = repo / ".agents/models.json"
    assert shipped.read_bytes() == (SOURCE / ".agents/models.json").read_bytes()

    shipped.write_text('{"local": true}\n')
    with pytest.raises(ValueError, match=r"\.agents/models\.json already differs"):
        installer.install(repo)


def test_update_refreshes_models_json_as_verified_scaffold_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from test_updates import select_release

    source, target, _ = release
    shipped = target / ".agents/models.json"
    assert shipped.is_file()
    base = git(target, "rev-parse", "HEAD")
    updated = json.loads((source / ".agents/models.json").read_text())
    updated["hosts"]["agy"]["reasoning"]["effort"] = "max"
    (source / ".agents/models.json").write_text(json.dumps(updated, indent=2) + "\n")
    select_release(source, monkeypatch)

    update.update(target)
    changed = git(
        target, "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"
    ).splitlines()
    assert "M\t.agents/models.json" in changed
    assert (
        json.loads(shipped.read_text())["hosts"]["agy"]["reasoning"]["effort"] == "max"
    )
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert update.check_scaffold_update(target, base)


@pytest.mark.parametrize("agent", ["claude", "codex", "agy"])
@pytest.mark.parametrize("present", [False, True])
def test_codex_and_agy_session_start_surface_models_config_and_rules(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    agent: str,
    present: bool,
) -> None:
    if present:
        (repository / ".agents").mkdir(exist_ok=True)
        (repository / ".agents/models.json").write_text(
            (SOURCE / ".agents/models.json").read_text()
        )
    context = session_start_context(
        repository, monkeypatch, capsys, agent, "models-note"
    )
    mentioned = (
        ".agents/models.json" in context and ".claude/rules/model-roles.md" in context
    )
    assert mentioned == (present and agent in {"codex", "agy"})


def write_policy(root: Path, base: str) -> None:
    (root / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "version": 1,
                "shipping": {**default_policy(), "base": base},
                "packages": [],
            }
        )
    )


@pytest.mark.parametrize("target_file", [".agents/models.json", "hard-eng.gates.json"])
def test_failed_git_read_on_trusted_base_fails_closed(
    repository: Path, monkeypatch: pytest.MonkeyPatch, target_file: str
) -> None:
    import subprocess

    git(repository, "branch", "-M", "main")
    (repository / ".agents").mkdir(exist_ok=True)
    (repository / ".agents/models.json").write_text(
        (SOURCE / ".agents/models.json").read_text()
    )
    write_policy(repository, "main")
    commit(repository, "commit base files")
    real_run = subprocess.run

    def fail_show(
        args: list[str],
        *,
        cwd: Path | None = None,
        capture_output: bool = False,
        text: bool = False,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        if args[:2] == ["git", "show"] and args[2].endswith(f":{target_file}"):
            return subprocess.CompletedProcess(
                args, 128, stdout="", stderr="fatal: missing promisor object"
            )
        return real_run(
            args,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            check=check,
        )

    monkeypatch.setattr(models.subprocess, "run", fail_show)
    with pytest.raises(ValueError, match="unreadable trusted base"):
        if target_file == ".agents/models.json":
            models.load_models(repository, trusted_ref="HEAD")
        else:
            models.trusted_base_ref(repository)


def test_hotfix_branch_cannot_redirect_trusted_base_to_itself(
    repository: Path,
) -> None:
    git(repository, "branch", "-M", "main")
    write_policy(repository, "main")
    base_commit = commit(repository, "base policy")
    git(repository, "checkout", "-qb", "hotfix/self-base")
    write_policy(repository, "hotfix/self-base")
    commit(repository, "self-pointing base")
    assert models.trusted_base_ref(repository) == base_commit


def test_migrated_develop_base_beats_stale_main_policy(repository: Path) -> None:
    git(repository, "branch", "-M", "main")
    write_policy(repository, "main")
    commit(repository, "stale main policy")
    git(repository, "checkout", "-qb", "develop")
    write_policy(repository, "develop")
    (repository / ".agents").mkdir(exist_ok=True)
    develop_models = json.loads((SOURCE / ".agents/models.json").read_text())
    develop_models["hosts"]["codex"]["reasoning"]["model"] = "gpt-6.2-trusted"
    (repository / ".agents/models.json").write_text(json.dumps(develop_models))
    develop_commit = commit(repository, "migrate base to develop")
    git(repository, "checkout", "-qb", "feature")
    tampered = json.loads((SOURCE / ".agents/models.json").read_text())
    tampered["hosts"]["codex"]["reasoning"]["model"] = "gpt-6.2-tampered"
    (repository / ".agents/models.json").write_text(json.dumps(tampered))
    commit(repository, "tamper models on feature")

    trusted = models.trusted_base_ref(repository)
    assert trusted == develop_commit
    assert (
        models.role_config("codex", "reasoning", repository, trusted_ref=trusted)[
            "model"
        ]
        == "gpt-6.2-trusted"
    )


def test_detached_head_cannot_redirect_trusted_base_to_itself(
    repository: Path,
) -> None:
    git(repository, "branch", "-M", "main")
    (repository / ".agents").mkdir(exist_ok=True)
    (repository / ".agents/models.json").write_text(
        (SOURCE / ".agents/models.json").read_text()
    )
    main_commit = commit(repository, "main with models")
    git(repository, "checkout", "-qb", "feature")
    write_policy(repository, "feature")
    commit(repository, "first policy pointing to feature")
    git(repository, "checkout", "-q", "--detach", "HEAD")
    assert models.trusted_base_ref(repository) == main_commit


def test_model_roles_rule_references_ssot_without_hardcoded_models() -> None:
    text = (SOURCE / ".claude/rules/model-roles.md").read_text()
    assert ".agents/models.json" in text
    assert "subagent_overflow" in text
    for forbidden in ("opus", "sonnet", "haiku", "gpt-", "gemini-"):
        assert forbidden not in text.lower(), forbidden
