"""Plan stage rules: an explicit Draft pause before Stop exempts unfinished planning, and the fields an edited plan must carry."""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import agent_hooks
import pytest
from conftest import SOURCE, commit, git, init
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


def test_draft_and_complete_agree_that_none_period_has_no_blockers(
    tmp_path: Path, completed_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(draft_plan(completed_plan, "Clarification", "None."))
    with pytest.raises(ValueError, match="Clarification needs concrete Blockers"):
        validate_plan(path)
    path.write_text(completed_plan.replace("Blockers: None", "Blockers: None."))
    assert validate_plan(path) == "Complete"


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
    (repository / ".gitignore").write_text(".hard-eng/\n__pycache__/\n")
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


@pytest.mark.parametrize(
    "unchanged,handoff,blockers",
    [
        (False, "Approval", "user must choose the affected workflow"),
        (False, "Approval", "None"),
        (False, "Missing", "user must choose the affected workflow"),
        (True, "Approval", "user must choose the affected workflow"),
    ],
)
def test_draft_stop_blocks_until_the_plan_has_a_valid_handoff(
    repository: Path,
    completed_plan: str,
    unchanged: bool,
    handoff: str,
    blockers: str,
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
    assert response.get("decision") == "block"
    assert ("Handoff" if handoff == "Missing" else "ux_reference") in str(response)


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


def test_unchanged_draft_session_gets_a_freshness_note_without_blocking(
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
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    agent_hooks.session_context(repository, payload)
    monkeypatch.setattr(update, "latest_verified", Mock(side_effect=AssertionError))
    response = agent_hooks.completion(repository, payload, "codex")
    assert response.get("decision") != "block"
    assert "approval handoff prepared" in str(response["systemMessage"])
    assert "freshness unknown" in str(response["systemMessage"])


def test_changed_plans_need_single_source_and_retro(
    tmp_path: Path, completed_plan: str
) -> None:
    """Only plans a change edits take the newer fields, so untouched plans still pass."""
    path = tmp_path / "PLAN.md"
    no_source = re.sub(r"(?m)^Single source:.*\n", "", completed_plan)
    no_retro = re.sub(r"(?m)^Retro:.*\n", "", completed_plan)
    ready = no_retro.replace("Status: Complete", "Status: Ready").replace(
        "- [x]", "- [ ]"
    )
    unticked = no_source.replace("Status: Complete", "Status: Ready")
    for text in (no_source, unticked.replace("- [x]", "- [ ]")):
        path.write_text(text)
        with pytest.raises(ValueError, match="Single source"):
            validate_plan(path)
        assert validate_plan(path, changed=False) in {"Ready", "Complete"}
    path.write_text(no_retro)
    with pytest.raises(ValueError, match="Retro"):
        validate_plan(path)
    path.write_text(ready)
    assert validate_plan(path) == "Ready"
    template = (SOURCE / ".agents/skills/he-plan/templates/PLAN.md").read_text()
    assert "\nSingle source: " in template and "\nRetro: " in template


def test_a_plan_untouched_since_the_hard_eng_update_skips_the_newer_fields(
    tmp_path: Path, completed_plan: str
) -> None:
    """A long-lived branch differs from its base in every plan; only later edits bind."""
    root = tmp_path / "project"
    init(root)
    (root / "README.md").write_text("base\n")
    commit(root, "base")
    marker = root / ".hooks/hard-eng-source.json"
    marker.parent.mkdir()
    plan = root / "features/old/PLAN.md"
    plan.parent.mkdir(parents=True)
    old = re.sub(r"(?m)^(Single source|Retro):.*\n", "", completed_plan)

    def dated(day: int, message: str) -> None:
        stamp = f"2026-11-0{day}T12:00:00+00:00"
        git(root, "add", ".")
        subprocess.run(
            ["git", "commit", "-qm", message],
            cwd=root,
            check=True,
            env={**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp},
        )

    plan.write_text(old)
    dated(1, "finish the old plan")
    marker.write_text('{"revision": "new"}\n')
    dated(2, "update Hard Eng")
    assert validate_plan(plan) == "Complete"
    plan.write_text(old.replace("Result: Passed", "Result: Passed\n", 1))
    with pytest.raises(ValueError, match="Single source"):
        validate_plan(plan)
    dated(3, "edit the old plan after the update")
    with pytest.raises(ValueError, match="Single source"):
        validate_plan(plan)
