"""Reject the observed false readiness and closure cases through the real gate."""

import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from plans import validate_plan, validate_plans


@pytest.mark.parametrize(
    "old,new,error",
    [
        ("Result: Passed", "Result: Blocked", "Result"),
        ("Blockers: None", "Blockers: browser unavailable", "Blockers"),
        ("- [x]", "- [ ]", "unchecked"),
        ("- [x]", "- [\t]", "unchecked"),
        ("- [x]", "- []", "unchecked"),
        ("- [x]", "- [?]", "unchecked"),
        ("N/A — fixture commands have no visual interface.", "N/A", "reason"),
        ("N/A — temporary fixture is removed by pytest.", "- [x] N/A", "reason"),
        ("N/A — temporary fixture is removed by pytest.", "Risks are N/A", "reason"),
        ("N/A — temporary fixture is removed by pytest.", "|Risk|N/A|", "reason"),
        (
            "Verify fixture command exits; no product release.",
            "<Outcome>",
            "placeholder",
        ),
        ("## Repository context", "## Missing context", "Repository context"),
        ("Status: Complete", "Status: Approved", "Status"),
        ("Evidence:", "Missing evidence:", "Evidence"),
        (
            "Controlled fixture baseline; not production acceptance.",
            "Pending",
            "Evidence",
        ),
        (
            "Controlled fixture baseline; not production acceptance.",
            "<actual verification evidence>",
            "placeholder",
        ),
        (
            "Controlled fixture baseline; not production acceptance.",
            "TODO",
            "placeholder",
        ),
    ],
)
def test_invalid_completion(
    tmp_path: Path, completed_plan: str, old: str, new: str, error: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(completed_plan.replace(old, new))
    with pytest.raises(ValueError, match=error):
        validate_plan(path)


def test_ready_requires_baseline_and_rendered_evidence(
    tmp_path: Path, completed_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    ready = completed_plan.replace("Status: Complete", "Status: Ready").replace(
        "- [x]", "- [ ]"
    )
    path.write_text(ready)
    assert validate_plan(path) == "Ready"
    for result in ("Blocked", "Pending", "N/A — unavailable browser"):
        path.write_text(
            ready.replace(
                "N/A — fixture commands have no visual interface.", f"Result: {result}"
            )
        )
        with pytest.raises(ValueError, match="Result"):
            validate_plan(path)
    path.write_text(ready.replace("Result: Passed", "Result: Blocked", 1))
    with pytest.raises(ValueError, match="Result"):
        validate_plan(path)


def test_exception_requires_authorization_and_impact(
    tmp_path: Path, completed_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    text = completed_plan.replace("Result: Passed", "Result: Exception", 1)
    path.write_text(text)
    with pytest.raises(ValueError, match="Authorization"):
        validate_plan(path)
    text = text.replace("One test actor.", "Authorization: Explicit fixture exception.")
    path.write_text(text)
    with pytest.raises(ValueError, match="Impact"):
        validate_plan(path)
    path.write_text(
        text.replace("Authorization:", "Impact: Fixture limitation.\nAuthorization:")
    )
    assert validate_plan(path) == "Complete"
    path.write_text(path.read_text().replace("Explicit fixture exception.", "Pending"))
    with pytest.raises(ValueError, match="Authorization"):
        validate_plan(path)


def test_changed_work_cannot_reuse_historical_complete_plan(
    runner: ModuleType, tmp_path: Path
) -> None:
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=tmp_path,
        check=True,
    )
    validate_plans(tmp_path)
    validate_plans(tmp_path, stage="Complete")
    (tmp_path / "new.py").write_text("print('new work')\n")
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(tmp_path)
    plan = tmp_path / "PLAN.md"
    plan.write_text(plan.read_text().replace("Status: Complete", "Status: Ready"))
    with pytest.raises(ValueError, match="requires Complete"):
        validate_plans(tmp_path)
    validate_plans(tmp_path, stage="Ready")
    plan.write_text(plan.read_text().replace("Status: Ready", "Status: Draft"))
    validate_plans(tmp_path, stage="Draft")
    with pytest.raises(ValueError, match="requires Ready"):
        validate_plans(tmp_path, stage="Ready")


def test_planning_only_can_stop_before_implementation(
    runner: ModuleType, tmp_path: Path, completed_plan: str
) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "--allow-empty",
            "-qm",
            "baseline",
        ],
        cwd=tmp_path,
        check=True,
    )
    path = tmp_path / "PLAN.md"
    path.write_text(completed_plan.replace("Status: Complete", "Status: Ready"))
    # This fixture has only Markdown files: stopping for approval is legitimate.
    validate_plans(tmp_path)
    with pytest.raises(ValueError, match="requires Complete"):
        validate_plans(tmp_path, stage="Complete")
    (tmp_path / "app.py").write_text("print('implementation')\n")
    with pytest.raises(ValueError, match="requires Complete"):
        validate_plans(tmp_path)


def test_feature_plan_is_selected_without_unrelated_draft(
    runner: ModuleType, tmp_path: Path, completed_plan: str
) -> None:
    root_plan = tmp_path / "PLAN.md"
    root_plan.write_text(completed_plan.replace("Status: Complete", "Status: Draft"))
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "unrelated planning",
        ],
        cwd=tmp_path,
        check=True,
    )
    feature = tmp_path / "features/current/plan.md"
    feature.parent.mkdir(parents=True)
    feature.write_text(completed_plan)
    (tmp_path / "app.py").write_text("print('current work')\n")
    validate_plans(tmp_path)


def test_native_cli_plan_stage_and_missing_plan(
    runner: ModuleType, tmp_path: Path
) -> None:
    source = Path(__file__).resolve().parents[1]
    hooks = tmp_path / ".hooks"
    hooks.mkdir()
    for path in (source / ".hooks").glob("*.py"):
        (hooks / path.name).write_bytes(path.read_bytes())
    (tmp_path / "hard-eng.gates.json").write_text(
        '{"packages": [], "shared": [{"name": "fixture", '
        '"command": ["' + sys.executable + '", "-c", "print(123)"]}]}'
    )
    command = [sys.executable, str(hooks / "hard-eng.py"), "check"]
    assert (
        subprocess.run(
            command, cwd=tmp_path, capture_output=True, check=False
        ).returncode
        == 0
    )
    result = subprocess.run(
        command + ["--base", "missing-comparison-base"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1 and "Cannot verify plan scope" in result.stderr
    assert (
        subprocess.run(
            command + ["--base", "0" * 40],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    plan = tmp_path / "PLAN.md"
    plan.write_text(plan.read_text().replace("Status: Complete", "Status: Draft"))
    result = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1 and "requires Complete" in result.stderr
    assert (
        subprocess.run(
            command + ["--plan-stage", "Draft"],
            cwd=tmp_path,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    plan.unlink()
    result = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1 and "applicable PLAN" in result.stderr
