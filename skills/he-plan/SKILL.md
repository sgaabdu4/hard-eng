---
name: he-plan
description: Execute one ordered Hard Eng planning stage from repository evidence through explicit approval. Use only when $he routes a fresh planning state, or when the user explicitly invokes this stage with router-validated state.
---

# Hard Eng Plan

## Contract

- Input = `$he`-selected fresh `PLAN.md` + `plan_stage`.
- Output = current stage approved/skipped, or exact unresolved blocker/issue/unknown.
- Production implementation/data/deploy/publish = forbidden.
- Planning owner = `PLAN.md`; optional split rules live with final [artifacts.md](references/artifacts.md).
- Current accepted state only; rejected/superseded history leaves canonical artifacts.

## Stage Route

Order = `repository → research → feature → flows → ux → contracts → technical → testing → rollout → slices → consistency → approval`.

| `plan_stage` | Load | Stage result |
|---|---|---|
| `repository` | [repository.md](references/repository.md) + `$research` | repository + revision + feature identity proven |
| `research` | [research.md](references/research.md) + `$research` | declared current-state scope proven or blocked |
| `feature` | [feature.md](references/feature.md) | problem + outcomes + scope accepted |
| `flows` | [flows.md](references/flows.md) | actors + state/failure paths accepted |
| `ux` | [ui.md](references/ui.md) | skip approved, or UX/prototype accepted |
| `contracts` | [contracts.md](references/contracts.md) | skip approved, or interfaces/data accepted |
| `technical` | [technical.md](references/technical.md) | owners + approach + cross-cutting design accepted |
| `testing` | [testing.md](references/testing.md) | requirement-to-proof coverage accepted |
| `rollout` | [operations.md](references/operations.md) | release/observe/recover plan accepted |
| `slices` | [slices.md](references/slices.md) | vertical delivery order accepted |
| `consistency` | [consistency.md](references/consistency.md) | traceability gaps = zero |
| `approval` | [artifacts.md](references/artifacts.md) | canonical plan explicitly approved |

- Load current row only; stack/domain skills = evidence owners, never stage/lifecycle owners.
- Prior stage not approved/skipped → stop; report first missing stage; never jump.
- Repository/research uncertainty → `$research`; desired-state uncertainty → `$question-me`.

## Gate

| Result | Action |
|---|---|
| User decision/review needed | Invoke `$question-me` Planning Stage; consume its authoritative review + verbatim response. |
| Material correction | Show delta → confirm → replace accepted state → invalidate earliest affected stage + downstream stages. |
| Unambiguous approval + no material gap | Record approval → advance exactly one stage. |
| Skip proposed | Require irrelevance evidence + risk + mitigation + explicit approval → record skip → advance; `consistency` + `approval` cannot skip. |
| Neither approved nor skipped | Persist exact blocker/issue/unknown + next action → remain at current stage. |
| Before question/handoff/turn end | Invoke `$he` checkpoint contract. |
| Final approval | Apply [artifacts.md](references/artifacts.md) completion → ask whether `PLAN.md` fully represents intended implementation → explicit yes transitions to `build-ready`; stop. |
