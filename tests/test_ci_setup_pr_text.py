"""Setup installs the PR text check beside any workflow of the project."""

import json
from pathlib import Path

import pytest
from ci_setup import PR_TEXT, configure_github_ci
from gate_config import parse_config

SOURCE = Path(__file__).resolve().parents[1]


_OWN_WORKFLOW = "on: pull_request\njobs:\n  quality:\n    runs-on: ubuntu-latest\n"


@pytest.mark.parametrize(
    ("files", "arrives"),
    [
        ({"quality.yml": _OWN_WORKFLOW}, True),
        ({"quality.yaml": _OWN_WORKFLOW}, True),
        ({"quality.yml": _OWN_WORKFLOW, "pr-text.yml": "stale\n"}, True),
        ({"quality.yml": _OWN_WORKFLOW, "pr-text.yml": "SOURCE"}, False),
        ({}, False),
        ({"pr-text.yml": "stale\n"}, False),
        ({"notes.txt": "not a workflow\n"}, False),
    ],
)
def test_pr_text_check_is_installed_beside_any_workflow_of_the_project(
    tmp_path: Path, files: dict[str, str], arrives: bool
) -> None:
    text = (SOURCE / PR_TEXT).read_text()
    directory = tmp_path / ".github/workflows"
    directory.mkdir(parents=True)
    for name, content in files.items():
        (directory / name).write_text(text if content == "SOURCE" else content)
    config = parse_config(json.dumps({"packages": [], "shared": []}))
    changes: dict[str, str] = {}

    configure_github_ci(tmp_path, SOURCE, config, changes)

    assert changes == ({PR_TEXT: text} if arrives else {})
