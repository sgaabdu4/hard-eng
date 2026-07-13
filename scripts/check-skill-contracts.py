#!/usr/bin/env python3
"""Check Hard Eng state/doc parity and representative skill routes."""

from __future__ import annotations

import importlib.util
import io
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PLAN_STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
CONTEXT_DOCS_PATH = ROOT / "skills/deterministic-checks/scripts/context-docs.py"
WORKTREE_PATH = ROOT / "skills/deterministic-checks/scripts/worktree.py"
DESIGN_CHECK_PATH = ROOT / "skills/deterministic-checks/scripts/check-design-md.js"
PRODUCT_REFERENCE_PATH = ROOT / "skills/he-plan/references/product.md"
DESIGN_REFERENCE_PATH = ROOT / "skills/atomic-ui/references/design-md.md"


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
        "state_version": "2",
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
        "open_blockers": "none",
        "open_issues": "none",
        "open_unknowns": "none",
    }
    values.update(changes)
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


def plan_text(module, values: dict[str, str], rows: tuple[tuple[str, ...], ...] = ()) -> str:
    state_lines = "\n".join(f"- {key} = {values[key]}" for key in module.REQUIRED)
    item_lines = "\n".join("| " + " | ".join(row) + " |" for row in rows)
    return f"""# fixture

## State
{state_lines}

## Active items
| ID | Type | Evidence | Impact | Owner | Next proof/action | Status |
|---|---|---|---|---|---|---|
{item_lines}

## Accepted plan
Fixture.
"""


def check_state_contract(module) -> None:
    expected_targets = {
        "planning": "$he-plan",
        "build-ready": "$he-build",
        "building": "$he-build",
        "green": "$he-ship",
        "shipping": "$he-ship",
        "learning": "$he-learn",
        "shipped": "none",
        "cancelled": "none",
    }
    if module.ROUTE_TARGETS != expected_targets or set(module.LIFECYCLE) != set(expected_targets):
        fail("lifecycle route targets are incomplete or changed")

    for index, stage in enumerate(module.PLAN_STAGES):
        prefix = module.PLAN_STAGES[:index]
        values = state(
            module,
            plan_stage=stage,
            approved_plan_stages=",".join(prefix) or "none",
        )
        module.validate_values(values)
        module.validate_transition(values)

    invalid_prefix = state(
        module,
        plan_stage="feature",
        approved_plan_stages="repository",
    )
    expect_invalid(module, invalid_prefix, "planning prefix gap")

    complete = ",".join(module.PLAN_STAGES)
    ready = state(
        module,
        lifecycle_status="build-ready",
        current_stage="build",
        plan_stage="none",
        approved_plan_stages=complete,
        stage_status="pending",
        plan_approved="yes",
    )
    module.validate_values(ready)
    module.validate_transition(ready)
    expect_invalid(module, {**ready, "open_issues": "I-1"}, "build-ready open item")

    cancelled = state(
        module,
        lifecycle_status="cancelled",
        plan_stage="none",
        stage_status="complete",
        waiting_for="none",
    )
    module.validate_values(cancelled)
    module.validate_transition(cancelled)


def check_checkpoint_contract(module) -> None:
    values = state(module)
    original = plan_text(module, values)
    token = module.checkpoint_token(original)
    prose_edit = original.replace("Fixture.", "Accepted evidence changed.")
    if module.checkpoint_token(prose_edit) != token:
        fail("checkpoint token changes for plan prose")

    updates = module.parse_state_updates(["next_action=Ask for approval.", "waiting_for=user"])
    if updates != {"next_action": "Ask for approval.", "waiting_for": "user"}:
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


def check_checkpoint_integration(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-checkpoint-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        result, _ = quietly(module.initialize, str(root), "fixture", None)
        if result != 0:
            fail("checkpoint fixture initialization failed")
        path = root / "features/fixture/PLAN.md"
        original = path.read_text(encoding="utf-8")
        result, inspect_output = quietly(module.inspect, str(root), str(path))
        token = module.checkpoint_token(original)
        if result != 0 or f"checkpoint_token={token}" not in inspect_output:
            fail("inspect did not emit checkpoint token")

        result, output = quietly(
            module.checkpoint,
            str(root),
            str(path),
            token,
            ["next_action=Resolve issue."],
            [["issue", "Missing proof", "Approval blocked", "agent", "Gather evidence"]],
            [],
            [],
        )
        if result != 0 or "added_items=I-1" not in output:
            fail("atomic checkpoint add failed")
        added_text = path.read_text(encoding="utf-8")
        added_state = module.validate_document(path, added_text)
        if added_state["open_issues"] != "I-1":
            fail("atomic checkpoint did not derive open issue")

        result, _ = quietly(module.checkpoint, str(root), str(path), token, [], [], [], ["I-1"])
        if result != 4 or path.read_text(encoding="utf-8") != added_text:
            fail("stale checkpoint changed PLAN.md")

        current_token = module.checkpoint_token(added_text)
        result, _ = quietly(module.checkpoint, str(root), str(path), current_token, [], [], [], ["I-1"])
        if result != 0:
            fail("atomic checkpoint close failed")
        closed_text = path.read_text(encoding="utf-8")
        closed_state = module.validate_document(path, closed_text)
        if closed_state["open_issues"] != "none" or module.parse_active_items(closed_text)["I-1"][6] != "closed":
            fail("atomic checkpoint close did not reconcile row/state")

        current_token = module.checkpoint_token(closed_text)
        result, _ = quietly(
            module.checkpoint,
            str(root),
            str(path),
            current_token,
            ["lifecycle_status=build-ready"],
            [],
            [],
            [],
        )
        if result != 4 or path.read_text(encoding="utf-8") != closed_text:
            fail("invalid transition changed PLAN.md")


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
        result, _ = quietly(module.inspect, str(source), "write")
        if result != 4:
            fail("primary checkout mutation accepted")

        subprocess.run(["git", "-C", str(source), "worktree", "add", "-q", "--detach", str(linked)], check=True)
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
        result, _ = quietly(module.inspect, str(linked), "publish")
        if result != 4:
            fail("detached worktree publish accepted")
        subprocess.run(["git", "-C", str(linked), "switch", "-q", "-c", "feature/fixture"], check=True)
        result, _ = quietly(module.inspect, str(linked), "publish")
        if result != 0:
            fail("named isolated worktree publish rejected")

        (linked / ".worktreeinclude").write_text("*\n", encoding="utf-8")
        result, _ = quietly(module.inspect, str(linked), "read")
        if result != 4:
            fail("universal .worktreeinclude pattern accepted")

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


def check_plan_stage_parity(module) -> None:
    text = (ROOT / "skills/he-plan/SKILL.md").read_text(encoding="utf-8")
    if "$he-validated" in text or "validated by $he" not in text:
        fail("he-plan description does not identify $he as validator")

    order_match = re.search(r"^Order = `([^`]+)`\.$", text, re.MULTILINE)
    if order_match is None:
        fail("he-plan order declaration missing")
    declared_order = tuple(part.strip() for part in order_match.group(1).split("→"))
    table_order = tuple(
        match.group(1)
        for match in re.finditer(r"^\| `([a-z][a-z-]+)` \|", text, re.MULTILINE)
    )
    if declared_order != module.PLAN_STAGES:
        fail("he-plan order differs from plan_state.PLAN_STAGES")
    if table_order != module.PLAN_STAGES:
        fail("he-plan stage table differs from plan_state.PLAN_STAGES")

    he_text = (ROOT / "skills/he/SKILL.md").read_text(encoding="utf-8")
    pointer = "Transition legality + lifecycle/plan-stage/item invariants + `route_target` = `plan_state.py`"
    if pointer not in he_text:
        fail("he does not point state invariants to plan_state.py")
    if "Use script-emitted `route_target`" not in he_text:
        fail("he does not consume script-owned lifecycle routing")
    for checkpoint_anchor in ("--expect-token", "--add-item", "--update-item", "--close-item"):
        if checkpoint_anchor not in he_text:
            fail(f"he checkpoint contract missing: {checkpoint_anchor}")
    if (
        "$deterministic-checks" not in he_text
        or "PRODUCT.md" not in he_text
        or "DESIGN.md" not in he_text
        or "worktree-readiness" not in he_text
    ):
        fail("he repository-context gate missing")

    product_reference = PRODUCT_REFERENCE_PATH
    design_reference = DESIGN_REFERENCE_PATH
    if "references/product.md" not in text or not product_reference.is_file():
        fail("he-plan product-context owner missing")
    atomic_text = (ROOT / "skills/atomic-ui/SKILL.md").read_text(encoding="utf-8")
    if "references/design-md.md" not in atomic_text or not design_reference.is_file():
        fail("atomic-ui DESIGN.md owner missing")

    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    context_route = "- Repository context = root `PRODUCT.md` + `DESIGN.md`; missing/invalid → `$he` repository gate before lifecycle advance."
    if context_route not in agents_text:
        fail("AGENTS repository-context route missing")
    owners_match = re.search(r"^- Stage owners = (.+)$", agents_text, re.MULTILINE)
    if owners_match is None:
        fail("AGENTS stage-owner route missing")
    declared_targets = tuple(
        dict.fromkeys(re.findall(r"\$(he(?:-[a-z]+)?)", owners_match.group(1)))
    )
    expected_targets = tuple(dict.fromkeys(module.ROUTE_TARGETS.values()))
    expected_targets = tuple(target.removeprefix("$") for target in expected_targets if target != "none")
    if declared_targets != expected_targets:
        fail("AGENTS stage owners differ from plan_state.ROUTE_TARGETS")

    deterministic_text = (ROOT / "skills/deterministic-checks/SKILL.md").read_text(encoding="utf-8")
    context_reference = ROOT / "skills/deterministic-checks/references/context-docs.md"
    worktree_reference = ROOT / "skills/deterministic-checks/references/worktree.md"
    if "references/context-docs.md" not in deterministic_text or not context_reference.is_file():
        fail("deterministic repository-context gate missing")
    if "references/worktree.md" not in deterministic_text or not worktree_reference.is_file():
        fail("deterministic worktree-readiness gate missing")
    if not WORKTREE_PATH.is_file():
        fail("worktree preflight script missing")
    if not DESIGN_CHECK_PATH.is_file():
        fail("DESIGN.md warning gate missing")
    override = (ROOT / "AGENTS.override.md").read_text(encoding="utf-8")
    for gate in (
        "skills/deterministic-checks/scripts/worktree.py --repo . --intent publish",
        "scripts/check-skill-contracts.py",
        "skills/deterministic-checks/scripts/check-design-md.js",
        "scripts/check-managed-skills.js",
    ):
        if gate not in override:
            fail(f"pre-push gate missing: {gate}")


ROUTE_FIXTURES = (
    {
        "skill": "codebase-design",
        "prompt": "Review this pass-through wrapper, module boundary, and ownership.",
        "anchors": ("module", "ownership", "wrapper"),
        "resources": ("references/workflow.md", "references/alternatives.md"),
    },
    {
        "skill": "atomic-ui",
        "prompt": "Create DESIGN.md and reconcile UI tokens with component ownership.",
        "anchors": ("design.md", "ui", "tokens", "component"),
        "resources": ("references/design-md.md", "references/system.md"),
    },
    {
        "skill": "deterministic-checks",
        "prompt": "Run deterministic repository gates for PRODUCT.md and DESIGN.md.",
        "anchors": ("deterministic", "gates"),
        "resources": ("references/context-docs.md",),
    },
    {
        "skill": "deterministic-checks",
        "prompt": "Check worktree readiness before changing or publishing code.",
        "anchors": ("worktree", "readiness"),
        "resources": ("references/worktree.md",),
    },
    {
        "skill": "security-review",
        "prompt": "Review this dependency and LLM tool path for exploitable security risk.",
        "anchors": ("dependency", "llm", "security"),
        "resources": ("references/broad.md", "references/dependencies.md"),
    },
)


def check_route_fixtures() -> None:
    for fixture in ROUTE_FIXTURES:
        skill = fixture["skill"]
        directory = ROOT / "skills" / skill
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1].lower()
        prompt = fixture["prompt"].lower()
        uncovered = [anchor for anchor in fixture["anchors"] if anchor not in prompt]
        if uncovered:
            fail(f"{skill} route fixture lacks prompt anchors: {','.join(uncovered)}")
        missing = [anchor for anchor in fixture["anchors"] if anchor not in frontmatter]
        if missing:
            fail(f"{skill} prompt route lacks description anchors: {','.join(missing)}")
        for resource in fixture["resources"]:
            if resource not in text or not (directory / resource).is_file():
                fail(f"{skill} route resource missing: {resource}")
        print(f"route-proof: {skill} -> PASS | {fixture['prompt']}")


def main() -> int:
    module = load_plan_state()
    context_module = load_context_docs()
    worktree_module = load_worktree()
    check_state_contract(module)
    check_checkpoint_contract(module)
    check_checkpoint_integration(module)
    check_context_docs_contract(context_module)
    check_worktree_contract(worktree_module)
    check_design_report_contract()
    check_plan_stage_parity(module)
    check_route_fixtures()
    print("skill-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
