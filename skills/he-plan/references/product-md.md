# PRODUCT.md

## Ownership

- `<repo-root>/PRODUCT.md` = repository product SSOT; every Git repository requires exactly one.
- Format = [product.md](https://product.md) canonical headings + Hard Eng proof additions.
- Headings = schema; alias-matched + order-free + prose first; YAML schema forbidden.
- Route + principle + lifecycle contract = `AGENTS.md` + `skills/`; restating them here forbidden.
- Missing/stale/contradictory + lifecycle product work → `he-plan` outcome decision → user approval.
- Direct bounded change → reuse current file; edit only when requested behavior changes product truth.

## Required

| Section | Accepted headings | Answers |
|---|---|---|
| Users | `Users` `Audience` | who it is for, in language they recognize |
| Purpose | `Product Purpose` `Purpose` `Value` | what it does + how success is measured |
| Boundaries | `Boundaries` `Non-goals` | what the product is not |
| Success | `Success` `Success metrics` | observable outcome + metric + target |
| Evidence | `Evidence` | canonical owner proving each claim |
| Unknowns | `Unknowns` `Open questions` | unresolved product truth + how it settles |

- Success + Evidence + Unknowns = Hard Eng proof additions; remainder = product.md canonical.
- Exactly one H1 = product name + one line answering "what is this".

## Optional

- Canonical = `Problem` + `Brand Personality` + `Tone` + `Anti-references` + `Design Principles` + `Accessibility & Inclusion` + `Offer` + `Stack`.
- Any other `##` section = allowed; duplicate heading = forbidden.
- Fenced block + info string `json product.md#<id>` = typed normative data; MUST parse.

## Template

```md
# <product>

<one line answering "what is this">

## Users

<who + their job to be done, in language they would recognize>

## Purpose

<what it does + how success is measured>

## Boundaries

- Not <the adjacent thing it is mistaken for>.

## Success

| Outcome | Metric | Target |
|---|---|---|
| <observable outcome> | <metric> | <target> |

## Evidence

- <claim> = <canonical owner path>

## Unknowns

- <unresolved product truth> = <how it settles>
```

## Proof

- Commands + result interpretation = `deterministic-checks` repository-context branch.
- Conformance owner = repository gate; external CLI/tooling dependency = none.
- Semantic truth = accepted Feature Brief; deterministic exit `0` cannot prove intent.

## Complete

- Root file valid + product truth current + every claim traced to a canonical owner.
