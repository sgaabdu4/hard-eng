"""Strict loading of the shipping policy in hard-eng.gates.json."""

import json
from pathlib import Path
from typing import cast

import ci_jobs
import pytest
import shipping
from gate_config import GateConfig


def _write(root: Path, **changes: object) -> None:
    policy: dict[str, object] = {
        "base": "main",
        "checks": ["build"],
        "ui_paths": [],
        "ci_seconds": 180,
        "pre_push_seconds": 180,
        "delivery": [],
    }
    root.mkdir(exist_ok=True)
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": policy | changes})
    )


def test_load_policy_is_optional_only_when_absent(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    assert shipping.load_policy(root, required=False) is None
    with pytest.raises(shipping.ShippingError):
        shipping.load_policy(root)
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": {"base": "main"}})
    )
    with pytest.raises(shipping.ShippingError):
        shipping.load_policy(root, required=False)


@pytest.mark.parametrize(
    "change",
    [
        {"extra": True},
        {"checks": ["build", "build"]},
        {"ci_seconds": False},
        {"pre_push_seconds": 0},
        {"pre_push_mutation_seconds": -1},
        {"pre_push_mutation_seconds": False},
        {"pre_push_checks": "never"},
        {"pre_push_checks": False},
        {"delivery": [{"name": "bad"}]},
    ],
)
def test_load_policy_rejects_malformed_values(
    tmp_path: Path, change: dict[str, object]
) -> None:
    _write(tmp_path / "project", **change)
    with pytest.raises(shipping.ShippingError):
        shipping.load_policy(tmp_path / "project")


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ({}, 120.0),
        ({"pre_push_mutation_seconds": 0}, 0.0),
        ({"pre_push_mutation_seconds": 30}, 30.0),
    ],
)
def test_load_policy_defaults_and_accepts_the_mutation_budget(
    tmp_path: Path, configured: dict[str, object], expected: float
) -> None:
    _write(tmp_path / "project", **configured)
    loaded = shipping.load_policy(tmp_path / "project")
    assert loaded is not None
    assert loaded["pre_push_mutation_seconds"] == expected


@pytest.mark.parametrize(
    ("configured", "expected"), [({}, "local"), ({"pre_push_checks": "ci"}, "ci")]
)
def test_load_policy_defaults_the_push_checks_to_local_and_accepts_ci(
    tmp_path: Path, configured: dict[str, object], expected: str
) -> None:
    _write(tmp_path / "project", **configured)
    loaded = shipping.load_policy(tmp_path / "project")
    assert loaded is not None
    assert loaded["pre_push_checks"] == expected


HISTORY_GATE = {"name": "history", "role": "secrets-history", "command": ["gitleaks"]}
CHECK_WORKFLOW = (
    "on: [pull_request]\njobs:\n  c:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - run: python3 .hooks/hard-eng.py check\n"
)


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ("no-workflow", "runs `hard-eng.py check`"),
        ("workflow-without-check", "runs `hard-eng.py check`"),
        ("no-history-gate", "secrets-history gate"),
        ("history-scan-off", "secrets-history gate"),
        ("ready", None),
    ],
)
def test_ci_push_checks_need_a_check_workflow_and_a_history_scan(
    tmp_path: Path, row: str, message: str | None
) -> None:
    root = tmp_path / "project"
    _write(root, pre_push_checks="ci")
    workflows = root / ".github/workflows"
    workflows.mkdir(parents=True)
    if row != "no-workflow":
        text = (
            "on: [push]\njobs: {}\n"
            if row == "workflow-without-check"
            else CHECK_WORKFLOW
        )
        (workflows / "ci.yml").write_text(text)
    config = cast(
        GateConfig,
        {
            "packages": [],
            "shared": [] if row == "no-history-gate" else [HISTORY_GATE],
            "scan_git_history": row != "history-scan-off",
        },
    )
    if message is None:
        ci_jobs.load_checked_policy(root, config)
        return
    with pytest.raises(shipping.ShippingError, match=message):
        ci_jobs.load_checked_policy(root, config)


CALLER = "on:\n  pull_request:\njobs:\n  check:\n    uses: ./.github/workflows/hard-eng.yml\n"
CALLED = CHECK_WORKFLOW.replace("on: [pull_request]", "on: workflow_call")
OTHER = "on:\n  pull_request:\njobs:\n  build:\n    runs-on: ubuntu-latest\n"


@pytest.mark.parametrize(
    ("caller", "accepted"),
    [(CALLER, True), (OTHER, False), (CALLER.replace("pull_request", "push"), False)],
    ids=["called-by-pull-request", "never-called", "called-by-push-only"],
)
def test_a_workflow_with_only_workflow_call_counts_when_a_pull_request_workflow_calls_it(
    tmp_path: Path, caller: str, accepted: bool
) -> None:
    root = tmp_path / "project"
    _write(root, pre_push_checks="ci")
    workflows = root / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "hard-eng.yml").write_text(CALLED)
    (workflows / "pull-request.yml").write_text(caller)
    config = cast(GateConfig, {"packages": [], "shared": [HISTORY_GATE]})
    if accepted:
        ci_jobs.load_checked_policy(root, config)
        return
    with pytest.raises(shipping.ShippingError, match="calls one that has only"):
        ci_jobs.load_checked_policy(root, config)
