# UI Decision Lab

Plan cannot pass for UI work until the user can inspect the complete intended
flow with realistic mock data.

- Discover the existing theme/token/component/layout owner and interaction
  patterns. Capture a reproducible sanitized baseline for existing UI; record a
  reason for a genuinely greenfield baseline.
- Review the actual app route first when it exists. When the target surface
  cannot exist before implementation, build the smallest code-native
  interactive prototype from the current design owners and label it as a Plan
  artifact.
- Existing stable systems use coded variations from real tokens/components.
  Greenfield, complete-new-UI, or radical-redesign work may offer OpenAI
  Imagegen direction boards only after explicit call-budget approval. A fully
  constrained direction skips options.
- Imagegen compares two or three distinct boards using identical product flow,
  states, and mock content. Pixels are exploration, never the token, component,
  interaction, responsive, or accessibility owner.
- Translate the selected direction into a code-native token proposal and an
  interactive prototype. Use HTML/CSS for web; use native previews for an
  existing non-web product when HTML would misrepresent it.
- Exercise happy, loading, empty, validation, permission, and error states.
  Store artifacts under `.hard-eng/prototypes/<run-id>/`; no secrets, private
  datasets, live auth/storage/payments/analytics/external APIs, network
  dependencies, or production-module edits. Mark the coded
  root `data-hard-eng-prototype="interactive"` and mock content
  `data-mock="realistic-sanitized"` so the validator can reject static shells.
- Record baseline, exploration path, prototype path/digest, user-approved
  direction, mock states, coded-option disposition, and Build review cadence in
  section 6 of `plan.md`.

Review cadence is `every-vertical-slice`, `meaningful-milestones` (default), or
`final-candidate`. User-visible work always keeps Plan direction approval and
final candidate approval. A video is optional when sequence matters; the coded
interactive prototype remains the Plan approval surface.
