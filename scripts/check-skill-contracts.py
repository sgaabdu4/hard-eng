#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import io
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from admission_wiring_contracts import check_admission_wiring_contract
from plan_approval_contracts import bind_approved, check_approved_content_lock
from skill_route_contracts import check_plan_stage_parity, check_route_fixtures
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PLAN_STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
CONTEXT_DOCS_PATH = ROOT / "skills/deterministic-checks/scripts/context-docs.py"
WORKTREE_PATH = ROOT / "skills/deterministic-checks/scripts/worktree.py"
STAGE_CHECK_PATHS = (ROOT / "skills/he-plan/scripts/check.py", ROOT / "skills/he-build/scripts/check.py", ROOT / "skills/he-ship/scripts/check.py", ROOT / "skills/e2e/scripts/visual_evidence_regression_check.py", ROOT / "skills/deterministic-checks/scripts/dart_decimate_gate_regression_check.py")
BOUNDED_RUN_CHECK_PATH = ROOT / "skills/deterministic-checks/scripts/bounded_run_regression_check.py"
STATE_INTEGRATION_CHECK_PATH = ROOT / "skills/he/scripts/integration_check.py"
GLOBAL_HOOK_TEST_PATH = ROOT / "scripts/git-hooks/test.sh"
DESIGN_CHECK_PATH = ROOT / "skills/deterministic-checks/scripts/check-design-md.js"
PRODUCT_REFERENCE_PATH = ROOT / "skills/he-plan/references/product.md"
DESIGN_REFERENCE_PATH = ROOT / "skills/atomic-ui/references/design-md.md"
BUILD_AXES_PENDING = "intent-spec:pending,deterministic:pending,tests:pending,review:pending,security:pending,ui-design:pending,e2e-runtime:pending,docs-context:pending,unknowns:pending"
BUILD_AXES_PASS = "intent-spec:pass,deterministic:pass,tests:pass,review:pass,security:pass,ui-design:na,e2e-runtime:pass,docs-context:pass,unknowns:pass"
def fail(message: str) -> None:
    print(f"skill-contracts: {message}", file=sys.stderr)
    raise SystemExit(1)
def load_plan_state():
    spec = importlib.util.spec_from_file_location("hard_eng_plan_state", PLAN_STATE_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def load_context_docs():
    spec = importlib.util.spec_from_file_location("hard_eng_context_docs", CONTEXT_DOCS_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load context-docs.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def load_worktree():
    spec = importlib.util.spec_from_file_location("hard_eng_worktree", WORKTREE_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load worktree.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
def state(module, **changes: str) -> dict[str, str]:
    values = {
        "state_version": "4",
        "plan_id": "fixture",
        "feature_slug": "fixture",
        "repository_root": str(ROOT),
        "branch": "main",
        "base_sha": "0" * 40,
        "head_sha": "0" * 40,
        "updated_at_utc": "2026-01-01T00:00:00Z",
        "lifecycle_status": "planning",
        "current_stage": "plan",
        "plan_stage": module.PLAN_STAGES[0],
        "approved_plan_stages": "none",
        "skipped_plan_stages": "none",
        "stage_status": "in-progress",
        "next_action": "fixture",
        "waiting_for": "agent",
        "plan_approved": "no",
        "approved_plan_digest": "none",
        "open_blockers": "none",
        "open_issues": "none",
        "open_unknowns": "none",
        "active_slice": "none",
        "slice_count": "none",
        "completed_slices": "none",
        "build_round": "0",
        "snapshot_id": "none",
        "artifact_id": "none",
        "build_axes": "none",
        "build_readiness": "none",
        "build_evidence": "none",
    }
    values.update(changes)
    if "approved_plan_digest" not in changes and values["plan_approved"] == "yes":
        values["approved_plan_digest"] = "sha256:" + "f" * 64
    return values
def expect_invalid(module, values: dict[str, str], label: str) -> None:
    try:
        module.validate_values(values)
        module.validate_transition(values)
    except module.PlanStateError:
        return
    fail(f"invalid state accepted: {label}")
def expect_error(module, action, label: str) -> None:
    try:
        action()
    except module.PlanStateError:
        return
    fail(f"invalid checkpoint operation accepted: {label}")
def plan_text(
    module,
    values: dict[str, str],
    rows: tuple[tuple[str, ...], ...] = (),
    learning: tuple[tuple[str, ...], ...] = (),
) -> str:
    state_lines = "\n".join(f"- {key} = {values[key]}" for key in module.REQUIRED)
    item_lines = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    learning_lines = "\n".join("| " + " | ".join(row) + " |" for row in learning)
    text = f"""# fixture

## State
{state_lines}

## Active items
| ID | Type | Evidence | Impact | Owner | Next proof/action | Status |
|---|---|---|---|---|---|---|
{item_lines}

## Learning Candidates
| ID | Trigger | Source | Evidence | Cause | Owner | Required proof | Resolution | Status |
|---|---|---|---|---|---|---|---|---|
{learning_lines}

## Accepted plan
Fixture.
"""
    return bind_approved(module, text)

def check_state_contract(module) -> None:
    for key in ("approved_plan_digest", "slice_count", "completed_slices"):
        if key not in module.REQUIRED:
            fail(f"PLAN state missing: {key}")
    expected_targets = {
        "planning": "$he-plan",
        "build-ready": "$he-build",
        "building": "$he-build",
        "green": "$he-ship",
        "shipping": "$he-ship",
        "shipped": "none",
        "cancelled": "none",
    }
    if module.ROUTE_TARGETS != expected_targets or set(module.LIFECYCLE) != set(expected_targets):
        fail("lifecycle route targets are incomplete or changed")
    expect_invalid(module, {**state(module), "lifecycle_status": "learning"}, "learning lifecycle")
    expect_invalid(module, {**state(module), "current_stage": "learn"}, "learn stage")

    for index, stage in enumerate(module.PLAN_STAGES):
        prefix = module.PLAN_STAGES[:index]
        values = state(
            module,
            plan_stage=stage,
            approved_plan_stages=",".join(prefix) or "none",
            slice_count="2" if index > module.PLAN_STAGES.index("slices") else "none",
        )
        module.validate_values(values)
        module.validate_transition(values)

    invalid_prefix = state(
        module,
        plan_stage="feature",
        approved_plan_stages="repository",
    )
    expect_invalid(module, invalid_prefix, "planning prefix gap")
    expect_invalid(module, {**state(module), "slice_count": "2"}, "slice count before slices")
    slices_state = state(
        module,
        plan_stage="slices",
        approved_plan_stages=",".join(module.PLAN_STAGES[: module.PLAN_STAGES.index("slices")]),
    )
    consistency_state = state(
        module,
        plan_stage="consistency",
        approved_plan_stages=",".join(module.PLAN_STAGES[: module.PLAN_STAGES.index("consistency")]),
        slice_count="2",
    )
    module.validate_state_change(slices_state, consistency_state)

    complete = ",".join(module.PLAN_STAGES)
    ready = state(
        module,
        lifecycle_status="build-ready",
        current_stage="build",
        plan_stage="none",
        approved_plan_stages=complete,
        stage_status="pending",
        plan_approved="yes",
        slice_count="2",
    )
    module.validate_values(ready)
    module.validate_transition(ready)
    expect_invalid(module, {**ready, "open_issues": "I-1"}, "build-ready open item")

    snapshot = "sha256:" + "a" * 64
    building = state(
        module,
        lifecycle_status="building",
        current_stage="build",
        plan_stage="none",
        approved_plan_stages=complete,
        stage_status="in-progress",
        plan_approved="yes",
        active_slice="S-1",
        slice_count="2",
        snapshot_id=snapshot,
        artifact_id=snapshot,
        build_axes=BUILD_AXES_PENDING,
        build_readiness="0",
        build_evidence="stale",
    )
    module.validate_values(building)
    module.validate_transition(building)
    expect_error(
        module,
        lambda: module.validate_state_change(building, {**building, "slice_count": "1", "active_slice": "final", "completed_slices": "S-1"}),
        "post-approval slice count rewrite",
    )
    expect_invalid(module, {**building, "active_slice": "none"}, "building without slice")
    expect_invalid(module, {**building, "snapshot_id": "none"}, "building without snapshot")
    expect_invalid(module, {**building, "artifact_id": "none"}, "building without artifact")
    expect_invalid(module, {**building, "completed_slices": "S-1"}, "active slice already completed")
    expect_invalid(module, {**building, "active_slice": "S-2"}, "skipped first slice")

    inventory = """\n## Slices\n\n| ID | Outcome |\n|---|---|\n| S-1 | First |\n| S-2 | Second |\n"""
    inventory_path = ROOT / "features/fixture/PLAN.md"
    approved = bind_approved(module, plan_text(module, building) + inventory)
    module.validate_document(inventory_path, approved)
    check_approved_content_lock(module, inventory_path, approved, expect_error)
    expect_error(
        module,
        lambda: module.validate_document(
            inventory_path, bind_approved(
                module, plan_text(module, building) + inventory.replace("| S-2 | Second |\n", "")
            )
        ),
        "slice inventory count mismatch",
    )

    second_slice = {**building, "active_slice": "S-2", "completed_slices": "S-1"}
    module.validate_values(second_slice)
    module.validate_transition(second_slice)
    final_build = {**building, "active_slice": "final", "completed_slices": "S-1,S-2"}
    module.validate_values(final_build)
    module.validate_transition(final_build)
    candidate = (
        "L-1", "false-gate", "build I-1", "Verified: false-pass gate", "required context omission",
        "audit controller", "overflow fixture fails closed", "pending", "open",
    )
    module.validate_document(
        inventory_path,
        bind_approved(module, plan_text(module, final_build, learning=(candidate,)) + inventory),
    )

    green = {
        **building,
        "lifecycle_status": "green",
        "current_stage": "ship",
        "stage_status": "pending",
        "active_slice": "none",
        "completed_slices": "S-1,S-2",
        "build_round": "2",
        "build_axes": BUILD_AXES_PASS,
        "build_readiness": "100",
        "build_evidence": "current",
    }
    module.validate_values(green)
    module.validate_transition(green)
    expect_invalid(module, {**green, "build_readiness": "99"}, "green below readiness 100")
    expect_invalid(
        module,
        {**green, "build_axes": BUILD_AXES_PASS.replace("deterministic:pass", "deterministic:fail")},
        "green with failed hard axis",
    )
    expect_invalid(
        module,
        {**green, "build_axes": BUILD_AXES_PASS.replace("review:pass", "review:na")},
        "green without final review",
    )
    expect_invalid(module, {**green, "build_evidence": "stale"}, "green with stale evidence")
    expect_invalid(module, {**green, "open_issues": "I-1"}, "green with open item")
    expect_invalid(module, {**green, "completed_slices": "S-1"}, "green before every slice")
    expect_invalid(module, {**green, "state_version": "2"}, "legacy state version")
    moved_green = {**green, "head_sha": "1" * 40, "snapshot_id": "sha256:" + "b" * 64}
    expect_error(module, lambda: module.validate_state_change(green, moved_green), "green HEAD reconciliation")
    shipping = {**green, "lifecycle_status": "shipping", "stage_status": "in-progress"}
    moved_shipping = {**shipping, "head_sha": "1" * 40, "snapshot_id": "sha256:" + "b" * 64}
    module.validate_state_change(shipping, moved_shipping)

    cancelled = state(
        module,
        lifecycle_status="cancelled",
        plan_stage="none",
        stage_status="complete",
        waiting_for="none",
    )
    module.validate_values(cancelled)
    module.validate_transition(cancelled)

    shipped = {**green, "lifecycle_status": "shipped", "stage_status": "complete"}
    expect_error(
        module,
        lambda: module.validate_document(
            inventory_path,
            bind_approved(module, plan_text(module, shipped, learning=(candidate,)) + inventory),
        ),
        "shipped with open learning candidate",
    )


def check_checkpoint_contract(module) -> None:
    values = state(module)
    original = plan_text(module, values)
    token = module.checkpoint_token(original)
    prose_edit = original.replace("Fixture.", "Accepted evidence changed.")
    if module.checkpoint_token(prose_edit) != token:
        fail("checkpoint token changes for plan prose")
    duplicate_mapping = original + f"\n## Notes\n\n- next_action = {values['next_action']}\n"
    replaced = module.replace_state(duplicate_mapping, {"next_action": "Continue safely."})
    if module.parse_state(replaced)["next_action"] != "Continue safely.":
        fail("state replacement did not update the State owner")
    if f"## Notes\n\n- next_action = {values['next_action']}" not in replaced:
        fail("state replacement mutated state-shaped non-state prose")

    learning, added_learning, _, _ = module.apply_learning_operations(
        {}, [["false-gate", "build I-1", "Verified: false-pass gate", "required context omission",
              "audit controller", "overflow fixture fails closed"]], []
    )
    if added_learning != ("L-1",) or learning["L-1"][8] != "open":
        fail("learning candidate add contract broken")
    current_snapshot = "sha256:" + "b" * 64
    current_artifact = "sha256:" + "c" * 64
    learning, _, resolved_learning, _ = module.apply_learning_operations(
        learning, [], [["L-1", "PASS: overflow fixture + full gate"]], (), (),
        current_snapshot, current_artifact,
    )
    receipt = learning["L-1"][7]
    if resolved_learning != ("L-1",) or not module.learning_pass_binding(receipt) or learning["L-1"][8] != "closed":
        fail("learning candidate resolution contract broken")
    expect_error(
        module,
        lambda: module.apply_learning_operations(
            {}, [["recurrence", "plan research", "Inferred: repeated waste", "unknown", "state owner", "prove recurrence"]], []
        ),
        "non-verified learning candidate creation",
    )
    expect_error(
        module,
        lambda: module.apply_learning_operations(
            {}, [["one-off", "build I-2", "Verified: local defect", "missing branch", "slice", "test"]], []
        ),
        "one-off learning trigger",
    )
    verified, _, _, _ = module.apply_learning_operations(
        {}, [["systemic-critical-gap", "build I-2", "Verified: systemic gap", "missing guard", "state owner", "contract proof"]], []
    )
    expect_error(
        module,
        lambda: module.apply_learning_operations(verified, [], [["L-1", "done"]]),
        "unstructured learning proof receipt",
    )
    expect_error(
        module,
        lambda: module.apply_learning_operations(
            verified,
            [["systemic-critical-gap", "BUILD I-2", "Verified: same gap", "  missing   guard ", "state owner", "proof"]],
            [],
        ),
        "duplicate learning candidate",
    )
    expect_error(
        module,
        lambda: module.apply_learning_operations(
            verified, [], [["L-1", "TRANSFER: destination/L-1"]]
        ),
        "free-form learning transfer receipt",
    )
    learning_text = plan_text(module, values, learning=tuple(learning.values()))
    module.validate_document(ROOT / "features/fixture/PLAN.md", learning_text)
    if module.checkpoint_token(learning_text) == token:
        fail("checkpoint token ignores learning candidates")
    pruned_items, pruned_learning = module.prune_closed_records(
        {}, learning, current_snapshot, current_artifact
    )
    if pruned_items or pruned_learning:
        fail("closed PLAN chronology was not pruned")
    expect_error(
        module, lambda: module.prune_closed_records({}, verified, current_snapshot, current_artifact),
        "open learning prune",
    )
    expect_error(
        module,
        lambda: module.prune_closed_records({}, learning, "sha256:" + "d" * 64, current_artifact),
        "stale learning prune",
    )
    pending_audit = {"I-1": (
        "I-1", "issue", "audit=A-1; snapshot=sha256:" + "a" * 64
        + "; axis=standards; severity=critical; source=x", "risk", "$he-build",
        "disposition=fixed; proof=contract pass; re-audit=pending", "closed",
    )}
    retained, _ = module.prune_closed_records(pending_audit, {}, current_snapshot, current_artifact)
    if retained != pending_audit:
        fail("pending re-audit evidence was pruned")
    stale_audit = {"I-1": (*pending_audit["I-1"][:5], "disposition=fixed; proof=pass; re-audit=pass@sha256:" + "a" * 64, "closed")}
    retained, _ = module.prune_closed_records(stale_audit, {}, current_snapshot, current_artifact)
    if retained != stale_audit:
        fail("stale re-audit evidence was pruned")
    current_audit = {"I-1": (*stale_audit["I-1"][:5], "disposition=fixed; proof=pass; re-audit=pass@" + current_snapshot, "closed")}
    if module.prune_closed_records(current_audit, {}, current_snapshot, current_artifact)[0]:
        fail("current re-audit evidence was not pruned")
    duplicate_learning = learning_text + "\n## Learning Candidates\n| ID | Trigger | Source | Evidence | Cause | Owner | Required proof | Resolution | Status |\n|---|---|---|---|---|---|---|---|---|\n"
    expect_error(
        module,
        lambda: module.validate_document(ROOT / "features/fixture/PLAN.md", duplicate_learning),
        "duplicate learning candidate table",
    )

    updates = module.parse_state_updates(
        ["next_action=Verify S-1.", "active_slice=S-1", "snapshot_id=" + "sha256:" + "b" * 64]
    )
    if updates != {
        "next_action": "Verify S-1.",
        "active_slice": "S-1",
        "snapshot_id": "sha256:" + "b" * 64,
    }:
        fail("checkpoint state updates parsed incorrectly")
    expect_error(module, lambda: module.parse_state_updates(["head_sha=" + "1" * 40]), "owned identity")
    expect_error(module, lambda: module.parse_state_updates(["open_issues=I-1"]), "derived open items")

    items, added = module.apply_item_operations(
        {},
        [["blocker", "Missing contract", "Build cannot start", "user", "Approve API"]],
        [],
        [],
    )
    if added != ("B-1",) or module.open_item_state(items)["open_blockers"] != "B-1":
        fail("checkpoint add-item contract broken")
    rendered = module.replace_active_items(original, items)
    rendered = module.replace_state(rendered, module.open_item_state(items))
    rendered_state = module.parse_state(rendered)
    module.validate_item_links(rendered_state, module.parse_active_items(rendered))
    if module.checkpoint_token(rendered) == token:
        fail("checkpoint token ignores active-item changes")

    items, _ = module.apply_item_operations(
        items,
        [],
        [["B-1", "next-action", "Confirm final contract"]],
        ["B-1"],
    )
    if items["B-1"][5] != "Confirm final contract" or items["B-1"][6] != "closed":
        fail("checkpoint update/close contract broken")
    if module.open_item_state(items)["open_blockers"] != "none":
        fail("closed item remains in derived open state")

    expect_error(
        module,
        lambda: module.apply_item_operations({}, [["issue", "bad|cell", "impact", "agent", "fix"]], [], []),
        "unsafe table value",
    )
    expect_error(
        module,
        lambda: module.apply_item_operations({}, [], [["I-1", "owner", "agent"]], []),
        "missing item update",
    )


def quietly(action, *args) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        result = action(*args)
    return result, output.getvalue()


def context_fixture(module) -> tuple[str, str]:
    sections = "\n".join(f"## {section}\n- Value = fixture\n" for section in module.PRODUCT_SECTIONS)
    product = f"# Product — Fixture\n\n{sections}"
    reference = DESIGN_REFERENCE_PATH.read_text(encoding="utf-8")
    match = re.search(r"^## Visual Surface = none\s+```md\n(.*?)\n```", reference, re.MULTILINE | re.DOTALL)
    if match is None:
        fail("DESIGN.md no-visual fixture missing")
    design = match.group(1).replace("<product>", "Fixture") + "\n"
    return product, design


def check_context_reference_parity(module) -> None:
    product_reference = PRODUCT_REFERENCE_PATH.read_text(encoding="utf-8")
    product_sections = tuple(re.findall(r"^\| `([^`]+)` \|", product_reference, re.MULTILINE))
    if product_sections != module.PRODUCT_SECTIONS:
        fail("PRODUCT.md reference differs from context_docs.PRODUCT_SECTIONS")

    design_reference = DESIGN_REFERENCE_PATH.read_text(encoding="utf-8")
    match = re.search(r"^- Body order = `([^`]+)`\.$", design_reference, re.MULTILINE)
    if match is None:
        fail("DESIGN.md reference body order missing")
    design_sections = tuple(part.strip() for part in match.group(1).split("→"))
    if design_sections != module.DESIGN_SECTIONS:
        fail("DESIGN.md reference differs from context_docs.DESIGN_SECTIONS")


def check_context_docs_contract(module) -> None:
    check_context_reference_parity(module)
    result, _ = quietly(module.inspect, str(ROOT))
    if result != 0:
        fail("repository root context documents are invalid")

    with tempfile.TemporaryDirectory(prefix="hard-eng-context-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        result, _ = quietly(module.inspect, str(root))
        if result != 4:
            fail("missing root context documents accepted")

        product, design = context_fixture(module)
        (root / "PRODUCT.md").write_text(product, encoding="utf-8")
        (root / "DESIGN.md").write_text(design, encoding="utf-8")
        result, _ = quietly(module.inspect, str(root))
        if result != 0:
            fail("valid root context documents rejected")

        nested = root / "nested"
        nested.mkdir()
        (nested / "PRODUCT.md").write_text(product, encoding="utf-8")
        result, _ = quietly(module.inspect, str(root))
        if result != 4:
            fail("nested PRODUCT.md owner accepted")
        (nested / "PRODUCT.md").unlink()
        nested.rmdir()

        (root / "PRODUCT.md").write_text(product + "\n## Identity\n- Value = duplicate\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(root))
        if result != 4:
            fail("duplicate PRODUCT.md section accepted")


def check_worktree_contract(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-worktree-") as temporary:
        fixture = Path(temporary)
        source = fixture / "source"
        linked = fixture / "linked"
        result, _ = quietly(module.inspect, str(source), "read")
        if result != 4:
            fail("non-Git worktree preflight accepted")
        subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.email", "fixture@example.com"], check=True)
        (source / ".gitignore").write_text(".env\n", encoding="utf-8")
        (source / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        (source / ".env").write_text("fixture=true\n", encoding="utf-8")
        (source / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", ".gitignore", ".worktreeinclude", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "fixture"], check=True)

        result, output = quietly(module.inspect, str(source), "read")
        if result != 0 or not all(
            anchor in output for anchor in ("worktree=primary", "branch=main", "head_sha=", "dirty_count=")
        ):
            fail("primary checkout read preflight rejected")
        result, output = quietly(module.inspect, str(source), "write")
        if result != 0 or "starting_state=clean" not in output:
            fail("clean primary checkout rejected")

        (source / "README.md").write_text("unstaged\n", encoding="utf-8")
        result, output = quietly(module.inspect, str(source), "write")
        if result != 3 or "result=choice-required" not in output: fail("unstaged primary checkout omitted user choice")
        if quietly(module.inspect, str(source), "write", "current")[0] != 0: fail("selected unstaged primary checkout rejected")
        subprocess.run(["git", "-C", str(source), "restore", "README.md"], check=True)

        (source / "README.md").write_text("staged\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", "README.md"], check=True)
        result, output = quietly(module.inspect, str(source), "write")
        if result != 3 or "result=choice-required" not in output: fail("staged primary checkout omitted user choice")
        if quietly(module.inspect, str(source), "write", "current")[0] != 0: fail("selected staged primary checkout rejected")
        subprocess.run(["git", "-C", str(source), "restore", "--staged", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "restore", "README.md"], check=True)

        (source / "untracked.txt").write_text("untracked\n", encoding="utf-8")
        result, output = quietly(module.inspect, str(source), "write")
        if result != 3 or "result=choice-required" not in output: fail("untracked primary checkout omitted user choice")
        if quietly(module.inspect, str(source), "write", "current")[0] != 0: fail("selected untracked primary checkout rejected")
        (source / "untracked.txt").unlink()

        (source / "README.md").write_text("task change\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(source), "publish")
        if result != 0:
            fail("named primary checkout publish rejected after clean write preflight")
        subprocess.run(["git", "-C", str(source), "restore", "README.md"], check=True)

        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "core.hooksPath=/dev/null",
                "worktree",
                "add",
                "-q",
                "--detach",
                str(linked),
            ],
            check=True,
        )
        result, _ = quietly(module.inspect, str(linked), "read")
        if result != 4:
            fail("read preflight with missing included input accepted")
        result, _ = quietly(module.inspect, str(linked), "write")
        if result != 4:
            fail("worktree with missing included input accepted")
        (linked / ".env").write_text("fixture=true\n", encoding="utf-8")
        result, output = quietly(module.inspect, str(linked), "write")
        if result != 0 or "worktree=isolated" not in output or "branch=DETACHED" not in output:
            fail("ready isolated worktree rejected")
        (linked / "README.md").write_text("dirty linked\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(linked), "write")
        if result != 0:
            fail("existing dirty linked worktree rejected")
        subprocess.run(["git", "-C", str(linked), "restore", "README.md"], check=True)
        result, _ = quietly(module.inspect, str(linked), "publish")
        if result != 4:
            fail("detached worktree publish accepted")
        subprocess.run(["git", "-C", str(linked), "switch", "-q", "-c", "review/fixture"], check=True)
        result, _ = quietly(module.inspect, str(linked), "publish")
        if result != 0:
            fail("named non-feature worktree publish rejected")

        (linked / ".worktreeinclude").write_text("*\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(linked), "read")
        if result != 4:
            fail("universal .worktreeinclude pattern accepted")

        (linked / ".worktreeinclude").write_text("**/*.missing.generated\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(linked), "read")
        if result != 4:
            fail("unmatched .worktreeinclude glob accepted")

        (linked / ".worktreeinclude").write_text("README.md\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(linked), "read")
        if result != 4:
            fail("tracked .worktreeinclude entry accepted")

        subprocess.run(
            ["git", "-C", str(linked), "rm", "-q", "--cached", "-f", ".worktreeinclude"],
            check=True,
        )
        (linked / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(linked), "read")
        if result != 4:
            fail("untracked .worktreeinclude accepted")


def check_design_report_contract() -> None:
    script = """const {reportExitCode}=require('./skills/deterministic-checks/scripts/check-design-md.js');
const report=JSON.parse(process.argv[1]);
process.exit(reportExitCode(report));"""
    clean = '{"summary":{"errors":0,"warnings":0}}'
    warning = '{"summary":{"errors":0,"warnings":1}}'
    if subprocess.run(["node", "-e", script, clean], cwd=ROOT).returncode != 0:
        fail("clean DESIGN.md report rejected")
    if subprocess.run(["node", "-e", script, warning], cwd=ROOT).returncode == 0:
        fail("DESIGN.md warning report accepted")


def run_external_contract(command: list[str], label: str) -> tuple[str, subprocess.CompletedProcess[str]]:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    return label, result


def check_external_contracts() -> None:
    contracts = (
        ("he-state integration", [sys.executable, str(STATE_INTEGRATION_CHECK_PATH)]),
        *((f"stage contract: {path.name}", [sys.executable, str(path)]) for path in STAGE_CHECK_PATHS),
        ("global worktree hook fixture", [str(GLOBAL_HOOK_TEST_PATH)]),
        ("worktree policy contract", [sys.executable, str(ROOT / "scripts/worktree-policy-contract-check.py")]),
        ("setup contract", [sys.executable, str(ROOT / "scripts/setup-contract-check.py")]),
        ("bounded command contract", [sys.executable, str(BOUNDED_RUN_CHECK_PATH)]),
    )
    with ThreadPoolExecutor(max_workers=len(contracts)) as pool:
        futures = [pool.submit(run_external_contract, command, label) for label, command in contracts]
        results = [future.result() for future in futures]
    for label, result in results:
        if result.returncode != 0:
            fail(result.stderr.strip() or result.stdout.strip() or f"{label} failed")
        if result.stdout.strip():
            print(result.stdout.strip())
def main() -> int:
    module = load_plan_state()
    context_module = load_context_docs()
    worktree_module = load_worktree()
    check_state_contract(module)
    check_checkpoint_contract(module)
    check_context_docs_contract(context_module)
    check_worktree_contract(worktree_module)
    check_design_report_contract()
    check_admission_wiring_contract(ROOT, fail)
    check_plan_stage_parity(ROOT, module, fail)
    check_route_fixtures(ROOT, fail)
    check_external_contracts()
    print("skill-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
