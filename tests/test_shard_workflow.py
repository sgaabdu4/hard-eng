"""The workflow template that setup writes into a project."""

import json
import shutil
from pathlib import Path

import yaml
from ci_setup import configure_ci
from conftest import WORKFLOW_TEMPLATE
from gate_config import GateConfig

OLD_PATH = ".github/workflows/hard-eng.yml"


def release_tree(tmp_path: Path, relative: str) -> Path:
    """A release tree that holds the template only at this path."""
    tree = tmp_path / "release"
    (tree / relative).parent.mkdir(parents=True)
    shutil.copy(WORKFLOW_TEMPLATE, tree / relative)
    return tree


def generated(tmp_path: Path, source: Path) -> str:
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"packageManager":"bun@1.3.0"}')
    config: GateConfig = {"packages": [], "shared": []}
    config["shipping"] = {
        "base": "main",
        "checks": ["hard-eng"],
        "ui_paths": [],
        "ci_seconds": 600,
        "pre_push_seconds": 600,
        "delivery": [],
    }
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
