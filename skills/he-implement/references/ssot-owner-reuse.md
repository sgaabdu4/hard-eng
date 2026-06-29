# SSOT Owner Reuse

Run this substage before `test-first` and before any owner change.

## Required Ledger

Record `ssot-owner-reuse` in `he-state.json.subStages[]` with evidence for each relevant owner class:

- shared and feature-peer widgets/components;
- list, row, card, modal, form, picker, tab, navigation, CTA, empty, loading, and error patterns;
- interaction owners: single select, multi select, checkbox, toggle, selectable cards/chips, settings rows, answer cards, alert controls, calendar/date-grid/month navigation, drag/drop, search/filter, pagination, uploads, and steppers;
- domain owners: date/time, currency/number formatting, permissions, API/repository/schema/query/cache, constants, fixtures, and test helpers;
- clone or duplicate evidence from Fallow for JS/TS, a stack-specific detector when available, or explicit static-search fallback evidence;
- design tokens, theme, typography, spacing, colors, radius, and motion

Use `ownerLedger[]` entries with `ownerClass`, `decision`, `owner` for reuse/extend/create decisions, and non-empty `evidence[]`.

Each relevant owner decision must be one of:

- `reuse`
- `extend existing owner`
- `create feature-local owner`
- `create shared owner`
- `not applicable`, with evidence

## Blocking Rules

- UI/component work cannot mark `ssot-scanners` as `not_applicable` without component, interaction-pattern, or similar-screen search evidence
- Raw framework controls are blocked when app-owned primitives exist unless the ledger justifies the exception
- Parallel local implementations are blocked when a similar owner exists; reuse, extend, or extract instead
- New or worsened clone groups are blocked unless the ledger names the temporary owner, guard, and removal path
- JS/TS duplicate checks require Fallow evidence; other stacks need stack-specific tool evidence or a tool-absence reason plus static-search evidence
- If no owner exists, create the smallest project-local owner before building screens

Receipts for `/he:implement` must summarize `SSOT reused`, `SSOT extended`, and `new owners created`.
