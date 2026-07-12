---
name: writing-great-skills
description: Design or review predictable, terse agent skills. Use for SKILL.md architecture, descriptions, routing, references, completion criteria, and pruning.
---

# Writing Great Skills

## Contract

- Root virtue = predictable process + task-appropriate output variance.
- Mechanics owner = `$skill-creator`; quality owner = this skill.
- Term ambiguity or failure diagnosis → read [GLOSSARY.md](GLOSSARY.md).
- Completion = every applicable gate proven; unresolved gate → `CONCERNS` or `FAIL`.

## Gates

| Axis | Target | Proof |
|---|---|---|
| Need | Skill adds non-default, reusable behavior. | Remove it → behavior materially degrades. |
| Branches | One distinct use = one branch. | Concrete trigger/example exists per branch. |
| Invocation | Implicit only when autonomous reach earns context load; otherwise explicit-only. | `agents/openai.yaml` policy matches intent. |
| Description | Leading concept + purpose + one trigger per branch. | No trigger synonyms, body summary, or unsupported frontmatter. |
| Hierarchy | Universal action inline; conditional reference behind a precise pointer. | Each file loads only when its branch needs it. |
| Steps | Each action ends on a checkable + sufficiently exhaustive completion criterion. | Agent can distinguish done from partial. |
| Resources | Repeated fragile logic → script; consulted knowledge → reference; copied output material → asset. | Every resource has one consumer + pointer. |
| Co-location | Definition + rules + caveats share one owner. | Meaning is not scattered. |
| Steering | Strong pretrained leading words + positive targets. | Wording changes behavior without restatement. |
| Split | Split only for independent invocation or observed premature completion. | Cut reduces context/cognitive load or hides later steps. |
| Pruning | Delete duplication + no-ops + sediment + irrelevant branches. | Each line changes behavior or supplies necessary knowledge. |
| Format | Agent `.md` = terse directives using `=` + `→` + tables; README = human prose. | Weak/local model reads once without inference gaps. |
| Package | Essential runtime files only. | No README, changelog, install guide, placeholders, legacy, or duplicate SSOT. |
| Validation | Current Codex contract + smallest realistic forward proof. | Validator passes + representative prompt follows intended path. |

## Codex Invocation

- Implicit = description visible + `policy.allow_implicit_invocation: true` or omitted.
- Explicit-only = valid description + `policy.allow_implicit_invocation: false`; invoke with `$skill-name`.
- Frontmatter = `name` + `description` only.

## Failure Routing

- Wrong trigger → description branch/leading concept.
- Missed reference → pointer wording/hierarchy.
- Partial work → completion criterion, then sequence split only if observed.
- Token growth → duplication/no-op/sediment/sprawl audit.
- Conflicting behavior → SSOT/co-location repair + full migration.
