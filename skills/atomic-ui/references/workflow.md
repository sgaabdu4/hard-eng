# Atomic UI Workflow

1. Locate the existing SSOT before editing: design tokens, theme files, primitives, component library, layout templates, and story/example files.
2. Reuse the SSOT when it exists.
3. If absent, create the smallest project-local SSOT needed for the task before building screens.
4. Keep hierarchy clear: atoms/primitives for raw controls and tokens, molecules/components for composed controls, organisms/sections for feature UI, templates/layouts for page structure, pages/routes for concrete data and orchestration.
5. Put reused visual decisions in tokens/theme: color, spacing, radius, typography, elevation, and motion.
6. Avoid hardcoded reusable values in product code unless they are one-off layout constraints.
7. Add components only when they own behavior, styling, or composition.
8. Verify responsive and interactive states for changed UI.
