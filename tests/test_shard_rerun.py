"""A setup rerun at the installed release writes the workflow form that the gates file asks for."""

import json
from pathlib import Path

import pytest
import update
from conftest import commit, git
from gate_config import json_file
from test_update_runner import GATES_FILE, add_shipping_policy, installed_python_project

WORKFLOW = ".github/workflows/hard-eng.yml"


def set_shards(project: Path, count: int) -> None:
    config = json.loads((project / GATES_FILE).read_text())
    for group in config["packages"]:
        for gate in group["checks"]:
            if gate.get("role") == "tests":
                gate.pop("shards", None)
                if count:
                    gate["shards"] = count
    (project / GATES_FILE).write_text(json_file(project, config))
    commit(project, "the shard count")


def test_a_setup_rerun_writes_the_workflow_form_that_the_shards_field_asks_for(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    add_shipping_policy(project)
    update.update(project, repair=True)
    one_job = (project / WORKFLOW).read_text()
    assert "hard-eng-checks" not in one_job
    set_shards(project, 2)
    assert WORKFLOW in update.update(project, repair=True)
    split = (project / WORKFLOW).read_text()
    assert "name: hard-eng-checks" in split
    assert "shard: [1, 2]" in split
    assert git(project, "status", "--porcelain") == ""
    assert update.update(project, repair=True).endswith("available.")
    set_shards(project, 3)
    update.update(project, repair=True)
    assert "shard: [1, 2, 3]" in (project / WORKFLOW).read_text()
    set_shards(project, 0)
    update.update(project, repair=True)
    assert (project / WORKFLOW).read_text() == one_job
