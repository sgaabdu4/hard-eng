---
name: he-plan
description: Use for /he:plan; stage 1 readiness with Treehouse, Grill Me, owner, proof path, PASS/FAIL.
---

# he-plan

Stage 1/5. Use for `/he:plan` before implementation. Finish the gate; do not timebox it.

Read `../workflow-help/references/route-map.md`, `../treehouse/SKILL.md`, and `../grill-me/SKILL.md` before acting. Also read existing `PRODUCT.md`, `DESIGN.md`, and the project token/design-system owner when present.

## Contract

- Create/update `he-state.json`; every internal step updates `steps[]`; every concern/failure updates `findings[]`; validate it before any ready-yes handoff
- Record every Plan sub-stage in `subStages[]`; each must be done or skipped with reason/evidence before `PASS`
- Before `PASS`, run `check-project-context-gates.mjs --require-all`; ensure `PRODUCT.md`, `DESIGN.md`, and the token/design-system owner exist and are current. If missing, route through Impeccable setup: `/impeccable init` creates PRODUCT.md and `/impeccable document` creates or refreshes DESIGN.md. Product changes update `PRODUCT.md`; design/UI/token changes update `DESIGN.md` and the token owner. Put their paths/status in the plan artifact and `he-state.json.context`
- Reduce context rot by treating `he-state.json` as the resume source. Record only current state, receipts, open findings, guardrails, artifacts, and next-stage readiness; do not depend on transcript memory
- Treehouse + `ensure-worktree-ready.sh` gate non-trivial work; skip only small clear work
- Use `grill-me` when outcome, scope, proof, risk, UI flow, or visual direction is unclear; do not duplicate its workflow. Let Grill Me ask unlimited one-question turns until user and AI are aligned with no guesswork, then mirror stage status, full visible Q text, alignment receipt, decisions, blockers, and artifact paths in `he-state.json.planReadiness`
- For UI work, Grill Me owns the active question/state; Impeccable Live reviews the real app route with the current design system first. If the real route cannot exist yet, create or review a current-design-system fallback mock before implementation and record it as fallback evidence. Lavish is decision capture only. When both are active, use separate browser surfaces and receipts: Impeccable Live URL for review, Lavish URL/poll for capture. Use Lavish only through `npx -y lavish-axi poll`; direct Live buttons are not Lavish receipts unless `window.lavish` capture actually ran
- Choose none, `to-prd`, `to-issues`, or both only after Grill Me/artifact needs are resolved
- Failure loop: stay in `he-plan` until every required Plan sub-stage, Grill Me stage, UI decision, owner, scope, proof, and risk is aligned or explicitly blocked with `Next: ready for /he:implement: no`; parked questions/artifacts/unknowns cannot `PASS`
- Exit with the stage receipt: state path, decision, owner/proof, artifacts, blocker, `Next: ready for /he:implement: yes/no`, and `Handover prompt:` for a fresh session with worktree, `he-state.json`, blockers, artifacts, and the next `/he:implement` command. Only `PASS` can say ready yes; `CONCERNS` and `FAIL` must say ready no. No transcript dump
