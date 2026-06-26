# Prototype module

Use after prototype tech stack decision when mapped `run` or `brief`. During Q&A, update only `plan_draft.md`; write `05-prototype.md` only at artifact creation, stage close, user request, or final synthesis.

## Scope

Build/plan a full-flow clickable/local prototype with mock data before backend/API/auth/storage connections.

Owns:
- Prototype artifact paths
- Mock data files
- Minimal token/component system for the prototype
- Covered flow states
- Preview URL/device + verification
- User approval status

Out of scope:
- Choosing prototype tech stack; use `04-prototype-tech.md`
- Real backend/auth/storage/realtime/payments/analytics/external APIs
- Backend/infra tech stack

## Rules

- Start after visual design alignment + prototype tech stack gate accepted/brief, or after the user explicitly says to skip visual design
- The prototype must use the chosen visual direction through semantic tokens, type direction, density, component feel, and motion tone
- UI prototypes are token-first and atomic by default: tokens -> atoms -> molecules -> organisms/templates -> pages
- Reuse primitives/composites across states; no one-off UI clones unless explicitly marked disposable
- Keep atomic design lean: create only tokens/components used by the current flow and required states; do not write a full design-system doc unless requested or needed
- Web/static prototypes use CSS custom properties + reusable classes/components; Flutter prototypes use theme/token constants or `ThemeExtension` + reusable widgets
- If no visual direction is chosen for a UI prototype, stop and return to `modules/visual-design.md`
- Cover primary journey + empty/loading/error/permission/offline or failure states
- Use local fixtures/mock services only
- Do not connect real backend, auth, storage, realtime, payments, analytics, or external APIs
- Web/unknown -> `docs/planning/prototypes/<slug>/`; use visual-design preview safety rules; show `Prototype preview:` only after verified
- Flutter -> `lib/prototypes/<slug>/` or `lib/main_prototype.dart`; use mock repos/providers/data; no live SDK init; verify/free port first
- Mock data must be obvious/editable. Persist fixture path + covered states in handoff
- Implementation/backend work starts only after user approves prototype flow

## Stage handoff plan

At artifact creation/stage close/final synthesis, `05-prototype.md` includes only relevant decisions:
- Inputs from `03-visual-design.md` and `04-prototype-tech.md`
- Chosen visual direction reused in the prototype
- Mock boundary used
- Mock data paths
- Token/component map: semantic tokens, atoms, molecules, organisms/templates, pages
- Covered flow states
- Prototype artifact paths
- Preview URL/device + verification status
- User approval/blocker status
- Next-stage handoff for backend/infra tech only when useful

Clarity gate:
- Visual design + prototype tech stack handoffs consumed, unless user explicitly skipped visual design
- Chosen visual direction is visible in the full-flow prototype
- Minimal semantic tokens + atomic component layers exist and are reused, or UI prototype is explicitly n/a
- Mock data covers primary journey + required non-happy states
- Preview/device verified when artifact exists
- No live backend/auth/storage/API calls
- User approves flow before backend/infra work starts

## Q pattern

Use `modules/questions.md`. Show verified preview/status first when available,
then ask one flow/state behavior decision. Keep artifact, stack, mock data,
token/component map, evidence, why, and scenarios for `session_state.md`,
artifact notes, stage close, or final synthesis.

## Notes

- If visual direction is missing or weak, go back to `modules/visual-design.md` first
- If stack or mock boundary must change, go back to `modules/prototype-tech.md` and update `04-prototype-tech.md` first
- Do not update `05-prototype.md` per question; record answers in `plan_draft.md` and summarize here only at artifact creation/stage close/final synthesis
