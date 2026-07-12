# Thermo-Nuclear Review Details

## Flow

1. Read repo rules and target diff.
2. Map owners, callers, routes, schemas, storage/cache keys, tests, and package boundaries.
3. Review independent focus areas directly. Use subagents only after an explicit user request; the parent records each delegated reviewer in `agentWork[]` and verifies all findings.
4. Run stack-specific gates. React/Next requires React Doctor, Fallow duplicate/clone result evidence, lint, positive typecheck pass/result evidence, and `git push --dry-run` when project policy expects pre-push gates.
5. Run final auditor pass: dedupe, reject weak claims, classify severity, and list unknowns.

## Review Board

Cover these independent reviewer perspectives directly by default. If the user
explicitly requests delegation, assign only the requested perspectives:

- Staff/architecture: ownership, abstraction quality, code-judo simplification
- Test quality: public-boundary coverage, mocks, edge cases, tests that cannot fail
- Edge/ripple: null, empty, concurrency, timezone, permissions, network partials, downstream callers
- Security: auth, authorization, trust boundaries, secrets, injection, data exposure, crypto, config
- Stack specialists only when touched: React/TS, Flutter, Appwrite, Fallow/cleanup, perf, UX, DevOps

Each reviewer returns lifecycle status/progress plus findings: severity, evidence, structural risk, simpler direction, confidence. Parent verifies, records recovery details for incomplete work, and decides.

## Final Auditor

Re-read evidence for every candidate finding. Reject uncited, preference-only, overstated, or non-actionable claims. Deduplicate. Ask whether each fix deletes complexity or just moves/wraps it. Record unknowns.

## Severity

- Critical: correctness break, security/privacy exposure, data loss, broken gate/build, migration/schema/API contract risk, cross-package regression, shared-flow spaghetti, wrong-owner logic, weak contract hiding invariant, file-size violation, missing required pre-push/React/Fallow/lint/typecheck gate
- Medium: localized maintainability risk, missing public-boundary tests, duplication, avoidable special case, incomplete docs for changed behavior, brittle orchestration with contained blast radius
- Low: cheap localized clarity/naming/test/docs issue
- Info only: best practice, education, future cleanup, praise, optional alternative. No required change

## React / Next / TS Gate

Detect via changed TS/JS files or deps. Required:

1. Inspect scripts and hooks.
2. Verify pre-push gate runs React Doctor, Fallow duplicate/clone evidence, lint, and typecheck, or report blocker.
3. Run `git push --dry-run` when safe/available.
4. If dry-run cannot exercise hooks, run React Doctor/Fallow/lint/typecheck directly and still report missing hook.
5. Diagnose with project scripts or standalone CLI.

## Gate Audit

Check hook manager setup, `.husky/pre-push`/`lefthook.yml`/`.git/hooks/pre-push`, executable bits, full quality gates, dry-push success, and whether failures were fixed rather than suppressed.

## Output

When paired with `code-review` for a branch, PR, WIP diff, or spec-linked
review, use its separate Standards and Spec report, with severity inside each
axis. The template below is only for a standalone maintainability review.

```md
## Findings
### Critical
- <file:line> - <required change>. Evidence: <quote/hunk/cmd>. Risk: <why blocks>. Fix: <simpler target>
### Medium
- <none>
### Low
- <none>
### Info only
- <none>

## Code-Judo Opportunities
- <behavior-preserving simplification> - evidence: <file:line/hunk>

## Review Board
- Subagents: <user-requested/unrequested/unavailable>
- Final auditor: <done/not done>

## Blast Radius
- Direct callers/Cross-package/Schema/Cache/Tests/Routes: <evidence>

## Gates
- Pre-push/dry-run/React Doctor/Fallow/tests/typecheck/lint: <pass/fail/not run + evidence>

## Verdict
- Block / approve with reservations / approve
```
