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
import change_size
import plans
import pytest
from conftest import SOURCE, add_origin, commit, git, init, ux_rules_block
from gate_config import JsonObject
from plans import usability_rules, validate_plan


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


def dated(root: Path, day: int, message: str) -> None:
    stamp = f"2026-11-0{day}T12:00:00+00:00"
    git(root, "add", ".")
    subprocess.run(
        ["git", "commit", "-qm", message],
        cwd=root,
        check=True,
        env={**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp},
    )


def finished_before_the_update(root: Path, text: str) -> Path:
    init(root)
    (root / "README.md").write_text("base\n")
    commit(root, "base")
    plan = root / "features/old/PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(text)
    dated(root, 1, "finish the plan")
    marker = root / ".hooks/hard-eng-source.json"
    marker.parent.mkdir()
    marker.write_text('{"revision": "new"}\n')
    dated(root, 2, "update Hard Eng")
    return plan


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

    plan.write_text(old)
    dated(root, 1, "finish the old plan")
    marker.write_text('{"revision": "new"}\n')
    dated(root, 2, "update Hard Eng")
    assert validate_plan(plan) == "Complete"
    plan.write_text(old.replace("Result: Passed", "Result: Passed\n", 1))
    with pytest.raises(ValueError, match="Single source"):
        validate_plan(plan)
    dated(root, 3, "edit the old plan after the update")
    with pytest.raises(ValueError, match="Single source"):
        validate_plan(plan)


def rules_plan(visual_plan: str, **verdicts: str) -> str:
    return visual_plan.replace(ux_rules_block(), ux_rules_block(**verdicts))


def test_the_rule_labels_come_from_the_ux_reference() -> None:
    rules = usability_rules()
    labels = [label for label, _ in rules]
    reference = (SOURCE / ".agents/skills/he-plan/references/ux.md").read_text()
    assert len(rules) == 13
    assert {"No clutter", "Hierarchy", "Observe"} <= set(labels)
    assert {label: units for label, units in rules if units} == {
        "Least effort": ["clicks"],
        "No clutter": ["kept", "removed"],
    }
    assert all(f"  - {label}" in reference for label in labels)


def test_a_passed_ux_record_without_rules_is_refused(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace(ux_rules_block(), ""))
    with pytest.raises(ValueError, match="UX Rules is missing; judge the inspected"):
        validate_plan(path)


def test_a_ux_record_that_skips_a_rule_names_the_rule(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    skipped = visual_plan.replace("- Observe: Pass — checked\n", "")
    path.write_text(
        skipped.replace(
            "- Widths: Pass — checked",
            "- Widths: Pass — checked\n- Widths: Pass — again",
        )
    )
    with pytest.raises(ValueError) as error:
        validate_plan(path)
    assert str(error.value).removeprefix("ux_reference: ") == (
        "UX Rules needs one `- <rule>: Pass|Fail|N/A — text` line for each Usability rule; "
        "no line: Observe; two lines: Widths; "
        "add a line for each rule of .agents/skills/he-plan/references/ux.md; "
        "the rule lines stand in one block below `Rules:` with no empty line between them"
    )


def test_a_ux_record_with_a_fail_cannot_be_passed(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(rules_plan(visual_plan, Hierarchy="Fail — two strong buttons"))
    with pytest.raises(ValueError, match="UX Rules: Hierarchy is Fail; fix the design"):
        validate_plan(path)


@pytest.mark.parametrize(
    ("rule", "verdict", "message"),
    [
        ("No_clutter", "Pass — checked at 375 px", "No clutter needs.*kept.*removed"),
        ("No_clutter", "Pass — 7 kept", "No clutter needs.*removed.*3 kept, 3 removed"),
        ("Least_effort", "Pass — 2 steps to save", "Least effort needs.*clicks"),
        ("Least_effort", "Pass — clicks counted", "Least effort needs.*clicks"),
    ],
    ids=["no-numbers", "one-unit-missing", "wrong-unit", "no-number"],
)
def test_a_count_rule_needs_its_counts(
    tmp_path: Path, visual_plan: str, rule: str, verdict: str, message: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(rules_plan(visual_plan, **{rule: verdict}))
    with pytest.raises(ValueError, match=f"UX Rules: {message}"):
        validate_plan(path)


@pytest.mark.parametrize(
    ("rule", "verdict"),
    [
        ("Least_effort", "Pass — 2 clicks to save a note"),
        ("Least_effort", "Pass — 1 click to save a note"),
        ("No_clutter", "Pass — 7 KEPT, 3 Removed"),
        ("No_clutter", "N/A — no new elements"),
        ("Least_effort", "N/A — no journey changes"),
    ],
)
def test_a_count_rule_passes_with_its_counts_or_a_reason(
    tmp_path: Path, visual_plan: str, rule: str, verdict: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(rules_plan(visual_plan, **{rule: verdict}))
    assert validate_plan(path) == "Complete"


def test_a_failed_count_rule_needs_no_count(tmp_path: Path, visual_plan: str) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(rules_plan(visual_plan, No_clutter="Fail — a helper sentence"))
    with pytest.raises(ValueError, match="UX Rules: No clutter is Fail"):
        validate_plan(path)


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("- Hierarchy: Pass — checked\n- Colour: Pass — checked", "not a rule: Colour"),
        ("- Hierarchy: Maybe — checked", "Hierarchy.*Pass, Fail or N/A"),
        ("- Hierarchy: Pass —", "Hierarchy.*text after the dash"),
        ("- Hierarchy: Pass checked", "Hierarchy.*dash"),
        ("Hierarchy is fine", "no line: .*Hierarchy"),
    ],
    ids=["unknown-rule", "unknown-verdict", "no-text", "no-dash", "no-label"],
)
def test_an_unknown_rule_line_is_refused(
    tmp_path: Path, visual_plan: str, line: str, message: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace("- Hierarchy: Pass — checked", line))
    with pytest.raises(ValueError, match=f"UX Rules.*{message}") as error:
        validate_plan(path)
    if "no-text" in message or "text after" in message:
        assert "Pass, Fail or N/A" not in str(error.value)


def test_every_bad_rule_line_is_named_in_one_refusal(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    bad = "- Observe: Maybe — x\n- Hierarchy: Pass\n- Colour: Pass — x"
    plan = visual_plan.replace("- Observe: Pass — checked\n", "")
    path.write_text(plan.replace("- Hierarchy: Pass — checked", bad))
    with pytest.raises(ValueError, match="UX Rules") as error:
        validate_plan(path)
    for name in ("Observe", "Hierarchy", "Colour"):
        assert name in str(error.value)
    assert str(error.value).count("UX Rules") == 1


def block_lines(block: str, kind: str) -> str:
    lines = block.splitlines()
    forms = {
        "star": "\n".join(line.replace("- ", "* ", 1) for line in lines[1:]),
        "indent": "\n".join("  " + line for line in lines[1:]),
        "hyphen": "\n".join(line.replace(" — ", " - ", 1) for line in lines[1:]),
        "wrapped": "\n".join(line.replace(" — ", " —\n  ", 1) for line in lines[1:]),
        "note": "\n".join(lines[1:]) + "\n\n- Note: judged by hand",
        "plain": "\n".join(lines[1:]),
    }
    return "Rules:\n" + forms[kind]


@pytest.mark.parametrize(
    "kind", ["star", "indent", "hyphen", "wrapped", "note", "plain"]
)
def test_rule_lines_may_use_the_usual_forms_below_an_empty_rules_label(
    tmp_path: Path, visual_plan: str, kind: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(
        visual_plan.replace(ux_rules_block(), block_lines(ux_rules_block(), kind))
    )
    assert validate_plan(path) == "Complete"


def test_the_refusals_print_the_reference_path_from_the_project_root(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace(ux_rules_block(), ""))
    with pytest.raises(ValueError, match="UX Rules is missing") as error:
        validate_plan(path)
    assert "of .agents/skills/he-plan/references/ux.md" in str(error.value)
    path.write_text(visual_plan.replace("- Observe: Pass — checked\n", ""))
    with pytest.raises(ValueError, match="UX Rules needs") as error:
        validate_plan(path)
    assert "of .agents/skills/he-plan/references/ux.md" in str(error.value)


def test_a_ux_record_with_one_line_for_each_rule_passes(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan)
    assert validate_plan(path) == "Complete"
    path.write_text(visual_plan.replace("Status: Complete", "Status: Ready"))
    assert validate_plan(path) == "Ready"


def test_an_unchanged_complete_plan_without_rules_still_passes(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace(ux_rules_block(), ""))
    assert validate_plan(path, changed=False) == "Complete"


def test_a_changed_complete_plan_from_before_the_update_passes_without_rules(
    tmp_path: Path, visual_plan: str
) -> None:
    plan = finished_before_the_update(
        tmp_path / "project", visual_plan.replace(ux_rules_block(), "")
    )
    assert validate_plan(plan) == "Complete"


def test_a_complete_plan_edited_after_the_update_needs_rules(
    tmp_path: Path, visual_plan: str
) -> None:
    root = tmp_path / "project"
    plan = finished_before_the_update(root, visual_plan.replace(ux_rules_block(), ""))
    plan.write_text(plan.read_text() + "\nReopened for new work.\n")
    dated(root, 3, "edit the plan after the update")
    with pytest.raises(ValueError, match="UX Rules is missing"):
        validate_plan(plan)


def test_a_missing_ux_reference_names_the_step(
    tmp_path: Path, visual_plan: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(plans, "UX_REFERENCE", "gone/ux.md")
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan)
    with pytest.raises(
        ValueError, match="gone/ux.md.*`git checkout HEAD -- gone/ux.md`"
    ):
        validate_plan(path)


def test_a_ready_plan_from_before_the_update_needs_rules(
    tmp_path: Path, visual_plan: str
) -> None:
    text = visual_plan.replace(ux_rules_block(), "").replace(
        "Status: Complete", "Status: Ready"
    )
    plan = finished_before_the_update(tmp_path / "project", text)
    with pytest.raises(ValueError, match="UX Rules is missing"):
        validate_plan(plan)


def test_a_draft_approval_plan_from_before_the_update_needs_rules(
    tmp_path: Path, visual_plan: str
) -> None:
    root = tmp_path / "project"
    text = draft_plan(
        visual_plan.replace(ux_rules_block(), ""), "Approval", "None", pending_ux=False
    )
    finished_before_the_update(root, text)
    notice, _ = plans.planning_feedback(root, {"features/old/PLAN.md"})
    assert "UX Rules is missing" in notice


def git_starts(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []
    real = plans._git_output

    def counted(root: Path, *args: str) -> str:
        calls.append(args)
        return real(root, *args)

    monkeypatch.setattr(plans, "_git_output", counted)
    return calls


@pytest.mark.parametrize(
    ("state", "starts"),
    [("draft", 0), ("ready", 0), ("complete", 3), ("complete-bare", 3)],
)
def test_the_age_of_an_old_plan_costs_git_starts_only_for_a_complete_plan(
    tmp_path: Path,
    visual_plan: str,
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    starts: int,
) -> None:
    root = tmp_path / "project"
    text = visual_plan.replace(ux_rules_block(), "")
    if state == "draft":
        text = draft_plan(text, "Approval", "None", pending_ux=False)
    if state == "ready":
        text = text.replace("Status: Complete", "Status: Ready")
    if state == "complete-bare":
        text = re.sub(r"(?m)^(Single source|Retro):.*\n", "", text)
    plan = finished_before_the_update(root, text)
    calls = git_starts(monkeypatch)
    if state == "draft":
        plans.planning_feedback(root, {"features/old/PLAN.md"})
    elif state == "ready":
        with pytest.raises(ValueError, match="UX Rules is missing"):
            validate_plan(plan)
    else:
        assert validate_plan(plan) == "Complete"
    assert len(calls) == starts


def test_a_plan_from_before_the_update_that_holds_rules_is_still_judged(
    tmp_path: Path, visual_plan: str
) -> None:
    text = rules_plan(visual_plan, Hierarchy="Fail — two strong buttons")
    plan = finished_before_the_update(tmp_path / "project", text)
    with pytest.raises(ValueError, match="UX Rules: Hierarchy is Fail; fix the design"):
        validate_plan(plan)


def test_a_ready_plan_edited_after_the_update_needs_rules(
    tmp_path: Path, visual_plan: str
) -> None:
    root = tmp_path / "project"
    text = visual_plan.replace(ux_rules_block(), "").replace(
        "Status: Complete", "Status: Ready"
    )
    plan = finished_before_the_update(root, text)
    plan.write_text(text + "\nReopened for new work.\n")
    dated(root, 3, "edit the plan after the update")
    with pytest.raises(ValueError, match="UX Rules is missing"):
        validate_plan(plan)


def test_a_new_ready_plan_needs_rules(tmp_path: Path, visual_plan: str) -> None:
    root = tmp_path / "project"
    finished_before_the_update(root, visual_plan)
    plan = root / "features/new/PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(
        visual_plan.replace(ux_rules_block(), "").replace(
            "Status: Complete", "Status: Ready"
        )
    )
    with pytest.raises(ValueError, match="UX Rules is missing"):
        validate_plan(plan)


def test_the_step_named_by_a_missing_ux_reference_repairs_the_checkout(
    release: tuple[Path, Path, str],
    visual_plan: str,
) -> None:
    _, target, _ = release
    add_origin(target)
    git(target, "switch", "-qc", "feature/work")
    (target / "PLAN.md").write_text(
        visual_plan.replace("Status: Complete", "Status: Ready")
    )
    reference = target / ".agents/skills/he-plan/references/ux.md"
    reference.unlink()
    command = [
        sys.executable,
        "-c",
        (
            "import sys; sys.path.insert(0, '.hooks'); from plans import validate_plan; "
            "from pathlib import Path; print(validate_plan(Path('PLAN.md')))"
        ),
    ]
    refused = subprocess.run(
        command, cwd=target, capture_output=True, text=True, check=False
    )
    assert refused.returncode == 1
    step = refused.stderr.split("`")[1]
    subprocess.run(step.split(), cwd=target, check=True)
    assert reference.is_file()
    assert (
        subprocess.run(command, cwd=target, capture_output=True, check=False).returncode
        == 0
    )
    assert git(target, "branch", "--show-current").strip() == "feature/work"


@pytest.mark.parametrize(
    "marked",
    [
        "- Least effort (count: clicks): Pass — 4 clicks",
        "- Least effort (count: steps): Pass — 4 clicks",
        "- Least effort: Pass — 4 clicks",
    ],
    ids=["marker", "wrong-marker-text", "plain"],
)
def test_a_rule_label_may_carry_its_marker(
    tmp_path: Path, visual_plan: str, marked: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace("- Least effort: Pass — 4 clicks", marked))
    assert validate_plan(path) == "Complete"


def test_a_ready_plan_with_a_passed_ux_record_needs_rules(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(
        visual_plan.replace(ux_rules_block(), "").replace(
            "Status: Complete", "Status: Ready"
        )
    )
    with pytest.raises(ValueError, match="UX Rules is missing"):
        validate_plan(path)


def test_a_draft_approval_plan_with_a_passed_ux_record_needs_rules(
    tmp_path: Path, visual_plan: str
) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "PLAN.md").write_text(
        draft_plan(
            visual_plan.replace(ux_rules_block(), ""),
            "Approval",
            "None",
            pending_ux=False,
        )
    )
    notice, unfinished = plans.planning_feedback(root, {"PLAN.md"})
    assert unfinished and "UX Rules is missing" in notice


def test_the_rule_labels_are_read_from_the_reference_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = (SOURCE / plans.UX_REFERENCE).read_text()
    last = "  - Performance:"
    assert last in text
    copy = tmp_path / "ux.md"
    copy.write_text(text.replace(last, "  - Extra: one more rule.\n" + last, 1))
    monkeypatch.setattr(plans, "UX_REFERENCE", str(copy))
    labels = [label for label, _ in usability_rules()]
    assert len(labels) == 14 and "Extra" in labels


def test_a_bracket_and_colon_in_the_free_text_is_not_a_marker(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    line = "- No clutter: Pass — 7 kept, 3 removed (counted on the 375 px image): the history note moved behind a tap"
    path.write_text(visual_plan.replace("- No clutter: Pass — 4 kept, 4 removed", line))
    assert line in path.read_text()
    assert validate_plan(path) == "Complete"


def test_a_failed_rule_with_its_marker_is_judged_as_failed(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    marked = "- No clutter (count: kept, removed): Fail — a helper sentence"
    path.write_text(
        visual_plan.replace("- No clutter: Pass — 4 kept, 4 removed", marked)
    )
    with pytest.raises(ValueError, match="UX Rules: No clutter is Fail"):
        validate_plan(path)


def test_an_empty_line_inside_the_rule_lines_names_the_block_step(
    tmp_path: Path, visual_plan: str
) -> None:
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace("- Observe:", "\n- Observe:", 1))
    with pytest.raises(ValueError, match="no line: Observe") as error:
        validate_plan(path)
    assert "one block below `Rules:` with no empty line between them" in str(
        error.value
    )


def test_a_rule_block_below_one_empty_line_is_read_as_the_template_writes_it(
    tmp_path: Path, visual_plan: str
) -> None:
    template = (SOURCE / ".agents/skills/he-plan/templates/PLAN.md").read_text()
    assert "\nRules:\n\n- [TODO" in template
    path = tmp_path / "PLAN.md"
    path.write_text(visual_plan.replace("Rules:\n", "Rules:\n\n", 1))
    assert validate_plan(path) == "Complete"


@pytest.mark.parametrize("label", ["**Rules:**", "- Rules:"])
def test_a_rules_label_in_another_form_says_the_field_starts_with_rules(
    tmp_path: Path, visual_plan: str, label: str
) -> None:
    path = tmp_path / "PLAN.md"
    plan = visual_plan.replace("\nRules: Judged", f"\n{label} Judged")
    assert label in plan
    path.write_text(plan)
    with pytest.raises(ValueError, match="UX Rules is missing") as error:
        validate_plan(path)
    assert "a line that starts with `Rules:`" in str(error.value)


OLD_NAME = "features/old/PLAN.md"
TABLE = "| Step | Result |\n| --- | --- |\n| one | pass |\n"


def plan_from_before_newer_fields(completed_plan: str) -> str:
    old = re.sub(r"(?m)^(Same cause|Single source|Retro):.*\n", "", completed_plan)
    return old.replace("The test creates", TABLE + "The test creates", 1)


def formatted_again(text: str) -> str:
    """What a formatter does to a plan: empty lines between sections and a longer table rule."""
    return text.replace("\n## ", "\n\n## ").replace(
        "| --- | --- |", "| ------ | ------ |"
    )


def old_plan_in_a_repository(root: Path, completed_plan: str) -> tuple[str, str]:
    old = plan_from_before_newer_fields(completed_plan)
    finished_before_the_update(root, old)
    return old, git(root, "rev-parse", "HEAD")


def test_a_reformatted_old_complete_plan_counts_as_unchanged(
    tmp_path: Path, completed_plan: str
) -> None:
    root = tmp_path / "project"
    old, base = old_plan_in_a_repository(root, completed_plan)
    (root / OLD_NAME).write_text(formatted_again(old))
    assert "Same cause" in str(
        pytest.raises(ValueError, validate_plan, root / OLD_NAME).value
    )
    assert plans.validate_plans(root, base) == "Draft"
    changed, _, applicable = change_size.judged_plans(root, base, {OLD_NAME})
    assert OLD_NAME not in changed and applicable == []


@pytest.mark.parametrize("change", ["a word added", "two words joined", "a new plan"])
def test_a_word_change_or_a_new_plan_still_needs_todays_fields(
    tmp_path: Path, completed_plan: str, change: str
) -> None:
    root = tmp_path / "project"
    old, base = old_plan_in_a_repository(root, completed_plan)
    text = formatted_again(old)
    name = OLD_NAME
    if change == "a word added":
        text = text.replace("Verify fixture", "Verify the fixture")
    if change == "two words joined":
        text = text.replace("Verify fixture", "Verifyfixture")
    if change == "a new plan":
        name = "features/new/PLAN.md"
        (root / name).parent.mkdir(parents=True)
    (root / name).write_text(text)
    with pytest.raises(ValueError, match="Same cause"):
        plans.validate_plans(root, base)


def test_a_reformatted_old_plan_does_not_cover_new_code(
    tmp_path: Path, completed_plan: str
) -> None:
    root = tmp_path / "project"
    old, base = old_plan_in_a_repository(root, completed_plan)
    (root / OLD_NAME).write_text(formatted_again(old))
    (root / "app.py").write_text("".join(f"line {n}\n" for n in range(60)))
    with pytest.raises(ValueError, match="applicable PLAN"):
        plans.validate_plans(root, base)


def test_a_passing_changed_complete_plan_starts_no_word_comparison(
    tmp_path: Path, completed_plan: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    finished_before_the_update(root, completed_plan)
    base = git(root, "rev-parse", "HEAD")
    (root / OLD_NAME).write_text(completed_plan.replace("Verify", "Check", 1))
    calls: list[tuple[str, ...]] = []
    real = change_size._git_output

    def counted(directory: Path, *args: str) -> str:
        calls.append(args)
        return real(directory, *args)

    monkeypatch.setattr(change_size, "_git_output", counted)
    changed, _, applicable = change_size.judged_plans(root, base, {OLD_NAME})
    assert OLD_NAME in changed and len(applicable) == 1
    assert not [args for args in calls if args[0] == "show"]
