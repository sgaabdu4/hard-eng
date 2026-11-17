"""An update replaces the annotations gate of an earlier install, so no project goes red because of a release."""

import json
from pathlib import Path
from types import ModuleType

import pytest
import update
from conftest import SOURCE
from resolved_settings import validate_resolved
from test_setup import repository

OLD_BANNED = [
    "--config",
    'lint.flake8-tidy-imports.banned-api."typing.Any".msg = "Use a precise type instead of Any"',
    "--config",
    'lint.flake8-tidy-imports.banned-api."typing_extensions.Any".msg = "Use a precise type instead of Any"',
]


def python_project(root: Path) -> None:
    repository(root)
    (root / "package.json").unlink()
    (root / "uv.lock").touch()
    (root / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="1"\n')
    (root / "main.py").write_text("value = 1\n")


def annotations(root: Path) -> list[tuple[str, list[str]]]:
    config = json.loads((root / "hard-eng.gates.json").read_text())
    return [
        (gate["role"], gate["command"])
        for gate in config["packages"][0]["checks"]
        if "annotations" in gate["role"]
    ]


def rewrite(root: Path, command: list[str]) -> None:
    path = root / "hard-eng.gates.json"
    config = json.loads(path.read_text())
    for gate in config["packages"][0]["checks"]:
        if gate["role"] == "annotations":
            gate["command"] = command
    path.write_text(json.dumps(config))


def judge(root: Path) -> None:
    groups = json.loads((root / "hard-eng.gates.json").read_text())["packages"]
    validate_resolved(root, groups, 900)


def test_an_update_replaces_the_old_two_line_banned_api_gate(
    installer: ModuleType, tmp_path: Path
) -> None:
    """HE-NO-SWITCH-OFF: the release changed the template's banned-api form; an installed gate with the old one ends with the new one and passes the judge."""
    python_project(tmp_path)
    installer.install(tmp_path)
    new = annotations(tmp_path)[0][1]
    old = [*new[:-2], *OLD_BANNED]
    rewrite(tmp_path, old)
    assert annotations(tmp_path)[0][1] == old
    installer.install(tmp_path)
    assert annotations(tmp_path) == [("annotations", new)]
    judge(tmp_path)


def test_an_annotations_gate_that_the_template_gate_covers_is_retired(
    installer: ModuleType, tmp_path: Path
) -> None:
    """One source of truth: a project gate whose paths, rules and config all lie inside the template gate is removed, so two copies do not run."""
    python_project(tmp_path)
    installer.install(tmp_path)
    own = ["ruff", "check", "main.py", "--select", "ANN", "--config", OLD_BANNED[1]]
    rewrite(tmp_path, own)
    installer.install(tmp_path)
    gates = annotations(tmp_path)
    assert [role for role, _ in gates] == ["annotations"]
    assert gates[0][1] != own
    judge(tmp_path)


def test_an_annotations_gate_that_adds_a_rule_is_kept_and_named(
    installer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A project gate that adds something the template lacks stays, with one printed line that names it."""
    python_project(tmp_path)
    installer.install(tmp_path)
    own = [
        "ruff",
        "check",
        "main.py",
        "--select",
        "ANN,E501",
        "--config",
        OLD_BANNED[1],
    ]
    rewrite(tmp_path, own)
    capsys.readouterr()
    installer.install(tmp_path)
    gates = annotations(tmp_path)
    assert [role for role, _ in gates] == ["project-annotations", "annotations"]
    assert gates[0][1] == own
    lines = [line for line in capsys.readouterr().err.splitlines() if "E501" in line]
    assert len(lines) == 1
    assert "adds E501" in lines[0]
    judge(tmp_path)


def test_a_gate_with_the_annotations_role_and_one_entry_is_refused_with_the_fix(
    installer: ModuleType, tmp_path: Path
) -> None:
    python_project(tmp_path)
    installer.install(tmp_path)
    rewrite(tmp_path, [*annotations(tmp_path)[0][1][:-2], *OLD_BANNED[:2]])
    with pytest.raises(
        ValueError, match=r"one `--config` banned-api table[\s\S]*typing_extensions"
    ):
        judge(tmp_path)


def test_an_update_plan_stays_json_when_it_retires_an_annotations_gate(
    installer: ModuleType, tmp_path: Path
) -> None:
    """HE-NO-SWITCH-OFF: the update reads the plan from the standard output of setup, so a retired gate is told on the error output only."""
    python_project(tmp_path)
    installer.install(tmp_path)
    own = [
        "ruff",
        "check",
        "src",
        "tests",
        "--select",
        "ANN",
        "--config",
        OLD_BANNED[1],
    ]
    rewrite(tmp_path, own)
    changes, _, _, _ = update.update_plan(tmp_path, SOURCE, SOURCE)
    assert "hard-eng.gates.json" in changes
