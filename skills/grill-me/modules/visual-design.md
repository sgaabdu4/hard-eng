# Visual design module

Use after UI flow when mapped `run` or `brief`. During Q&A, update only
`plan_draft.md`; write `03-visual-design.md` only at artifact creation, stage
close, user request, or final synthesis.

## Scope

Choose visual direction before full-flow UI prototype. Show styled key screens
so the user can judge the experience.

Owns: Impeccable context; 2-4 distinct directions; Project-local direction boards or component/state artifacts when choice must be seen; register, scene,
OKLCH tokens, type/density, component feel, motion, contrast notes, user choice,
and saved UI review receipts. No full-flow UI prototype before
pick/merge/custom/use-default.

Out of scope:
- Backend/API/auth/storage connection
- Full clickable prototype build
- Final implementation

## Impeccable setup gate

Before directions/artifacts, identify tokens, theme, primitives, components,
shared CSS, and representative pages. Use `atomic-ui` for missing/disputed SSOT.
Then load `impeccable/SKILL.md` and follow its setup gate exactly:
`context.mjs` first, then the matching register reference. If context reports
missing `PRODUCT.md`/`NO_PRODUCT_MD`, stop directions/artifacts and run
`/impeccable init`; Plan readiness stays `no` until PRODUCT.md exists. If
`DESIGN.md` is missing, run `/impeccable document` in scan or seed mode before
visual choices; refusal or uncertainty is a blocker, not a skip. Existing
PRODUCT/DESIGN answers are anchors and must not be overwritten silently.

## Required references

Load relevant impeccable refs: always `shape`, `spatial-design`, `typography`;
color/theming `color-and-contrast`; forms/nav/flows/permissions
`interaction-design`; motion `motion-design`; responsive `responsive-design`;
copy/errors/onboarding `ux-writing`; native image generation `codex` plus
palette/mock gates; Flutter/Dart also `building-flutter-apps`.

If a reference is unavailable, note it in the handoff.

## Required design behavior

- Pick register, scene, and color strategy before colors
- Use OKLCH semantic tokens, tinted neutrals, and readable contrast
- Name only enough atomic vocabulary to guide reuse
- Show multiple structural approaches, not trivial color swaps
- Reject category-reflex/AI-slop aesthetics
- Product UI: task focus, state coverage, familiar components. Brand UI: point
  of view, references, imagery when implied

## Gates

Do not compress these gates: context, direction input, palette when high
fidelity/native image generation is used, direction choice, and prototype
handoff. Gate 4 needs chosen/merged/customized/default/block with `Next: ready
for /he:implement: no`.

No full-flow UI prototype before gate 4 unless user explicitly skips visual design.

## Direction artifact rules

Show 2-4 directions with structural differences: hierarchy/topology, density,
type voice, color strategy, composition, component/material language, or motion.
For each: name, register fit, scene, tokens, type/density, component feel,
accessibility, and prototype carryover.

Direction artifacts must match the user request, then subject-project
tokens/components/CSS vars, brand assets, or styled pages. If no UI library or
token owner exists, create the smallest project-local token/component owner
first and mark any artifact-only styling as representative.

If native image generation exists, follow `reference/codex.md` Steps A-D, ask
Step A first, confirm one palette, generate 1-3 north-star mocks, then stop for
approval. Otherwise state unavailable and produce code-native boards or styled
key-screen concepts. Web default: `docs/planning/visual-design/<slug>/`.
Flutter default: `lib/visual_design/<slug>/` or `lib/main_visual_design.dart`.

## Preview rules

- First visual-design turn: create/update concept artifact only if useful
- Tool split: Grill Me owns active question/state; Impeccable Live reviews the
  real app route first; current-design-system mocks are fallback only. Capture
  UI choices with a saved `ui-review-receipt` from the visible review surface
- React previews should use the real route/localhost or Storybook; Flutter
  previews should use Flutter Widget Previewer, Widgetbook, or a simulator when
  platform behavior matters; local HTML is fallback only when no app surface
  exists
- Before asking for a choice, make the artifact show the exact current Grill Me
  question/options. Do not keep a stale preview open after moving to the next
  question
- For localhost, verify/free a port, serve only artifact dir, fetch exact HTML
  URL, and use `/` only for real `index.html`
- Label `Visual design preview:` only after verification; otherwise label `Run preview:` plus command and expected URL
- Flutter -> Flutter-native styled concept; verify/free port; run target entry
- Existing code -> reuse real routes, copy, components, and tokens; if they conflict with the direction, name it

## Stage handoff plan

At artifact creation/stage close/final synthesis, `03-visual-design.md` records
only relevant setup/refs, scene, directions, chosen direction, tokens/type,
accessibility, artifacts/previews, image status, and prototype handoff.

Clarity gate:
- Context gate is resolved
- PRODUCT.md, DESIGN.md, and the token/design-system owner are current, or the
  stage is blocked with an Impeccable init/document receipt
- User has selected, merged, customized, or accepted the default direction
- At least one styled key screen/flow moment exists when needed
- Palette/type/density/component decisions and initial vocabulary are captured
  enough for a prototype.
- Accessibility constraints are named or the stage is blocked
- Preview points to the actual artifact when shown
- Artifact feedback is applied when used; parked feedback blocks Plan readiness

## Q pattern

Use `modules/questions.md`. Show verified preview/status first, then ask one
style choice Q. Allow pick, merge, custom, use-default, or block. Keep setup,
refs, scene, directions, tokens, artifact path, why, and scenario for state,
artifact notes, stage close, or final synthesis.

## Rules

- Show 2-4 meaningfully different style directions; do not show trivial color swaps
- Each direction must include enough of a real screen/flow moment to judge the experience
- Ask about visual direction, density, hierarchy, tone, and fit; do not ask the user to approve invisible implementation details
- If the user says a direction feels wrong, ask what to preserve/change before generating more variants
- Do not proceed to a full-flow UI prototype until visual direction is chosen, merged, customized, or explicitly accepted as the default
- If the user cannot choose, ask what to preserve/change or generate a tighter second set of directions; do not silently pick
- The next-stage handoff must name the chosen direction and what the prototype must reuse from it
- Do not update `03-visual-design.md` per Q; record answers in `plan_draft.md` and summarize only at artifact creation/stage close/final synthesis
