---
name: code-review
description: Code review for branch, PR, commit, or WIP diffs against repository standards and originating behavioral sources before merge.
---

# Code Review

## Target

- Fixed point = user ref; else upstream merge-base; else `origin/main`; else `main`.
- Prove `git rev-parse <base>` + non-empty committed/WIP evidence; failure = `FAIL` before review.

| Scope | Required evidence |
|---|---|
| Committed | `git diff <base>...HEAD` + `git log <base>..HEAD --oneline`; requested commit range = each patch + cumulative diff |
| WIP | `git diff --cached` + `git diff` + `git ls-files --others --exclude-standard`; read every in-scope untracked file |

- Read full hunks + nearby owners; stats/names/subjects = insufficient.

## Axes

| Axis | Question |
|---|---|
| Standards | Correct, safe, maintainable, tested, repository-compliant, gate-clean? |
| Spec | Originating request/spec complete, correctly scoped, behaviorally faithful? |

- Originating behavioral source exists or is likely → read [spec.md](references/spec.md); standards-only request or confirmed absence → skip Spec + state why.
- One issue affecting both axes → distinct evidence under each; never merge/rerank axes.

## Evidence

- Standards sources = applicable `AGENTS.md` + coding/contribution/framework/architecture docs; repo rules override heuristics.
- Finding = exact file:line/hunk + code fact/quote + risk + simpler fix + confidence.
- Blast radius = owners/callers + packages + schemas + cache/storage keys + tests/fixtures + routes/endpoints + docs/config.
- Direct perspectives = architecture/ownership + tests + edge/ripple + security + touched stack/perf/UX/DevOps.
- Architecture = owner/abstraction/code-judo; tests = public behavior/mocks/edges/cannot-fail; ripple = null/empty/concurrency/timezone/permissions/network/downstream.
- Security = auth/authz/trust/secrets/injection/exposure/crypto/config; stack = touched framework/perf/UX/DevOps only.
- Subagents = explicit user request only; active lifecycle state → record scope/status/recovery in its `agentWork[]`; standalone → record under Coverage; parent verifies every finding.
- Required change ≠ optional taste; tooling-enforced result stays in Gates unless enforcement is broken or risk needs manual explanation.
- Maintainability = merge concern, not polish.
- Smells = mysterious name + duplication + feature envy + data clump + primitive obsession + repeated switch + shotgun/divergent change + message chain + middle man/pass-through + refused bequest + speculative layer.
- Also challenge = wrong owner + scattered flags + casts/`any`/`unknown` + nullable modes + hidden fallback + unjustified sequential/non-atomic orchestration + oversized owner + implementation-detail test.
- Prefer deletion + owner reuse + simpler invariant over wrapper/mode/layer growth.
- Load matching specialist skills/tools; unavailable → state once + continue with evidence-backed fallback.
- Applicable gates → `$deterministic-checks`; cite commands/exits + reports; inspect project scripts, hook owner/wiring, executable bits, and suppression.
- Required pre-push proof → safe `git push --dry-run`; if unavailable/non-exercising, run full gate directly + report hook gap.
- Final audit = reread evidence; reject uncited, preference-only, overstated, duplicate, or non-actionable candidates; record unknowns.

## Completion

- Account for every in-scope hunk/file + applicable perspective + blast-radius surface + Spec requirement + gate as reviewed, `N/A`, or unknown.
- Verdict-changing unknown or incomplete coverage → `CONCERNS` or `FAIL`; never approve.

## Severity

| Level | Meaning |
|---|---|
| Critical | Correctness/security/privacy/data/migration/schema/API/invariant/gate/root-owner/file-size/cross-package release blocker |
| Medium | Localized maintainability, duplication, missing public-boundary test/docs, or brittle special case |
| Low | Cheap localized clarity, naming, test, or docs fix |
| Info | Optional alternative, education, praise, or future cleanup; never required |

## Report

| Section | Content |
|---|---|
| Standards | Findings grouped by severity |
| Spec | Findings grouped by severity, or explicit skip |
| Coverage | Hunks/files + perspectives + blast radius + Spec requirements + delegation |
| Unknowns | Unverified evidence + impact |
| Gates | Command + pass/fail/not-run + evidence |
| Verdict | Block / approve with reservations / approve |
| Final line | Finding count + worst issue per axis |

- Critical remains → Block. Medium → fix before merge unless explicitly deferred.
