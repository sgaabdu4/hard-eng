---
name: atomic-ui
description: Use for UI components, design systems, atomic design, tokens, themes, hardcoded visuals, or missing design SSOT.
---

# Atomic UI

Use atomic design as a practical UI SSOT, not folder dogma.

## Trigger

Use for:
- New or changed UI components
- Design-system or token work
- Reusable layout, theme, primitive, or page composition
- Removing duplicated styles or hardcoded visual decisions

## Flow

1. Locate the existing SSOT before editing:
   - design tokens
   - theme files
   - primitives
   - component library
   - layout templates
   - story/example files
2. Reuse the SSOT when it exists.
3. If absent, create the smallest project-local SSOT needed for the task before building screens.
4. Keep hierarchy clear:
   - atoms/primitives: raw controls, typography, icons, tokens
   - molecules/components: small composed controls
   - organisms/sections: feature-level composed UI
   - templates/layouts: page structure without final data
   - pages/routes: concrete data and orchestration
5. Put visual decisions in tokens/theme when reused: color, spacing, radius, typography, elevation, motion.
6. Avoid hardcoded reusable values in product code unless they are one-off layout constraints.
7. Do not add wrappers that only pass props through. Add a component only when it owns behavior, styling, or composition.
8. Verify responsive states and interactive states for changed UI.

## Review Report

For UI reviews, report:
- SSOT found or created
- Token/theme reuse
- New reusable components and their hierarchy role
- Hardcoded visual values left behind
- Responsive/accessibility verification
