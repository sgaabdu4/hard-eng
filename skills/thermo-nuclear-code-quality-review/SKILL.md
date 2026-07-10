---
name: thermo-nuclear-code-quality-review
description: Branch, PR, or WIP diff review requires both code-review and thermo-nuclear-code-quality-review for strict maintainability.
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

Read `references/review-board.md` for workflow, reviewer roles, severity taxonomy, gate audit, and report template.
For PR, branch, or spec-linked review, also read `references/standards-spec-review.md`.

## Verdict

Do not approve while any Critical remains. Medium items should fix before merge unless explicitly deferred. Keep Info-only separate from required changes.
