# Repository Context Gates

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
- Semantic truth/approval = `$he-plan` + `$atomic-ui`; deterministic exit `0` cannot prove intent.
