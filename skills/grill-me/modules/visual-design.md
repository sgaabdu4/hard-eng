# Visual design module

Use after UI flow when mapped `run` or `brief`. During Q&A, update only
`plan_draft.md`; write `03-visual-design.md` only at artifact creation, stage
close, user request, or final synthesis.

## Scope

Choose visual direction before any full-flow UI prototype. Show styled key
screens/flow moments so the user can judge the experience.

Owns:
- Impeccable project context setup
- 2-4 distinct visual directions
- Project-local direction boards or component/state artifacts when visual choice needs to be seen
- Register: brand or product
- Physical scene/theme choice
- Color strategy and OKLCH palette tokens
- Typography, density, spacing rhythm, component feel, and motion tone
- Styled key-screen/flow concept artifacts
- Accessibility notes for text/background contrast
- User choice: pick, merge, custom, or explicit use-default. No full-flow UI prototype without this choice
- Lavish decision loop for UI options only: show 2-4 directions, poll until the
  user chooses, then save selected choice, rejected options, and chosen components

Out of scope:
- Backend/API/auth/storage connection
- Full clickable prototype build
- Final implementation

## Impeccable setup gate

Before directions/artifacts, identify the design/library SSOT: tokens, theme,
primitives, component library, shared CSS, and representative pages. Use
`atomic-ui` for missing or disputed SSOT before inventing reusable styling. Then load
`impeccable/SKILL.md`, run
`load-context.mjs` when available, and consume the output. If `PRODUCT.md` is
missing/empty/placeholder/lacks register, pause and run the substance of
`impeccable teach` one Q at a time; never overwrite silently, then rerun the
loader. If `DESIGN.md` is missing, offer `impeccable document` scan mode for
existing UI/code or seed mode for greenfield; if skipped, continue and record
`DESIGN.md skipped`. Existing PRODUCT/DESIGN answers are anchors; do not re-ask.
Identify register and load `reference/brand.md` or `reference/product.md`.

## Required references

Load relevant impeccable refs:
- Always: `shape`, `spatial-design`, `typography`
- Color/theming: `color-and-contrast`
- Forms/nav/flows/permissions: `interaction-design`
- Motion: `motion-design`
- Responsive: `responsive-design`
- Copy/errors/onboarding: `ux-writing`
- Native image generation: `codex`, then palette/mock gates
- Flutter/Dart: also load `building-flutter-apps`

If a reference is unavailable, state it in the handoff and continue with available evidence.

## Required design behavior

- Pick register, scene, and color strategy before colors
- Use OKLCH semantic tokens, tinted neutrals, and readable contrast
- Name only enough atomic vocabulary to guide reuse
- Show multiple structural approaches, not trivial color swaps
- Reject category-reflex/AI-slop aesthetics
- Product UI: task focus, state coverage, familiar components. Brand UI:
  point of view, named references, imagery when implied.

## Gates

Do not compress these gates:

1. **Context gate** - PRODUCT/DESIGN context loaded, created, or explicitly skipped where allowed.
2. **Direction-input gate** - scene, color strategy, fidelity, breadth, and named references are clear enough.
3. **Palette gate** - palette/tokens are confirmed when native image generation or high-fidelity exploration is used.
4. **Direction-choice gate** - one direction is chosen, merged, customized, accepted as default, or blocked with `Next: ready for /he:implement: no`.
5. **Prototype handoff gate** - chosen direction contract is recorded for the prototype.

No full-flow UI prototype before gate 4, unless the user explicitly says to skip visual design.

## Direction artifact rules

Show 2-4 directions with structural differences: hierarchy/topology, density,
type voice, color strategy, composition, component/material language, or motion.
For each, include name, register fit, scene, color/token notes, type/density,
component feel, accessibility, and what carries into prototype.

Direction artifacts must match the user request, then subject-project
tokens/components/CSS vars, brand assets, or styled pages. If no UI library or
token owner exists, create the smallest project-local token/component owner
first and mark any artifact-only styling as representative.

If native image generation exists:
- Follow `reference/codex.md` Steps A-D
- Ask Step A direction questions first
- Confirm one palette before mocks
- Generate 1-3 high-fidelity north-star mocks against that palette
- Stop for approval before prototype/code

If native image generation does not exist:
- State one line in the handoff: native image generation unavailable
- Produce code-native visual direction boards or styled key-screen concepts instead
- Web/unknown default: static HTML/CSS under `docs/planning/visual-design/<slug>/`
- Flutter default: Flutter-native styled concept under `lib/visual_design/<slug>/` or `lib/main_visual_design.dart`

## Preview rules

- First visual-design turn: create/update concept artifact only if useful; show preview in same reply
- When Lavish is the review surface, update the artifact to the exact current
  Grill Me question before each poll and seed the panel with `--agent-reply`.
  Do not continue polling a stale artifact after moving to the next question.
- For localhost, verify the port (`lsof -iTCP:4173 -sTCP:LISTEN -n -P`),
  use a free port, and serve only the artifact dir. Fetch the exact HTML URL
  before replying; use `/` only for real `index.html`.
- Label `Visual design preview:` only after verification; otherwise label `Run preview:` + exact command + expected URL
- Flutter -> Flutter-native styled concept; verify/free port; run target entry
- Existing code -> reuse real routes, copy, components, and tokens; if they conflict with the direction, name it

## Stage handoff plan

At artifact creation/stage close/final synthesis, `03-visual-design.md` includes
only relevant decisions: setup/register/refs, scene, directions shown,
chosen/merged direction, color/token/type/density/component decisions,
accessibility, artifacts/previews, image-generation status, and prototype
handoff.

Clarity gate:
- Context gate is resolved
- User has selected, merged, customized, or explicitly accepted the default visual direction
- At least one styled key screen/flow moment exists when an artifact is needed
- Palette/type/density/component decisions and initial vocabulary are captured
  enough for a prototype.
- Accessibility constraints are named or the stage is blocked
- Preview points to the actual artifact when shown
- Artifact feedback is applied when used; parked feedback blocks Plan readiness

## Q pattern

Use `modules/questions.md`. Show verified preview/status first when available,
then ask one style choice question. Allow pick, merge, custom, use-default, or
block. Keep setup status, refs, scene, directions, tokens, type/density,
accessibility, artifact path, why, and scenario for `session_state.md`, artifact
notes, stage close, or final synthesis.

## Rules

- Show 2-4 meaningfully different style directions; do not show trivial color swaps
- Each direction must include enough of a real screen/flow moment to judge the experience
- Ask about visual direction, density, hierarchy, tone, and fit; do not ask the user to approve invisible implementation details
- If the user says a direction feels wrong, ask what to preserve/change before generating more variants
- Do not proceed to a full-flow UI prototype until visual direction is chosen, merged, customized, or explicitly accepted as the default
- If the user cannot choose, ask what to preserve/change or generate a tighter second set of directions; do not silently pick
- The next-stage handoff must name the chosen direction and what the prototype must reuse from it
- Do not update `03-visual-design.md` per Q; record answers in `plan_draft.md` and summarize only at artifact creation/stage close/final synthesis
