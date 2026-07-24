# DESIGN.md

## Ownership

- `<repo-root>/DESIGN.md` = repository visual SSOT; every Git repository requires exactly one.
- Format = [Google DESIGN.md](https://github.com/google-labs-code/design.md/blob/main/docs/spec.md) alpha schema.
- YAML tokens = normative; Markdown = terse rationale/application.
- Production token/theme owners = generated from or deterministically sync-checked against `DESIGN.md`.
- Eligible lifecycle/design-system work + missing/stale/contradictory file → `$he-plan` UX decision + `$atomic-ui` inventory/migration.
- Direct bounded UI edit → reuse production owner; do not create/repair this file unless the requested behavior changes its reusable contract.

## Route

1. Inventory brand assets + tokens/themes + primitives/components + actual consumers.
2. Classify visual surface = `present | none`; code proves current state, user approves intended direction.
3. Missing/invalid/drift → research + propose decision-useful options + obtain explicit approval.
4. Write root `DESIGN.md` → migrate duplicate/hardcoded reusable values → delete parallel owners.
5. Run `$deterministic-checks` repository-context branch + project sync gate + affected UI/a11y proof; record a material reusable-design decision in the active Feature Brief when one exists.

## Visual Surface = none

```md
---
version: alpha
name: <product>
description: No user-visible visual surface.
---

## Overview
- Visual surface = none
- Visual system = not applicable
- Revisit trigger = first user-visible UI, brand asset, or generated visual output
```

- No-visual repository still requires the file; UX feature work may skip only after this declaration is approved.

## Visual Surface = present

- Frontmatter = `version + name + colors + typography + spacing/rounded/components when applicable`.
- Body order = `Overview → Colors → Typography → Layout → Elevation & Depth → Shapes → Components → Do's and Don'ts`.
- Cover semantics + interaction states + responsive/a11y constraints + asset treatment.
- Existing visual system → extract evidence first; never invent replacements from inconsistent code.

## Proof

- Commands + result interpretation = `$deterministic-checks` repository-context branch.
- Lint error/warning = block; no silent downgrade.
- Alpha-format change = explicit migration + locked dependency/CI update; silent format drift = forbidden.

## Complete

- Root file valid + intended direction approved + actual visual owners mapped.
- Reusable tokens/components have one editable owner + deterministic sync proof.
