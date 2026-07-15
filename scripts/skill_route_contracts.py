#!/usr/bin/env python3
"""Focused lifecycle-skill routing contracts."""

from __future__ import annotations

import re
from pathlib import Path


ROUTE_FIXTURES = (
    ("codebase-design", "Review this pass-through wrapper, module boundary, and ownership.",
     ("module", "ownership", "wrapper"), ("references/workflow.md", "references/alternatives.md")),
    ("atomic-ui", "Create DESIGN.md and reconcile UI tokens with component ownership.",
     ("design.md", "ui", "tokens", "component"), ("references/design-md.md", "references/system.md")),
    ("deterministic-checks", "Run deterministic repository gates for PRODUCT.md and DESIGN.md.",
     ("deterministic", "gates"), ("references/context-docs.md",)),
    ("deterministic-checks", "Check worktree readiness before changing or publishing code.",
     ("worktree", "readiness"), ("references/worktree.md",)),
    ("security-review", "Review this dependency and LLM tool path for exploitable security risk.",
     ("dependency", "llm", "security"), ("references/broad.md", "references/dependencies.md")),
)


def check_plan_stage_parity(root: Path, module, fail) -> None:
    text = (root / "skills/he-plan/SKILL.md").read_text(encoding="utf-8")
    if "$he-validated" in text or "validated by $he" not in text:
        fail("he-plan description does not identify $he as validator")
    order_match = re.search(r"^Order = `([^`]+)`\.$", text, re.MULTILINE)
    if order_match is None:
        fail("he-plan order declaration missing")
    declared_order = tuple(part.strip() for part in order_match.group(1).split("→"))
    table_order = tuple(match.group(1) for match in re.finditer(r"^\| `([a-z][a-z-]+)` \|", text, re.MULTILINE))
    if declared_order != module.PLAN_STAGES or table_order != module.PLAN_STAGES:
        fail("he-plan stages differ from plan_state.PLAN_STAGES")
    if "$he-learn" not in text or "keep `plan_stage` unchanged" not in text:
        fail("he-plan learning boundary does not preserve planning state")

    he_text = (root / "skills/he/SKILL.md").read_text(encoding="utf-8")
    pointer = "Transition legality + lifecycle/plan-stage/item invariants + `route_target` = `plan_state.py`"
    if pointer not in he_text or "Use script-emitted `route_target`" not in he_text:
        fail("he router does not consume plan_state ownership")
    for anchor in ("--expect-token", "--add-item", "--update-item", "--close-item", "--prune-closed"):
        if anchor not in he_text:
            fail(f"he checkpoint contract missing: {anchor}")
    for anchor in ("--add-learning", "--resolve-learning", "--transfer-learning", "lifecycle unchanged", "$he-learn"):
        if anchor not in he_text:
            fail(f"he learning overlay missing: {anchor}")

    learn = root / "skills/he-learn"
    learn_text = (learn / "SKILL.md").read_text(encoding="utf-8")
    learn_workflow = (learn / "references/workflow.md").read_text(encoding="utf-8")
    learn_metadata = (learn / "agents/openai.yaml").read_text(encoding="utf-8")
    for anchor in ("evidence-backed", "overlay", "$repeated-failure-learning", "open candidate blocks"):
        if anchor not in learn_text:
            fail(f"he-learn contract missing: {anchor}")
    for anchor in ("root invariant/type/schema/code", "scanner/lint/hook/CI", "return `$he-build`", "zero open candidate"):
        if anchor not in learn_workflow:
            fail(f"he-learn workflow missing: {anchor}")
    if "allow_implicit_invocation: true" not in learn_metadata:
        fail("he-learn must be exposed for router delegation")
    if "exposed metadata ≠ unsolicited classification" not in learn_text:
        fail("he-learn exposure lacks verified-route boundary")

    recurrence = (root / "skills/repeated-failure-learning/SKILL.md").read_text(encoding="utf-8")
    recurrence_meta = (root / "skills/repeated-failure-learning/agents/openai.yaml").read_text(encoding="utf-8")
    if "root-cause evidence only" not in recurrence or "prevention selection = `$he-learn`" not in recurrence:
        fail("recurrence/prevention ownership overlaps")
    if "narrowest durable prevention" in recurrence + recurrence_meta:
        fail("recurrence skill still claims prevention promotion")
    if not all(anchor in he_text for anchor in ("$deterministic-checks", "PRODUCT.md", "DESIGN.md", "worktree-readiness")):
        fail("he repository-context gate missing")

    if "references/product.md" not in text or not (root / "skills/he-plan/references/product.md").is_file():
        fail("he-plan product-context owner missing")
    atomic_text = (root / "skills/atomic-ui/SKILL.md").read_text(encoding="utf-8")
    if "references/design-md.md" not in atomic_text or not (root / "skills/atomic-ui/references/design-md.md").is_file():
        fail("atomic-ui DESIGN.md owner missing")

    agents_text = (root / "AGENTS.md").read_text(encoding="utf-8")
    for anchor in ("Default = direct", "Direct examples = UI height/spacing/color/copy",
                   "Route scope = current request only",
                   "unrelated/terminal goal/PLAN/state ≠ routing input",
                   "missing/invalid `PRODUCT.md` or `DESIGN.md` alone ≠ escalation/blocker",
                   "Direct autonomy = clear outcome + no material unknown",
                   "After `$he` selection only", "Explicit lifecycle persistence → `$he` Continuity goal contract",
                   "Lifecycle continuity = `PASS`",
                   "Finding + accepted outcome + no new material decision",
                   "PLAN reopen = changed user decision",
                   "Cross-repository prevention = source pause + bounded destination repair",
                   "final answer/`continue?` = forbidden"):
        if anchor not in agents_text:
            fail(f"AGENTS direct-first route missing: {anchor}")
    if "Make the existing dashboard cards equal height" not in (root / "README.md").read_text(encoding="utf-8"):
        fail("README small-UI direct route fixture missing")
    for skill in ("he-plan", "he-build", "he-ship", "he-learn", "question-me"):
        metadata = (root / "skills" / skill / "agents/openai.yaml").read_text(encoding="utf-8")
        if "allow_implicit_invocation: true" not in metadata:
            fail(f"router child is not exposed: {skill}")
    if "Stage PASS = commentary + checkpoint + same-turn continuation" not in text:
        fail("he-plan PASS auto-continuation missing")
    for anchor in ("Stage name/transition ≠ approval boundary",
                   "generic `continue`/`yes` request = forbidden",
                   "generic downstream reapproval = forbidden",
                   "Finding + accepted outcome unchanged",
                   "Skip proven + no material decision",
                   "final full-PLAN approval remains mandatory"):
        if anchor not in text:
            fail(f"he-plan decision boundary missing: {anchor}")
    if "User correction → pause" in agents_text or "Goal/plan/state mismatch → pause" in agents_text:
        fail("AGENTS contains unscoped correction/state pause")
    if "Intermediate PASS = commentary only" not in he_text:
        fail("he router allows PASS turn boundaries")
    for anchor in ("create/maintain one Codex goal", "Incomplete slice/work", "auto-continue"):
        if anchor not in he_text:
            fail(f"he persistence continuity missing: {anchor}")
    for anchor in ("bounded known repair → destination direct",
                   "Source lifecycle = paused, never nested"):
        if anchor not in learn_text:
            fail(f"he-learn cross-scope boundary missing: {anchor}")
    owners_match = re.search(r"^- Stage owners = (.+)$", agents_text, re.MULTILINE)
    if owners_match is None:
        fail("AGENTS stage-owner route missing")
    declared = tuple(dict.fromkeys(re.findall(r"\$(he(?:-[a-z]+)?)", owners_match.group(1))))
    expected = tuple(target.removeprefix("$") for target in dict.fromkeys(module.ROUTE_TARGETS.values()) if target != "none")
    if declared != expected:
        fail("AGENTS stage owners differ from plan_state.ROUTE_TARGETS")

    deterministic = (root / "skills/deterministic-checks/SKILL.md").read_text(encoding="utf-8")
    for reference in ("references/context-docs.md", "references/worktree.md"):
        if reference not in deterministic or not (root / "skills/deterministic-checks" / reference).is_file():
            fail(f"deterministic gate missing: {reference}")
    for path, label in ((root / "skills/deterministic-checks/scripts/worktree.py", "worktree preflight"),
                        (root / "skills/deterministic-checks/scripts/check-design-md.js", "DESIGN warning")):
        if not path.is_file():
            fail(f"{label} script missing")
    override = (root / "AGENTS.override.md").read_text(encoding="utf-8")
    for gate in ("skills/deterministic-checks/scripts/worktree.py --repo . --intent publish",
                 "scripts/check-skill-contracts.py", "skills/deterministic-checks/scripts/check-design-md.js",
                 "scripts/check-managed-skills.js"):
        if gate not in override:
            fail(f"pre-push gate missing: {gate}")


def check_route_fixtures(root: Path, fail) -> None:
    for skill, prompt_text, anchors, resources in ROUTE_FIXTURES:
        directory = root / "skills" / skill
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        frontmatter, prompt = text.split("---", 2)[1].lower(), prompt_text.lower()
        if uncovered := [anchor for anchor in anchors if anchor not in prompt]:
            fail(f"{skill} route fixture lacks prompt anchors: {','.join(uncovered)}")
        if missing := [anchor for anchor in anchors if anchor not in frontmatter]:
            fail(f"{skill} prompt route lacks description anchors: {','.join(missing)}")
        for resource in resources:
            if resource not in text or not (directory / resource).is_file():
                fail(f"{skill} route resource missing: {resource}")
        print(f"route-proof: {skill} -> PASS | {prompt_text}")
