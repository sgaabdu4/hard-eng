# Hard Eng Design

## Overview

Hard Eng should feel like a serious engineering control surface: clear order,
dense but readable information, restrained color, and explicit handoffs. The
visual system follows a DESIGN.md-style contract: token values are normative;
this prose explains how to use them.

## Tokens

Token owner: `docs/design/tokens.css`

Use OKLCH colors, 8px radii, no negative letter spacing, and compact type
scales. Do not introduce a new palette or typography rhythm without updating
the token owner.

Semantic status tokens in `docs/design/tokens.css` own pass, ready, concern,
fail, blocked, and push-blocking gate color roles. Workflow visuals should use
those aliases instead of raw colors.

Workflow code labels wrap at arbitrary boundaries so long identifiers stay
inside narrow viewports.

## Components

Design system: `docs/project-workflow-gates.html`

The current component vocabulary is a hero summary, stage summary cells, stage
rows, terminal blocks, and checklist sections. Keep cards flat, avoid nested
cards, and reserve framed surfaces for repeated items or real tool surfaces.

Generated architecture reports are offline artifacts: inline CSS owns their
semantic report tokens, static inline SVG owns diagrams, and no external asset,
script, or network request may inspect private codebase content.

## States

Every workflow surface must make stage order, current state, blockers, next
command, and proof requirements visible. Failure states route back to the owner
stage; ready states require validated state and guardrails.

UI planning surfaces must show the current design system before implementation.
Grill Me chooses the UI flow/visual stages and keeps asking one question at a
time until user and agent are aligned with no guesswork; skipped UI/product
planning needs explicit user-approved skip evidence. Missing PRODUCT.md routes
through `/impeccable init`; missing DESIGN.md routes through `/impeccable
document` before visual choices. Impeccable Live reviews the real app route
first using current tokens, fonts, and shared components; localhost mock flows
are fallback evidence only when the real surface cannot exist yet. Required UI
review must be accepted, shown to the user, tied to a review surface, and
aligned with no open decisions or unknowns. UI decisions are captured by a
saved `ui-review-receipt` from a framework-native or localhost surface such as
a real React route, Storybook, Flutter Widget Previewer, Widgetbook, simulator,
or local HTML fallback. Accepted receipt status, artifact and receipt paths,
saved choices/components paths, selected/rejected options, chosen components,
screenshot paths for every option shown, user-visible screenshot evidence, and
approval must be saved before the UI plan is ready.

## Sources

Inspired by [Google Labs `design.md`](https://github.com/google-labs-code/design.md)
as a structured design-system memory format and by
[`impeccable`](https://github.com/pbakaus/impeccable) for PRODUCT/DESIGN context
loading, token-first UI, contrast, responsive, component, and state checks.

## Change Rule

Any UI, visual, component, token, design-system, or stage-diagram change must
update this file and the token owner when values or component rules change.
Any product behavior or positioning change must update `PRODUCT.md`.
