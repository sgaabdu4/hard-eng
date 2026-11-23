"""A root file that is not documentation runs the shared checks; only documentation keeps the secret scan alone."""

import json
from pathlib import Path
from types import ModuleType

import pytest
from conftest import commit
from gate_config import Gate, Group, affected_groups

SECRETS: Gate = {"name": "secrets", "role": "secrets-files", "command": ["x"]}
BUDGET: Gate = {"name": "budget", "role": "custom", "command": ["x"]}


def project(repository: Path) -> list[Group]:
    groups: list[Group] = [
        {"path": "app", "checks": [], "depends_on": []},
        {"path": ".", "checks": [SECRETS, BUDGET]},
    ]
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": groups[:-1], "shared": groups[-1]["checks"]})
    )
    commit(repository, "configuration")
    return groups


@pytest.mark.parametrize(
    ("changed", "checks", "docs_only"),
    [
        ("AGENTS.md", [SECRETS, BUDGET], "false"),
        (".agents/models.json", [SECRETS, BUDGET], "false"),
        ("README.md", [SECRETS], "true"),
        (".agents/skills/x/SKILL.md", [SECRETS], "true"),
        ("CLAUDE.md", [SECRETS], "true"),
        ("docs/notes.md", [SECRETS], "true"),
    ],
)
def test_a_root_file_runs_the_shared_checks_unless_it_is_documentation(
    repository: Path,
    runner: ModuleType,
    capsys: pytest.CaptureFixture[str],
    changed: str,
    checks: list[Gate],
    docs_only: str,
) -> None:
    """Escaped bug: a root AGENTS.md change in a Hard Eng update printed docs_only=true and skipped the root budget check."""
    groups = project(repository)
    path = repository / changed
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("change\n")
    assert affected_groups(repository, groups, "HEAD") == [
        {"path": ".", "checks": checks}
    ]
    runner.__dict__["ROOT"] = repository
    assert runner.impact("HEAD") == 0
    assert f"docs_only={docs_only}\n" in capsys.readouterr().out
