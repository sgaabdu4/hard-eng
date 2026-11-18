"""Strict loading of the shipping policy in hard-eng.gates.json."""

import json
from pathlib import Path
from typing import cast

import ci_jobs
import pytest
import shipping
import workflow_blocking
import yaml
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
CI_CONFIG = cast(GateConfig, {"packages": [], "shared": [HISTORY_GATE]})


def _ci_project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "project"
    _write(root, pre_push_checks="ci")
    workflows = root / ".github/workflows"
    workflows.mkdir(parents=True)
    return root, workflows


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
    root, workflows = _ci_project(tmp_path)
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
    root, workflows = _ci_project(tmp_path)
    (workflows / "hard-eng.yml").write_text(CALLED)
    (workflows / "pull-request.yml").write_text(caller)
    if accepted:
        ci_jobs.load_checked_policy(root, CI_CONFIG)
        return
    with pytest.raises(shipping.ShippingError, match="calling the one that has only"):
        ci_jobs.load_checked_policy(root, CI_CONFIG)


FILTERED_CALLER = (
    "on:\n  pull_request:\n    {filter}\njobs:\n  check:\n    {gate}"
    "uses: ./.github/workflows/hard-eng.yml\n"
)


@pytest.mark.parametrize(
    ("filter_line", "gate", "named"),
    [
        ("paths: ['src/**']", "", "paths"),
        ("branches: [main]", "", "branches"),
        ("types: [opened]", "", "types"),
        ("branches-ignore: [wip]", "", "branches-ignore"),
        ("paths-ignore: ['docs/**']", "", "paths-ignore"),
        ("", "if: github.actor != 'bot'\n    ", "if"),
    ],
)
def test_a_called_check_workflow_is_refused_when_the_caller_filters_or_conditions_the_run(
    tmp_path: Path, filter_line: str, gate: str, named: str
) -> None:
    root, workflows = _ci_project(tmp_path)
    (workflows / "hard-eng.yml").write_text(CALLED)
    caller = FILTERED_CALLER.format(filter=filter_line, gate=gate)
    (workflows / "pull-request.yml").write_text(
        caller.replace("    \njobs", "jobs") if not filter_line else caller
    )
    with pytest.raises(shipping.ShippingError, match=rf"`{named}`"):
        ci_jobs.load_checked_policy(root, CI_CONFIG)


def test_a_check_workflow_with_a_filtered_pull_request_trigger_is_refused(
    tmp_path: Path,
) -> None:
    root, workflows = _ci_project(tmp_path)
    filtered = CHECK_WORKFLOW.replace(
        "on: [pull_request]", "on:\n  pull_request:\n    paths: ['src/**']"
    )
    (workflows / "hard-eng.yml").write_text(filtered)
    with pytest.raises(shipping.ShippingError, match="`paths`"):
        ci_jobs.load_checked_policy(root, CI_CONFIG)


STEP = "    steps:\n      - run: python3 .hooks/hard-eng.py check\n"


@pytest.mark.parametrize(
    "workflow",
    [
        CHECK_WORKFLOW.replace("on: [pull_request]", "on: [push]"),
        CHECK_WORKFLOW.replace(
            "on: [pull_request]", "on:\n  push:\n    branches: [main]"
        ),
        CHECK_WORKFLOW.replace("    runs-on", "    if: false\n    runs-on"),
        CHECK_WORKFLOW.replace(
            STEP, STEP.replace("- run:", "- if: false\n        run:")
        ),
        CHECK_WORKFLOW.replace("check\n", "check --quick\n"),
        CHECK_WORKFLOW.replace("check\n", "check --related-tests\n"),
        CHECK_WORKFLOW.replace("check\n", "check --commit-secrets\n"),
        CHECK_WORKFLOW.replace("check\n", "check --plan-stage Draft\n"),
        CHECK_WORKFLOW.replace("- run: python3", "- run: '# python3").replace(
            "check\n", "check'\n"
        ),
        CHECK_WORKFLOW.replace(
            "  c:\n", "  gate:\n    if: false\n    runs-on: x\n  c:\n    needs: gate\n"
        ),
        CHECK_WORKFLOW.replace(
            "- run: python3", "- run: 'echo skipping # python3"
        ).replace("check\n", "check'\n"),
        CHECK_WORKFLOW.replace(
            STEP,
            "    steps:\n"
            "      - if: x == 'true' && y\n        run: python3 .hooks/hard-eng.py check\n"
            "      - if: x != 'true' && y\n        run: python3 .hooks/hard-eng.py check\n",
        ),
        CHECK_WORKFLOW.replace(
            STEP,
            "    steps:\n"
            "      - if: y&&x == 'true'\n        run: python3 .hooks/hard-eng.py check\n"
            "      - if: y&&x != 'true'\n        run: python3 .hooks/hard-eng.py check\n",
        ),
    ],
    ids=[
        "push-only",
        "push-filtered",
        "job-if",
        "step-if",
        "quick",
        "related-tests",
        "commit-secrets",
        "plan-stage-draft",
        "commented-out",
        "needs-a-conditional-job",
        "inline-comment",
        "paired-conditions-with-and",
        "paired-conditions-with-unspaced-and",
    ],
)
def test_a_workflow_that_does_not_run_the_whole_check_on_every_pull_request_is_refused(
    tmp_path: Path, workflow: str
) -> None:
    root, workflows = _ci_project(tmp_path)
    (workflows / "ci.yml").write_text(workflow)
    with pytest.raises(shipping.ShippingError, match="every pull request"):
        ci_jobs.load_checked_policy(root, CI_CONFIG)


@pytest.mark.parametrize(
    "name", [".github/hard-eng.yml", ".github/workflows/hard-eng.yml"]
)
def test_the_hard_eng_workflows_with_a_docs_only_step_pair_run_the_whole_check(
    name: str,
) -> None:
    source = Path(__file__).resolve().parents[1] / name
    assert ci_jobs.runs_whole_check(yaml.safe_load(source.read_text()))


def test_a_called_check_workflow_is_refused_when_the_calling_job_needs_a_conditional_job(
    tmp_path: Path,
) -> None:
    root, workflows = _ci_project(tmp_path)
    (workflows / "hard-eng.yml").write_text(CALLED)
    (workflows / "pull-request.yml").write_text(
        "on:\n  pull_request:\njobs:\n  gate:\n    if: false\n    runs-on: x\n"
        "  check:\n    needs: gate\n    uses: ./.github/workflows/hard-eng.yml\n"
    )
    with pytest.raises(shipping.ShippingError, match="`if` condition"):
        ci_jobs.load_checked_policy(root, CI_CONFIG)


@pytest.mark.parametrize(
    "workflow",
    [
        CHECK_WORKFLOW.replace(
            "    runs-on", "    if: ${{ !cancelled() }}\n    runs-on"
        ),
        CHECK_WORKFLOW.replace(
            "on: [pull_request]", "on:\n  pull_request:\n    branches: [main, '**']"
        ),
    ],
    ids=["not-cancelled", "branches-with-double-star"],
)
def test_a_condition_or_filter_that_skips_no_pull_request_does_not_refuse_the_workflow(
    tmp_path: Path, workflow: str
) -> None:
    root, workflows = _ci_project(tmp_path)
    (workflows / "ci.yml").write_text(workflow)
    ci_jobs.load_checked_policy(root, CI_CONFIG)


def test_a_branches_filter_with_double_star_and_an_exclusion_is_refused(
    tmp_path: Path,
) -> None:
    root, workflows = _ci_project(tmp_path)
    filtered = CHECK_WORKFLOW.replace(
        "on: [pull_request]", "on:\n  pull_request:\n    branches: ['**', '!main']"
    )
    (workflows / "ci.yml").write_text(filtered)
    with pytest.raises(shipping.ShippingError, match="`branches`"):
        ci_jobs.load_checked_policy(root, CI_CONFIG)


@pytest.mark.parametrize(
    ("patterns", "covers"),
    [
        ("**", True),
        (["**"], True),
        (["main", "**"], True),
        (["**", "!main"], False),
        (["main"], False),
    ],
)
def test_the_one_branch_filter_rule_of_the_workflow_check_covers_every_branch_only_with_double_star_and_no_exclusion(
    patterns: object, covers: bool
) -> None:
    assert workflow_blocking.covers_every_branch(patterns) is covers
