# Agent Rules

## Stop
- Material uncertainty/conflict → inspect evidence → ask 1 targeted question → wait.
- Non-trivial mutation → resolve all material unknowns first.
- User correction → pause → reconcile goal + plan/state → show delta → confirm → mutate.
- Goal/plan/state mismatch → pause; never choose an owner silently.
- Destructive action/external write/commit/push/merge/publish → exact scoped approval.
- Secret/credential exposure → stop + report.

## Engineering
- KISS = fewest complete concepts.
- YAGNI = remove speculation; never omit correctness/root cause/blast radius.
- DRY = one fact once.
- SSOT = one canonical owner.
- Fix = root owner + every connected caller/schema/key/test/route/doc/config/live wire.
- Replacement → full migration; delete legacy/alias/compatibility/dual paths.
- Patchwork/pass-through wrappers = forbidden.
- Preserve security/trust/privacy/accessibility/schema/data-loss protections.

## Route
- New feature/material behavior/ambiguous product or UI → `he-plan`.
- Accepted bounded plan → `he-build`.
- `he-build` = Implement ⇄ Verify until the exact candidate is green.
- Green accepted candidate → `he-ship`.
- Proven process gap only → `he-learn`.
- Small clear fix/read-only audit/explanation → direct.
- Missing required stage → stop + report; never improvise a replacement.
- Automatic subagents/model evals/Imagegen/daemons/cron/watchdogs/retries = forbidden.

## Tools
- Topology/callers/dependencies/impact → `codebase-memory-mcp cli ...` only.
- Missing/stale index → index once.
- CLI failure → report once → bounded `rg` fallback.
- Large evidence → bounded Context Mode.
- Exact text/path → `rg`.
- File mutation → `apply_patch`.

## Proof
- Read before claim/edit.
- Validation breadth ≥ change blast radius.
- Recurring violation → narrow deterministic check.
- Evidence class = `Verified | Inferred | Unknown`.
- Final status = `PASS | CONCERNS | FAIL`; include why, risk, proof/gaps.
- No commit/push/merge/publish without its approval boundary.

## Markdown
- Agent-facing `.md` = terse directives; paragraph prose = forbidden.
- Mapping = `concept = owner`; routing = `condition → action`; sequence = `A → B ⇄ C`.
- Symbols must remain unambiguous to weak/local models.
- `README.md` = human writing.
- Canonical docs = current accepted state only; omit before/rejected/migration history.
