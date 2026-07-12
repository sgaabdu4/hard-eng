---
name: writing-great-skills
description: Design or review terse, predictable agent skills.
---

# Writing Great Skills

## Contract

- Goal = predictable process + task-valid output variance.
- Mechanics = `$skill-creator`; quality = this skill.
- Term ambiguity/failure diagnosis → [GLOSSARY.md](GLOSSARY.md).
- Unproven applicable gate → `CONCERNS | FAIL`.

## Gates

| Gate | `PASS` proof |
|---|---|
| Need | Remove skill → reusable non-default behavior materially degrades. |
| Trigger | Description = leading concept + purpose + one unique trigger/branch; no body summary/synonym pile. |
| Invocation | Implicit only when autonomous reach earns context; otherwise `allow_implicit_invocation: false`. |
| Branch | One distinct use → one branch + representative prompt; same action/proof → merge. |
| Hierarchy | `SKILL.md` = router + universal invariants; branch detail → directly linked reference. |
| Workflow | ≥3 ordered actions → one reference or deterministic script; each action ends in checkable completion. |
| Resource | Script = repeated fragile logic; reference = branch/workflow; asset = copied output material; each has one owner/consumer. |
| SSOT | Definition + rule + caveat share one owner; other surfaces point to it. |
| Steering | Strong pretrained leading words + positive target; prohibition pairs with replacement action. |
| Split | Independent invocation or observed premature completion only; otherwise keep together. |
| Prune | Remove no-op + duplication + sediment + irrelevant branch; every line changes behavior/knowledge. |
| Format | Agent Markdown = terse `=` + `→` + `+` + tables; symbols remain unambiguous to weak/local models. |
| Package | `SKILL.md` + required `agents/`/resources only; no README/changelog/install guide/placeholder/legacy owner. |
| Validation | Current Codex validator + smallest realistic forward proof + metadata/resource parity. |

## DRY

- Scan = frontmatter + `SKILL.md` + references + scripts + sibling skills + `AGENTS.md`.
- Same meaning → one canonical owner + pointer; repeated gates/templates/lists/safety prose → delete copies.
- Description = routing only; body = universal execution only; reference = branch/workflow only.
- Executable enforcement may mirror a human contract only when a deterministic parity test prevents drift.

## Failure Route

| Failure | Repair |
|---|---|
| Wrong trigger/invocation | Fix description branch or policy. |
| Missed/always-loaded detail | Fix pointer; inline universal invariant; delete irrelevant reference. |
| Partial/premature work | Strengthen completion → split sequence only if failure persists. |
| Token growth/conflict | Run DRY/SSOT scan → full migration to one owner. |
