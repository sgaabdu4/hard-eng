"""Reject the observed false readiness and closure cases through the real gate."""

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from conftest import SOURCE, git
from gate_config import GateConfig
from plans import validate_plan, validate_plans
from shipping import ShippingPolicy


@pytest.mark.parametrize("status", ["Ready", "Complete"])
def test_runtime_journey_cannot_disappear_behind_nonvisual_ux(
    tmp_path: Path, completed_plan: str, status: str
) -> None:
    path = tmp_path / "PLAN.md"
    plan = completed_plan.replace("Status: Complete", f"Status: {status}")
    e2e = next(line for line in plan.splitlines() if line.startswith("E2E:"))
    path.write_text(plan.replace(e2e, ""))
    with pytest.raises(ValueError, match="E2E"):
        validate_plan(path)
    path.write_text(
        plan.replace(
            e2e,
            "E2E: Required — complete and rebook through the browser; confirm retained history",
        )
    )
    if status == "Complete":
        with pytest.raises(ValueError, match="E2E is still Required"):
            validate_plan(path)
    else:
        assert validate_plan(path) == status
    path.write_text(plan.replace(e2e, "E2E: Passed — Pending browser access"))
    with pytest.raises(ValueError, match="actual runtime evidence"):
        validate_plan(path)
    path.write_text(plan)
    assert validate_plan(path) == status


@pytest.mark.parametrize("target", ["PR", "Merge", "Deploy"])
def test_deployment_journey_keeps_delivery_open(
    runner: ModuleType, shipping_policy: ShippingPolicy, target: str
) -> None:
    path = runner.ROOT / "PLAN.md"
    content = path.read_text()
    e2e = next(line for line in content.splitlines() if line.startswith("E2E:"))
    path.write_text(
        content.replace(
            e2e, "E2E: Delivery — rebook on the deployed revision and verify history"
        )
        + f"\nDelivery target: {target}\n"
    )
    config = runner.ROOT / "hard-eng.gates.json"
    config.write_text(json.dumps({"shipping": shipping_policy}))
    with pytest.raises(ValueError, match="delivery checks"):
        validate_plans(runner.ROOT, base="0" * 40, stage="Complete")
    if target == "Deploy":
        shipping_policy["delivery"] = [
            {
                "name": "journey",
                "command": [sys.executable, "-c", "raise SystemExit(1)"],
            }
        ]
        config.write_text(json.dumps({"shipping": shipping_policy}))
        # Build readiness schedules this verifier; it cannot claim deployed proof.
        assert (
            validate_plans(runner.ROOT, base="0" * 40, stage="Complete") == "Complete"
        )


@pytest.mark.parametrize(
    "stage,message",
    [
        ("Ready", "ready for build"),
        ("Complete", "ready for ship"),
        (None, "ready for ship"),
    ],
)
@pytest.mark.parametrize("lockfiles", [False, True])
def test_stage_handoff_only_follows_successful_gate(
    runner: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    stage: str | None,
    message: str,
    lockfiles: bool,
) -> None:
    config: GateConfig = {
        "packages": [],
        "shared": [{"name": "verify", "command": [sys.executable, "-c", "pass"]}],
    }
    if lockfiles:
        config["shared"][0]["role"] = "lockfiles"
    path = tmp_path / "hard-eng.gates.json"
    path.write_text(json.dumps(config))
    assert runner.check(plan_stage=stage) == 0
    assert message in capsys.readouterr().out
    config["shared"][0]["command"][-1] = "raise SystemExit(1)"
    path.write_text(json.dumps(config))
    assert runner.check(plan_stage=stage) == 1
    output = capsys.readouterr().out
    assert message not in output
    assert "next stage is blocked" in output


def test_complete_delivery_requires_shipping_configuration(
    runner: ModuleType, shipping_policy: ShippingPolicy
) -> None:
    root = runner.ROOT
    validate_plans(root, base="0" * 40, stage="Complete")
    plan = root / "PLAN.md"
    plan.write_text(plan.read_text() + "\nDelivery target: Merge\nDelivery: Pending\n")
    with pytest.raises(ValueError, match="shipping"):
        validate_plans(root, base="0" * 40, stage="Complete")
    (root / "hard-eng.gates.json").write_text(json.dumps({"shipping": shipping_policy}))
    validate_plans(root, base="0" * 40, stage="Complete")


@pytest.mark.parametrize("stage", ["Ready", "Complete"])
def test_deploy_plan_requires_verifier_before_handoff(
    runner: ModuleType, shipping_policy: ShippingPolicy, stage: str
) -> None:
    root = runner.ROOT
    plan = root / "PLAN.md"
    plan.write_text(
        plan.read_text().replace("Status: Complete", f"Status: {stage}")
        + "\nDelivery target: Deploy\nDelivery: Pending\n"
    )
    config = root / "hard-eng.gates.json"
    config.write_text(json.dumps({"shipping": shipping_policy}))
    with pytest.raises(ValueError, match="Deploy target requires configured delivery"):
        validate_plans(root, base="0" * 40, stage=stage)
    shipping_policy["delivery"] = [
        {"name": "production", "command": [sys.executable, "-c", "raise SystemExit(1)"]}
    ]
    config.write_text(json.dumps({"shipping": shipping_policy}))
    assert validate_plans(root, base="0" * 40, stage=stage) == stage


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


@pytest.mark.parametrize("status", ["Ready", "Complete"])
def test_ready_requires_baseline_and_rendered_evidence(
    tmp_path: Path, completed_plan: str, visual_plan: str, status: str
) -> None:
    path = tmp_path / "PLAN.md"
    ready = completed_plan.replace("Status: Complete", f"Status: {status}")
    if status == "Ready":
        ready = ready.replace("- [x]", "- [ ]")
    path.write_text(ready)
    assert validate_plan(path) == status
    for result in ("Blocked", "Pending", "N/A — unavailable browser"):
        path.write_text(
            ready.replace(
                "N/A — fixture commands have no visual interface.", f"Result: {result}"
            )
        )
        with pytest.raises(ValueError, match="Result"):
            validate_plan(path)
    visual = ready.replace(
        "N/A — fixture commands have no visual interface.",
        "Result: Passed\nEvidence: Rendered proposal inspected at the affected size.",
    )
    path.write_text(visual)
    with pytest.raises(ValueError, match="Markdown image reference"):
        validate_plan(path)
    path.write_text(
        visual.replace(
            "Rendered proposal inspected at the affected size.",
            "![Proposed state](https://example.test/proposed.png) inspected at the affected size.",
        )
    )
    with pytest.raises(ValueError, match="Surface"):
        validate_plan(path)
    path.write_text(visual_plan.replace("Status: Complete", f"Status: {status}"))
    assert validate_plan(path) == status
    path.write_text(ready.replace("Result: Passed", "Result: Blocked", 1))
    with pytest.raises(ValueError, match="Result"):
        validate_plan(path)


@pytest.mark.parametrize("name", ["Surface", "Before", "Proposed", "Capture", "Review"])
def test_visual_readiness_requires_capture_context(
    tmp_path: Path, visual_plan: str, name: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(
        "\n".join(
            line for line in visual_plan.splitlines() if not line.startswith(f"{name}:")
        )
    )
    with pytest.raises(ValueError, match=name):
        validate_plan(path)


@pytest.mark.parametrize("name", ["Capture", "Review"])
def test_pending_capture_or_review_cannot_establish_readiness(
    tmp_path: Path, visual_plan: str, name: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(
        "\n".join(
            f"{name}: Pending browser access" if line.startswith(f"{name}:") else line
            for line in visual_plan.splitlines()
        )
    )
    with pytest.raises(ValueError, match=name):
        validate_plan(path)


def test_new_app_can_explain_absent_baseline_but_existing_screen_cannot(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    missing_before = visual_plan.replace(
        "Before: ![Before](https://example.test/account-before.png)",
        "Before: N/A — greenfield app has no prior screen; concept uses the supplied brief.",
    )
    path.write_text(missing_before)
    with pytest.raises(ValueError, match="Before"):
        validate_plan(path)
    path.write_text(missing_before.replace("Surface: Existing", "Surface: New"))
    assert validate_plan(path) == "Complete"


def test_same_image_cannot_represent_a_visible_change(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace("account-proposed.png", "account-before.png"))
    with pytest.raises(ValueError, match="distinct"):
        validate_plan(path)


@pytest.mark.parametrize(
    "state",
    [
        "incomplete",
        "question",
        "unchanged-question",
        "question-template",
        "question-code",
        "question-code-parked",
    ],
)
def test_native_stop_reports_incomplete_visual_planning(
    repository: Path, completed_plan: str, state: str
) -> None:
    question = state != "incomplete"
    shutil.copytree(
        SOURCE / ".hooks",
        repository / ".hooks",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    for name in ("PRODUCT.md", "DESIGN.md"):
        shutil.copyfile(SOURCE / name, repository / name)
    (repository / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [
                    {
                        "name": "fixture-check",
                        "command": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; Path('checked').touch()",
                        ],
                    }
                ],
            }
        )
    )
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "native hooks")
    (repository / "PLAN.md").write_text(
        completed_plan.replace("Status: Complete", "Status: Draft")
        .replace(
            "Blockers: None",
            "Blockers: choose the target screen" if question else "Blockers: None",
        )
        .replace(
            "N/A — fixture commands have no visual interface.",
            "Result: Passed\nEvidence: Only a prose description; actual screen capture is missing.",
        )
        + "\n## Historical example\n\nBlockers: obsolete example outside decisions\n"
    )
    if state == "question":
        (repository / ".git/info/exclude").write_text(".hard-eng/\n")
        captures = repository / ".hard-eng/ux"
        captures.mkdir(parents=True)
        (captures / "proposal.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>'
        )
    if state == "question-template":
        plan = repository / "PLAN.md"
        plan.write_text(plan.read_text() + "\n[TODO: Fill after the user answers]\n")
    if state == "question-code-parked":
        plan = repository / "PLAN.md"
        parked = repository / "features/parked/PLAN.md"
        parked.parent.mkdir(parents=True)
        plan.rename(parked)
        plan.write_text(completed_plan)
        git(repository, "add", ".")
        git(repository, "commit", "-qm", "parked question")
    if state.startswith("question-code"):
        (repository / "app.py").write_text("print('implementation')\n")
    if state == "unchanged-question":
        git(repository, "add", "PLAN.md")
        git(repository, "commit", "-qm", "question")
        (repository / ".git/info/exclude").write_text(".hard-eng/\n")
        session = repository / ".hard-eng/sessions/acceptance.json"
        session.parent.mkdir(parents=True)
        session.write_text(json.dumps({"base": git(repository, "rev-parse", "HEAD")}))
    result = subprocess.run(
        [sys.executable, "-B", str(repository / ".hooks/hard-eng.py"), "stop", "codex"],
        cwd=repository,
        input=json.dumps({"session_id": "acceptance"}),
        text=True,
        capture_output=True,
        check=True,
    )
    response = json.loads(result.stdout)
    if state.startswith("question-code"):
        assert response.get("decision") == "block"
        assert "requires Complete" in response["reason"]
        return
    assert "Planning incomplete" in response["systemMessage"]
    assert "Markdown image" in response["systemMessage"]
    assert (response.get("decision") == "block") is not question
    assert not (repository / "checked").exists()


@pytest.mark.parametrize("status", ["Ready", "Complete"])
def test_baseline_waiver_cannot_authorize_feature_work(
    tmp_path: Path, completed_plan: str, status: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(
        completed_plan.replace("Status: Complete", f"Status: {status}")
        .replace("Result: Passed", "Result: Exception", 1)
        .replace(
            "One test actor.",
            "Authorization: Explicit fixture waiver.\nImpact: Known failing baseline.",
        )
    )
    with pytest.raises(ValueError, match="Result"):
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
    assert validate_plans(tmp_path) == "Ready"
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
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "baseline",
        ],
        cwd=tmp_path,
        check=True,
    )
    stopped = subprocess.run(
        command[:-1] + ["stop", "codex"],
        input="{}",
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ready for ship" in json.loads(stopped.stdout)["systemMessage"]
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
    completed = plan.read_text()
    e2e = next(line for line in completed.splitlines() if line.startswith("E2E:"))
    plan.write_text(completed.replace(e2e, ""))
    result = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 1 and "E2E" in result.stderr
    plan.write_text(completed)
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
