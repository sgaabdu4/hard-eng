"""The workflow template that setup writes into a project."""

import json
import shutil
from pathlib import Path
from types import ModuleType

import gate_config
import pytest
import yaml
from ci_setup import configure_ci
from conftest import SOURCE, WORKFLOW_TEMPLATE, configure
from gate_config import Gate, GateConfig, Group, affected_groups
from shards import split_test_shards
from test_shards import serve

OLD_PATH = ".github/workflows/hard-eng.yml"


def release_tree(tmp_path: Path, relative: str) -> Path:
    """A release tree that holds the template only at this path."""
    tree = tmp_path / "release"
    (tree / relative).parent.mkdir(parents=True)
    shutil.copy(WORKFLOW_TEMPLATE, tree / relative)
    return tree


def suite_config(shards: int | None, seconds: int = 600) -> GateConfig:
    suite: Gate = {
        "name": "tests",
        "role": "tests",
        "command": ["uv", "run", "pytest"],
        "report": {"type": "python-tests", "tests": "j.xml", "coverage": "c.json"},
    }
    if shards:
        suite["shards"] = shards
    config: GateConfig = {
        "packages": [{"path": ".", "language": "python", "checks": [suite]}],
        "shared": [],
    }
    config["shipping"] = {
        "base": "main",
        "checks": ["hard-eng"],
        "ui_paths": [],
        "ci_seconds": seconds,
        "pre_push_seconds": 600,
        "delivery": [],
    }
    return config


def generated(tmp_path: Path, source: Path, config: GateConfig | None = None) -> str:
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    (project / "uv.lock").write_text("")
    config = config if config is not None else suite_config(None)
    (project / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}
    configure_ci(project, source, config, changes)
    return changes[OLD_PATH]


def test_a_project_without_shards_gets_the_one_job_workflow(tmp_path: Path) -> None:
    text = generated(tmp_path, release_tree(tmp_path, ".github/hard-eng.yml"))
    assert list(yaml.safe_load(text)["jobs"]) == ["hard-eng"]
    assert "--shard" not in text


def test_an_older_release_tree_still_gives_the_template(tmp_path: Path) -> None:
    text = generated(tmp_path, release_tree(tmp_path, OLD_PATH))
    assert list(yaml.safe_load(text)["jobs"]) == ["hard-eng"]


def test_shards_split_the_ci_job_into_checks_tests_and_the_gate_job(
    tmp_path: Path,
) -> None:
    text = generated(tmp_path, SOURCE, suite_config(3))
    jobs = yaml.safe_load(text)["jobs"]
    assert list(jobs) == ["checks", "tests", "hard-eng"]
    assert jobs["tests"]["strategy"]["matrix"] == {"shard": [1, 2, 3]}
    assert jobs["hard-eng"]["needs"] == ["checks", "tests"]
    commands = {
        name: [step.get("run", "") for step in job["steps"]]
        for name, job in jobs.items()
    }
    assert (
        sum(
            'check --base "$BASE_SHA" --shard rest' in run for run in commands["checks"]
        )
        == 2
    )
    assert (
        sum(
            'check --base "$BASE_SHA" --shard "$SHARD"' in run
            for run in commands["tests"]
        )
        == 2
    )
    assert not any("--shard" in run for run in commands["checks"][:1])
    assert 'check --base "$BASE_SHA" --shard merge' in commands["hard-eng"][-1]
    assert jobs["tests"]["env"]["SHARD"] == "${{ matrix.shard }}"
    upload = jobs["tests"]["steps"][-1]
    assert upload["with"]["name"] == "hard-eng-shard-${{ matrix.shard }}"
    assert upload["with"]["path"] == "coverage/shards"
    assert upload["with"]["if-no-files-found"] == "ignore"
    assert "if" not in upload
    download = jobs["hard-eng"]["steps"][1]
    assert download["with"] == {
        "pattern": "hard-eng-shard-*",
        "merge-multiple": True,
        "path": "coverage/shards",
    }


def test_shard_jobs_inherit_the_budget_timeout_and_the_gate_job_keeps_five(
    tmp_path: Path,
) -> None:
    jobs = yaml.safe_load(generated(tmp_path, SOURCE, suite_config(2, 1200)))["jobs"]
    assert {name: job["timeout-minutes"] for name, job in jobs.items()} == {
        "checks": 20,
        "tests": 20,
        "hard-eng": 5,
    }


def installed(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "project" / OLD_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return tmp_path / "project"


def rewritten(project: Path, config: GateConfig) -> str:
    changes: dict[str, str] = {}
    configure_ci(project, SOURCE, config, changes)
    return changes[OLD_PATH]


def test_a_changed_shard_count_rewrites_the_shard_list(tmp_path: Path) -> None:
    project = installed(tmp_path, generated(tmp_path, SOURCE, suite_config(3)))
    jobs = yaml.safe_load(rewritten(project, suite_config(4)))["jobs"]
    assert jobs["tests"]["strategy"]["matrix"] == {"shard": [1, 2, 3, 4]}


def test_update_splits_an_installed_one_job_workflow(tmp_path: Path) -> None:
    one_job = generated(tmp_path, SOURCE, suite_config(None))
    project = installed(tmp_path, one_job)
    jobs = yaml.safe_load(rewritten(project, suite_config(3)))["jobs"]
    assert list(jobs) == ["checks", "tests", "hard-eng"]


def test_a_split_workflow_gets_a_note_and_no_shards(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    custom = (
        generated(tmp_path, SOURCE, suite_config(None)) + "  extra:\n    runs-on: x\n"
    )
    assert split_test_shards(suite_config(3), custom) == custom
    assert capsys.readouterr().err == (
        "CI shards not added: .github/workflows/hard-eng.yml is customised or split. "
        "Split its hard-eng job into the checks, tests and hard-eng jobs of Hard "
        "Eng's own workflow, or remove shards.\n"
    )


def test_setup_refuses_shards_on_a_gate_that_does_not_run_pytest(
    tmp_path: Path,
) -> None:
    config = suite_config(3)
    config["packages"][0]["checks"][0]["command"] = ["sh", "-c", "pytest -q"]
    with pytest.raises(ValueError, match="shards split pytest suites only"):
        generated(tmp_path, SOURCE, config)


def provisioned_nothing(*_arguments: object) -> None:
    return None


def test_a_run_that_selects_no_package_passes_in_the_gate_job_with_no_download(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jobs = yaml.safe_load(generated(tmp_path, SOURCE, suite_config(2)))["jobs"]
    upload = next(
        s for s in jobs["tests"]["steps"] if "upload-artifact" in s.get("uses", "")
    )
    download = next(
        s for s in jobs["hard-eng"]["steps"] if "download-artifact" in s.get("uses", "")
    )
    assert "if" not in upload
    assert "if" not in download
    configure(runner.ROOT, [])
    monkeypatch.setattr(gate_config, "load_groups", serve([]))
    monkeypatch.setattr(runner, "provision_tools", provisioned_nothing)
    for shard in ("1", "2", "merge"):
        assert runner.check(base="0" * 40, shard=shard) == 0
    kept = sorted(
        path.relative_to(runner.ROOT).as_posix()
        for path in (runner.ROOT / "coverage/shards").rglob("*")
        if path.is_file()
    )
    assert kept == ["coverage/shards/1/ran.txt", "coverage/shards/2/ran.txt"]


OWN_GATES = SOURCE / "hard-eng.gates.json"


def test_own_workflow_is_the_generated_shard_form() -> None:
    config = json.loads(OWN_GATES.read_text())
    expected = split_test_shards(config, WORKFLOW_TEMPLATE.read_text())
    assert (SOURCE / OLD_PATH).read_text() == expected
    assert list(yaml.safe_load(expected)["jobs"]) == ["checks", "tests", "hard-eng"]


@pytest.mark.parametrize("name", [".github/hard-eng.yml", OLD_PATH])
def test_an_edit_under_github_selects_the_package_checks(
    repository: Path, name: str
) -> None:
    config = json.loads(OWN_GATES.read_text())
    groups: list[Group] = [
        *config["packages"],
        {"path": ".", "checks": config["shared"]},
    ]
    (repository / name).parent.mkdir(parents=True, exist_ok=True)
    (repository / name).write_text("name: edited\n")
    chosen = affected_groups(repository, groups, "HEAD")
    assert "tests" in [gate["name"] for group in chosen for gate in group["checks"]]
