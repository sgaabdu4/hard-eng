# Repository Context Gates

- Scope = Feature Loop work changing product/design SSOT + explicit repository-context/design-SSOT work.
- Direct/Feature Loop work not changing those owners = do not run solely because context files are missing/old.

## Commands

```sh
python3 <agents-root>/skills/deterministic-checks/scripts/context-docs.py --repo <repo-root>
node <agents-root>/skills/deterministic-checks/scripts/check-design-md.js <repo-root>/DESIGN.md
```

## Contract

- Structural result = `valid | invalid`; invalid = missing/duplicate/nested owner + PRODUCT structure/order + DESIGN alpha envelope/order.
- Google gate = DESIGN schema/references/contrast/orphans; error or warning = block.
- Visual surface present → project-owned `DESIGN.md → runtime tokens/theme/assets` sync gate required.
- Visual surface none → approved `Visual surface = none` + revisit trigger required.
- Semantic truth = accepted Feature Brief + `$atomic-ui`; deterministic exit `0` cannot prove intent.
