---
name: he-plan
description: Use for /he:plan; stage 1 readiness with Treehouse, Grill Me, owner, proof path, PASS/FAIL.
---

# he-plan

Stage 1/5. Use for `/he:plan` before implementation. Finish the gate; do not timebox it.

Read `../workflow-help/references/route-map.md`, `../treehouse/SKILL.md`, and `../grill-me/SKILL.md` before acting. Also read existing `PRODUCT.md`, `DESIGN.md`, and the project token/design-system owner when present.

## Contract

- Create/update `he-state.json`; every internal step updates `steps[]`; every concern/failure updates `findings[]`; repeated misses, process gaps, and future guards get learning/process findings; validate it before any ready-yes handoff
- Record every Plan sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before `PASS`
- Before `PASS`, run `check-project-context-gates.mjs --require-all`; ensure `PRODUCT.md`, `DESIGN.md`, and the token/design-system owner exist and are current. If missing, route through Impeccable setup: `/impeccable init` creates PRODUCT.md and `/impeccable document` creates or refreshes DESIGN.md. Product changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner. Put their paths/status in the plan artifact and `he-state.json.context`
- Reduce context rot by treating `he-state.json` as the resume source. Record only current state, receipts, open findings, guardrails, artifacts, and next-stage readiness; do not depend on transcript memory
- Treehouse + `ensure-worktree-ready.sh` gate non-trivial work; skip only small clear work
- Use `grill-me` when outcome, scope, proof, risk, UI flow, or visual direction is unclear; do not duplicate its workflow. Let Grill Me ask unlimited one-question turns until user and AI are aligned with no guesswork, then mirror stage status, full visible Q text, alignment receipt, decisions, blockers, and artifact paths in `he-state.json.planReadiness`
- If Grill Me is marked not required for feature, product, design, UI, or ambiguous work, record explicit user-approved skip evidence in `planReadiness.grillMe`
- For UI work, Grill Me owns the active question/state; Impeccable Live reviews the real app route with the current design system first. Use a current-design-system mock only when the real surface cannot exist yet, and record it as fallback evidence before implementation. Capture UI choices with a saved `ui-review-receipt` from the real or fallback surface: React route/localhost or Storybook for React, Flutter Widget Previewer/Widgetbook/simulator for Flutter, or local HTML fallback when no app surface exists
- Required UI review needs `status: accepted`, `shownToUser: true`, `decisionTool: ui-review-receipt`, `receipt.status: accepted`, a review surface, user response, design-system evidence, shared-component evidence, and alignment with no open decisions or unknowns. `receipt.surfaceKind` is one of `real-route`, `react-localhost`, `storybook`, `flutter-widget-preview`, `widgetbook`, `simulator`, or `local-html`; browser surfaces need localhost `surfaceUrl`, simulator needs `deviceTarget`, and Widgetbook needs localhost `surfaceUrl` or `deviceTarget`
- Choose none, `to-prd`, `to-issues`, or both only after Grill Me/artifact needs are resolved
- Record `learning-capture` as skipped with reason/evidence when Plan found no learning/process finding
- `CONCERNS` is not a shortcut around Grill Me. If a blocker is answerable by the user, ask the next visible Grill Me question in the thread and keep `Next: ready for /he:implement: no`; only use a final blocked receipt when the next action is outside the user interview
- Failure loop: stay in `he-plan` until every required Plan sub-stage, Grill Me stage, UI decision, owner, scope, proof, and risk is aligned or explicitly blocked with `Next: ready for /he:implement: no`; parked questions/artifacts/unknowns cannot `PASS`
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, `Next: ready for /he:implement: yes/no`, and `Handover prompt:` for a fresh session with worktree, `he-state.json`, blockers, artifacts, and the next `/he:implement` command. Only `PASS` can say ready yes; `CONCERNS` and `FAIL` must say ready no. No transcript dump
