#!/usr/bin/env python3
"""Single owner for prose-anchor doc contracts; wording assertions live only here."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ANCHORS: dict[str, tuple[str, ...]] = {
    "AGENTS.md": (
        "| Direct | bounded clear outcome",
        "lean Feature Brief → one Ready-to-build approval",
        "Feature alignment = `question-me` until aligned",
        "arbitrary question limit = none",
        "Approval answers the immediately preceding proposed action only",
        "delivery form/lifetime when it changes observable operation",
        "Terminal PLAN cleanup = prove terminal state + exact path/hash",
        "active/nonterminal PLAN deletion forbidden",
        "Terminal handoff + unrelated request = recommend fresh task",
        "Shared session/preferences/account CLI = sequential",
        "Commentary = material state change + blocker + approval boundary + proof",
        "Critical overlay = slice-scoped; safe slices keep standard flow.",
        "bug + flake + failure + regression",
        "root cause + blast radius",
        "regression proof green",
        "product outcome + UX behavior + default/policy + security/privacy + data loss + irreversible choice",
        "Accepted outcome or material risk contract change",
        "show exact delta → confirm",
        "Replan = accepted outcome change OR material risk contract change",
        "File/owner/caller/schema/key/test/route discovery with unchanged outcome/risk",
        "reapproval forbidden",
        "unchanged outcome/risk continues automatically",
        "Destructive action/external write/commit/push/merge/publish = state target + effect",
        "unchanged steps/retries stay covered; changed target/effect → ask again",
        "Commit/push/merge/publish = separate approval boundary.",
        "Commit changing product truth =",
        "unchanged product truth = no read",
        "Process learning =",
        "block only when continued work risks protected boundary",
        "Subagents = current user prompt explicitly requests",
        "Review = actual diff + affected behavior + risk-targeted proof",
        "Tests/QA/TDD → `test-quality`",
        "real UI proof → `e2e`",
        "Security → `security-review`",
        "Implement ⇄ Verify",
        "Gate scope = affected-full",
        "or uncertainty → full repository",
        "Gate concurrency = independent affected owners parallel",
        "Outcome-first = after readiness/approval",
        "deadline ≠ implementation priority",
        "Gate timing = targeted proof during Implement ⇄ Verify",
        "Publish approval closure",
        "Release actor = one per target + environment + revision",
        "Remote PASS = required CI jobs green for the delivered commit",
    ),
    "README.md": (
        "Fix the typo in the account menu.",
        "# Direct",
        "lean Feature Brief",
        "one Ready-to-build approval",
        "Questions are asked one at a time.",
        "Before each one, the agent researches the available evidence",
        "There is no arbitrary limit on material questions.",
        "Ready-to-build approval rounds before standard build",
        "Material question cadence",
        "A decision answer to an open question or a reply from before the brief",
        "original reported examples at the boundary where users observed them",
        "remove only the exact terminal PLAN paths the user approves",
        "Unrelated work starts a fresh task after a long delivery",
        "Routine tool narration and unchanged polling are omitted",
        "Critical overlay follows risk",
        "for that slice only",
        "Bugs are diagnosed before they are patched.",
        "root cause and blast radius",
        "product outcome or user-visible behavior",
        "security or privacy",
        "data-loss exposure",
        "an irreversible decision",
        "shows the exact delta and asks for confirmation",
        "caller, file, owner, schema, route, test, or configuration",
        "without reopening the brief",
        "destructive actions, external writes, commits, pushes, merges, or publication",
        "explicitly approved",
        "An approval covers the action just proposed",
        "Product delivery continues",
        "unless continuing would risk security, privacy, accessibility, data integrity",
        "actual diff, affected behavior, blast radius, and risk-targeted evidence",
        "Deterministic project gates",
        "browser or device evidence",
        "Implement ⇄ Verify",
    ),
    "PRODUCT.md": (
        "one lean Feature Brief",
        "one Ready-to-build approval",
        "Implement ⇄ Verify",
        "runs affected-full gates",
        "shared behavior = agent-agnostic canonical skills",
        "restating them here forbidden",
    ),
    "DESIGN.md": (
        "risk marker on affected slice only",
        "Implement ⇄ Verify",
        "Ready-to-build",
    ),
    "skills/question-me/SKILL.md": (
        "Before every question = refresh",
        "evidence-settled item → record + never ask",
        "exactly one material user decision per turn",
        "next question branches from accepted answers",
        "Unlimited material questions",
        "Delivery form/lifetime = material only when",
    ),
    "skills/question-me/references/direct.md": (
        "Select next material user decision by dependency + impact",
    ),
    "skills/question-me/references/feature-brief.md": (
        "Select next material `user-decision` by dependency + impact",
    ),
    "skills/he/SKILL.md": (
        "exact user-authorized terminal PLAN file cleanup",
        "lifecycle_status",
        "Ready-to-build",
        "Engineering-only discovery",
        "material security/privacy/data-loss/irreversible contract",
    ),
    "skills/he-plan/SKILL.md": (
        "[feature-brief.md](references/feature-brief.md)",
        "Unknown implementation owner/file/test",
        "Ready-to-build",
        "Outcome",
        "Non-goals",
        "Material decisions",
        "Acceptance examples",
        "Affected canonical areas",
        "Risk and rollback",
        "First vertical slice",
        "every required persistence/API/backend/UI owner",
    ),
    "skills/he-plan/references/feature-brief.md": (
        "ask for approval",
        "clear affirmative",
        "Approval fingerprint = frozen content only.",
        "reference media is shown, never committed",
    ),
    "skills/he-build/SKILL.md": (
        "one active independently demonstrable vertical slice",
        "actual-diff review",
        "affected proof",
        "relevant E2E/security proof",
        "targeted independent review by every applicable protected-boundary owner",
        "Planning reopens only",
        "Candidate patches + path manifests + patch/hash admission + repeated final LLM audits = forbidden",
        "one successful full pre-ship gate",
        "Learning = record verified `he-learn` trigger + continue",
        "slice-gate receipt on the final tree",
        "Implement ⇄ Verify",
        "UI-only skeleton/mock/local state is not a slice",
        "`before commit/push` is a delivery deadline",
        "Gate order = focused behavior proof during the loop",
    ),
    "skills/he-build/references/workflow.md": (
        "reproduce first",
        "canonical owner + every connected caller/schema/key/route/config/test/doc",
        "Review actual diff once",
        "finding-scoped re-review",
        "preserve inspected `completed_slices` exactly",
        "first remaining planned `S-ID`",
        "`building + active_slice=none + completed_slices!=none`",
        "resetting/omitting completed progress = forbidden",
        "one unchanged corrected snapshot with full gate PASS",
        "data-loss/irreversible/schema/recovery",
        "no routine cross-repository source pause",
        "Final Pre-ship Gate",
        "canonical `e2e` receipt PASS",
        "run the slice gate on the final slice tree",
        "slice gate `--full` receipt on the same snapshot",
        "`slice_receipt|full_receipt` debt",
        "required persistence/API/backend/UI = one path",
        "visual acceptance never pauses persistence/API/backend work",
        "keep active behavior on the critical path",
    ),
    "skills/he-build/agents/openai.yaml": (
        "allow_implicit_invocation: true",
    ),
    "skills/he-ship/SKILL.md": (
        "exact green snapshot",
        "exact target + remote + branch + scope approval",
        "Generic workflow/build approval ≠ delivery approval",
        "`deterministic-checks` `publish` PASS",
        "later local lifecycle-state bytes are not part of that artifact",
        "Force push + bypassed hook/check",
        "protected-boundary evidence",
    ),
    "skills/he-ship/references/workflow.md": (
        "git push --dry-run",
        "After commit hooks complete + before dry-run/push",
        "global publish approval closure",
        "active release actors",
        "`github_delivery.py`",
        "affected-full classifier",
        "record run IDs/URLs + results for the delivered commit",
        "Failure after external mutation",
        "CI ⇄ Build",
        "`he-build` root fix",
        "canonical `e2e` receipt validator PASS",
        "do not amend/create/push another commit",
        "--set lifecycle_status=shipped",
        "assert-green --delivered-head",
    ),
    "skills/he-ship/agents/openai.yaml": (
        "allow_implicit_invocation: true",
    ),
    "skills/he-learn/SKILL.md": (
        "protected boundary",
        "execution follows global Subagents contract",
    ),
    "skills/diagnosing-bugs/references/diagnose.md": (
        "Reporter-provided examples = immutable reproduction inventory",
    ),
    "skills/diagnosing-bugs/references/fix.md": (
        "observed public/package/release boundary",
    ),
    "skills/deterministic-checks/SKILL.md": (
        "github_delivery.py",
        "Diagnostic/validation-only workflow path",
        "Nested timeout",
        "Remote CI PASS",
        "[Affected-full gates](references/affected-full.md)",
        "proven non-impacted scope may skip",
        "[Slice gate](references/slice-gate.md)",
    ),
    "skills/deterministic-checks/references/affected-full.md": (
        "Affected-full = universal gates always + full applicable gate row per impacted owner.",
        "global/shared/toolchain/CI/classifier change → full repository",
        "external mutation serial via one release actor",
        "Skip = only scope the classifier proved non-impacted.",
    ),
    "skills/deterministic-checks/references/hooks.md": (
        "`pre-push` = affected-full",
        "CI = same classifier + gate commands",
        "one always-run aggregate",
    ),
    "skills/building-flutter-apps/SKILL.md": (
        "Dart Decimate full JSON scan exits 0 with zero findings",
        "changed/base/baseline/audit modes and inherited exceptions are forbidden",
        "once per affected Git root",
    ),
    "skills/building-flutter-apps/references/dart-decimate.md": (
        "Every project → `npx --yes dart-decimate@latest json <git-root>`",
        "per-package full-repository rescans forbidden",
        "Changed/base/baseline/audit modes + inherited finding exceptions = forbidden",
    ),
}

FORBIDDEN: dict[str, tuple[str, ...]] = {
    "skills/he-build/references/workflow.md": ("--set completed_slices=none",),
    "skills/building-flutter-apps/SKILL.md": (
        "new-only audit",
        "changed-code audit",
    ),
    "skills/building-flutter-apps/references/dart-decimate.md": (
        "dart-decimate@latest audit",
        "--gate new-only",
    ),
}


def main() -> int:
    findings: list[str] = []
    for relative in sorted(set(ANCHORS) | set(FORBIDDEN)):
        path = ROOT / relative
        if not path.is_file():
            findings.append(f"missing owner: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        findings.extend(
            f"{relative}: missing {anchor!r}"
            for anchor in ANCHORS.get(relative, ())
            if anchor not in text
        )
        findings.extend(
            f"{relative}: forbidden {term!r}"
            for term in FORBIDDEN.get(relative, ())
            if term in text
        )
    if findings:
        raise SystemExit("doc-contracts: FAIL | " + " | ".join(findings))
    print(f"doc-contracts: PASS ({len(ANCHORS)} owners)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
