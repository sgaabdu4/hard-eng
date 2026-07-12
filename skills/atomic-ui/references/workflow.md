# Atomic UI Workflow

1. Locate the existing SSOT before editing: design tokens, theme files, primitives, component library, layout templates, and story/example files.
2. Search by interaction and domain pattern, not just component name: select/toggle/checkbox/card/list/form/picker/calendar/navigation/empty/error/loading, plus formatting, API/schema/query/cache, fixtures, and helpers.
3. Treat duplicate widgets, clone groups, repeated helpers, and near-duplicate screens as owner evidence; record Fallow duplicate/clone result evidence for JS/TS.
4. Reuse the SSOT when it exists.
5. If absent, create the smallest project-local SSOT needed for the task before building screens.
6. Keep hierarchy clear: atoms/primitives for raw controls and tokens, molecules/components for composed controls, organisms/sections for feature UI, templates/layouts for page structure, pages/routes for concrete data and orchestration.
7. Put reused visual decisions in tokens/theme: color, spacing, radius, typography, elevation, and motion.
8. Avoid hardcoded reusable values in product code unless they are one-off layout constraints.
9. Add components only when they own behavior, styling, or composition.
10. Verify responsive and interactive states for changed UI.
