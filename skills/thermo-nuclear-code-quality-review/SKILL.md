---
name: thermo-nuclear-code-quality-review
description: Use for strict maintainability review: diffs, PRs, commits, wrappers, abstractions, spaghetti, giant files, weak tests.
---

# Thermo-Nuclear Review

Review maintainability as a blocker, not a polish pass. Prefer behavior-preserving simplification that deletes concepts, branches, wrappers, modes, or layers.

## Load

Use relevant skills/tools when available: `terse`, `codebase-memory`, `test-quality`, React/Vercel/React Doctor/Fallow, Flutter, Appwrite. If absent, state unavailable and continue.

## Target

- Local branch: upstream merge-base if present, else `origin/main`, else `main`
- PR/commit range: exact user range
- Dirty tree: include staged and unstaged
- Commit-by-commit: review each patch, then cumulative diff

Read full patches; stats/name-only/subjects are insufficient.

## Standard

Every finding needs exact file/line or hunk, code fact/quote, structural risk, and simpler target.

Block or challenge:
- wrong-owner logic
- pass-through abstractions
- scattered feature flags/branches in busy flows
- casts, `any`, `unknown`, nullable modes, silent fallback hiding invariants
- orchestration that is sequential or non-atomic without reason
- file growth past repo limit
- tests that assert implementation instead of public behavior
- missing required gates

## Flow

1. Read repo rules and target diff.
2. Map owners, callers, routes, schemas, storage/cache keys, tests, and package boundaries.
3. Use subagents in parallel when available for independent focus areas; parent verifies all findings.
4. Run stack-specific gates. React/Next/TS requires React Doctor/Fallow evidence and `git push --dry-run` when project policy expects pre-push gates.
5. Run final auditor pass: dedupe, reject weak claims, classify severity, list unknowns.

Read `references/review-board.md` for reviewer roles, severity taxonomy, gate audit, and report template.

## Verdict

Do not approve while any Critical remains. Medium items should fix before merge unless explicitly deferred. Keep Info-only separate from required changes.
