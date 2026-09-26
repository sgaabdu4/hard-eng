"""Require an explicit Draft pause before Stop exempts unfinished planning."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import agent_hooks
import pytest
from conftest import SOURCE, git
from gate_config import JsonObject
from plans import validate_plan


def draft_plan(
    completed_plan: str, handoff: str, blockers: str, *, pending_ux: bool = True
) -> str:
    plan = (
        completed_plan.replace("Status: Complete", "Status: Draft")
        .replace("Blockers: None", f"Blockers: {blockers}")
        .replace("Handoff: Approval", f"Handoff: {handoff}")
    )
    if pending_ux:
        return plan.replace(
            "N/A — fixture commands have no visual interface.",
            "Result: Pending\nEvidence: Required mock remains missing.",
        )
    return plan


def test_design_system_mock_can_explain_absent_baseline(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(
        visual_plan.replace(
            "Surface: Existing — /account, rendered by app/account/page.tsx",
            "Surface: Mock — design-system account card in app/ui/account-card.tsx",
        ).replace(
            "Before: ![Before](https://example.test/account-before.png)",
            "Before: N/A — design-system mock has no app capture.",
        )
    )
    assert validate_plan(path) == "Complete"


@pytest.mark.parametrize(
    "handoff,blockers,error",
    [
        ("Clarification", "None", "Clarification"),
        ("Approval", "[TODO: decision]", "placeholder"),
        ("Unclear", "choose the affected policy", "Handoff"),
    ],
)
def test_draft_handoff_requires_the_declared_boundary(
    tmp_path: Path, completed_plan: str, handoff: str, blockers: str, error: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(draft_plan(completed_plan, handoff, blockers))
    with pytest.raises(ValueError, match=error):
        validate_plan(path)


def test_draft_clarification_can_pause_without_ux(
    tmp_path: Path, completed_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(
        draft_plan(completed_plan, "Clarification", "choose the affected policy")
    )
    assert validate_plan(path) == "Draft"


def test_approval_stop_rejects_placeholder_despite_passed_baseline(
    repository: Path, completed_plan: str
) -> None:
    (repository / "PLAN.md").write_text(
        draft_plan(
            completed_plan, "Approval", "choose the affected policy", pending_ux=False
        ).replace("Verify fixture command exits; no product release.", "[TODO: scope]")
    )
    response = agent_hooks.completion(repository, {}, "codex")
    assert response.get("decision") == "block"
    assert "placeholder" in str(response["systemMessage"])


@pytest.mark.parametrize("pending_baseline", [False, True])
def test_native_stop_only_pauses_ready_approval(
    repository: Path, completed_plan: str, pending_baseline: bool
) -> None:
    shutil.copytree(SOURCE / ".hooks", repository / ".hooks")
    for name in ("PRODUCT.md", "DESIGN.md"):
        shutil.copyfile(SOURCE / name, repository / name)
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "native hooks")
    plan = draft_plan(
        completed_plan, "Approval", "choose the affected policy", pending_ux=False
    )
    if pending_baseline:
        plan = plan.replace("Result: Passed", "Result: Pending", 1)
    (repository / "PLAN.md").write_text(plan)
    result = subprocess.run(
        [sys.executable, str(repository / ".hooks/hard-eng.py"), "stop", "codex"],
        cwd=repository,
        input="{}",
        text=True,
        capture_output=True,
        check=True,
    )
    response = json.loads(result.stdout)
    if pending_baseline:
        assert response["decision"] == "block"
        assert "Baseline + execution" in response["systemMessage"]
    else:
        assert "decision" not in response
        assert "approval handoff prepared" in response["systemMessage"]


@pytest.mark.parametrize("unchanged", [False, True])
@pytest.mark.parametrize(
    "handoff,blockers,blocked",
    [
        ("Clarification", "user must choose the affected workflow", False),
        ("Approval", "user must choose the affected workflow", True),
        ("Approval", "None", True),
        ("Missing", "user must choose the affected workflow", True),
    ],
)
def test_draft_stop_requires_handoff_before_exempting_questions(
    repository: Path,
    completed_plan: str,
    unchanged: bool,
    handoff: str,
    blockers: str,
    blocked: bool,
) -> None:
    plan = draft_plan(completed_plan, handoff, blockers)
    if handoff == "Missing":
        plan = plan.replace("Handoff: Missing\n", "")
    (repository / "PLAN.md").write_text(plan)
    hooks = repository / ".hooks"
    hooks.mkdir()
    (hooks / "hard-eng.py").write_text("print('Draft check passed')\n")
    payload: JsonObject = {"session_id": "known"}
    if unchanged:
        subprocess.run(["git", "add", "."], cwd=repository, check=True)
        subprocess.run(["git", "commit", "-qm", "draft"], cwd=repository, check=True)
        (repository / ".git/info/exclude").write_text(".hard-eng/\n")
        agent_hooks.session_context(repository, payload)
    response = agent_hooks.completion(repository, payload, "codex")
    assert "Planning incomplete" in str(response)
    if blocked:
        assert response.get("decision") == "block"
        assert ("Handoff" if handoff == "Missing" else "ux_reference") in str(response)
    else:
        assert response.get("decision") != "block"
        assert "user must choose" in str(response)


def test_clarification_cannot_exempt_an_invalid_approval_plan(
    repository: Path, completed_plan: str
) -> None:
    (repository / "PLAN.md").write_text(
        draft_plan(completed_plan, "Clarification", "choose the prerequisite")
    )
    approval = repository / "features/approval/PLAN.md"
    approval.parent.mkdir(parents=True)
    approval.write_text(draft_plan(completed_plan, "Approval", "choose the policy"))
    response = agent_hooks.completion(repository, {}, "codex")
    assert response.get("decision") == "block"
    assert "features/approval/PLAN.md" in str(response["systemMessage"])


def test_unchanged_draft_session_only_warns_about_a_stale_install(
    repository: Path, completed_plan: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import update

    plan = draft_plan(completed_plan, "Approval", "None", pending_ux=False)
    (repository / "PLAN.md").write_text(plan)
    (repository / ".hooks").mkdir()
    marker = repository / ".hooks/hard-eng-source.json"
    marker.write_text(json.dumps({"revision": "a" * 40}))
    git(repository, "add", ".")
    git(repository, "commit", "-qm", "draft")
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    payload: JsonObject = {"session_id": "known"}
    agent_hooks.session_context(repository, payload)
    monkeypatch.setattr(update, "latest_verified", lambda _: "b" * 40)
    response = agent_hooks.completion(repository, payload, "codex")
    assert response.get("decision") != "block"
    assert "approval handoff prepared" in str(response)
    assert "freshness" in str(response)
