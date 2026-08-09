---
name: he-plan
description: Produce and approve one lean living Feature Brief after he selects lifecycle work.
---

# Hard Eng Plan

## Contract

- Input = `he`-selected valid `PLAN.md` with `lifecycle_status=planning`.
- Output = one Ready-to-build brief OR one material decision question.
- Owner = accepted current state in `PLAN.md`; planning history + rejected alternatives stay out.
- Production code/config mutation = forbidden.
- Build readiness/setup/full gates = build-entry concerns, not planning prerequisites; selected checkout `read` PASS → finish the brief + approval while recording exact build-entry debt.
- Planning-time process repair = forbidden unless selected-checkout readability/integrity is unsafe; a failed product `write` gate alone does not block `he-plan`.
- Load [feature-brief.md](references/feature-brief.md) for workflow + template + field meaning.
- Missing/stale root `PRODUCT.md` + product-truth change → load [product-md.md](references/product-md.md).

- No serial planning stages, trace graph, exact path manifest, semantic-completeness prediction, or repeated plan challenge.
- Research + `codebase-design` + `test-quality` = evidence specialists only when the brief needs them.
- Non-`n/a` `ux_reference` → design-forensics evidence first + `atomic-ui` PASS before reference creation/selection.
- Generated/reference media = local lifecycle evidence + show in chat before Ready-to-build approval; product commit requires explicit product-asset acceptance.
- External contract/current vendor fact → `research` PASS before acceptance.
- Desired-state uncertainty → reference workflow `question-me` branch.

## Brief Gate

| Section | Ready evidence |
|---|---|
| Outcome | one observable user/system result |
| Non-goals | explicit boundary |
| Material decisions | accepted constraints + material delivery form/lifetime when applicable + grounded `ux_reference`/sources or n/a + unresolved material choice = none |
| Acceptance examples | concrete Given/When/Then or equivalent examples |
| Affected canonical areas | known owner surfaces; path precision optional |
| Risk and rollback | `risk_level`, scoped `critical_overlay`, recovery route, living `deferred`/`blocked_on` rows |
| First vertical slice | smallest end-to-end behavior + focused proof |

- Unknown implementation owner/file/test = discover during build + update brief if useful; non-`n/a` visual sources excluded.
- Such discoveries never trigger replan/reapproval.
- Decision visible but not yet phrasable → `deferred` row; decision waiting on user action → `blocked_on` row + `he` Continuity rule.
- Neither row delays Ready-to-build unless it changes a frozen constraint.
- New/changed user-visible surface = entry point + placement + layout + modal structure = material UX; accepted proposed-state design recorded in `ux_reference` + displayed in chat before Ready-to-build; unsettled → `question-me`.
- Non-`n/a` reference = root `DESIGN.md` + actual production token/theme/component/layout owners verified through `atomic-ui` → record `ux_reference_sources = DESIGN.md + <repo-relative-owner>...`; contradiction/missing owner → `question-me`.
- Before creating or showing any non-`n/a` proposed-state visual → inspect or reuse a valid design-forensics receipt for the relevant current product screen + affected user flow + verified production owners; genuinely new surface → inspect the nearest existing flow + record the gap; unavailable product/flow → `question-me` + no generic mock.
- Design-forensics pass = route + current screen + affected flow + states + production owners; when delegation is user-authorized, one depth-1 sub-agent performs it read-only, otherwise the main agent performs the same pass; output = evidence only; main agent owns reference creation, UX decision + proof.
- Valid design-forensics receipt = PASS + exact repository revision/source fingerprint + route + current screen/affected flow + states + production owners; unchanged receipt may be reused; changed, stale, or missing receipt → inspect again; conversation memory alone ≠ receipt.
- Existing changed surface → current runtime screenshot = input evidence only; current screenshot alone is never the approval reference.
- Proposed-state design = ImageGen mock OR HTML/CSS wireframe rendered to an image + verified production owners reused; choose the smallest sufficient low-token option; hand-rolled styling invention = forbidden.
- HTML/CSS wireframe + in-app browser available → serve on localhost + open exact preview URL in that browser + keep it live through review + display matching captured image in chat; reuse one server/tab across revisions; browser unavailable → render + chat image only.
- User requests visual change → update same preview + refresh browser + capture/display matching image; superseded visual cannot receive Ready-to-build approval.
- Path-only, `file://`, or unopened localhost HTML = not delivered for design review.
- `validate` emits `ux_reference_markdown` only for a real local image or direct image URL + valid sources → display that exact image in chat before asking for approval.
- New/changed surface → first vertical slice = smallest end-to-end accepted behavior through every required persistence/API/backend/UI owner + actual-media proof; a visual skeleton alone is invalid when the outcome is durable.
- `risk_level=critical` only for payment/auth/security/privacy/destructive-data/irreversibility or a material unresolved safety uncertainty.
- Critical overlay = named risky slice + boundary owner + failure/recovery/rollback + negative proof; it does not expand the whole lifecycle.
- Validator checks shape/state/fingerprint + reference image, provenance paths, and render Markdown.

## Change Route

| Finding | Route |
|---|---|
| owner/file/test/internal approach changes | living brief update → current owner continues |
| accepted outcome/non-goal/material decision/acceptance changes | `he reopen --reason changed-outcome` |
| material security/privacy/data-loss/irreversible contract changes | `he reopen --reason material-safety-contract` |
| implementation contradicts accepted brief | implementation defect → fix + focused proof |

- Reopen only the brief; unchanged accepted constraints need no repeated review.
- Ready-to-build approval freezes outcome/material constraints, not implementation detail.
- Protected actions follow `AGENTS.md`; exact task authorization continues without another approval.

## Completion

- `validate` PASS + no material unknown + user's clear affirmative reply immediately after the complete brief = approve.
- Decision answer to an open question + pre-brief reply = remain planning.
- Approval failure = remain planning + report exact validator issue.
- Approval PASS = commentary checkpoint + same-turn route to `he-build`, unless user requested plan-only.
