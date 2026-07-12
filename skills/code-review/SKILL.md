---
name: code-review
description: Review branch, PR, commit, or WIP diffs against repository standards and intended behavior.
---

# Code Review

## Target

- Base = user ref → upstream merge-base → `origin/main` → `main`.
- Prove base resolves + combined committed/WIP evidence is non-empty; else `FAIL`.

| Scope | Evidence |
|---|---|
| Committed | `git diff <base>...HEAD` + `git log <base>..HEAD --oneline`; commit range → each patch + cumulative diff |
| WIP | cached diff + unstaged diff + every untracked in-scope file |

- Review full hunks + nearby owners; stats/names/subjects = insufficient.

## Axes

| Axis | Question |
|---|---|
| Standards | Correct + safe + maintainable + tested + repo-compliant + gate-clean? |
| Spec | Originating behavior complete + faithful + no scope creep? |

- Behavioral source exists/likely → [spec.md](references/spec.md); confirmed absent/standards-only → skip Spec + why.
- One issue affecting both axes → distinct evidence per axis; never merge/rerank.

## Review

- Standards = applicable repo rules/docs; repo rules override heuristics.
- Finding = exact file:line/hunk + code fact + risk + simpler fix + confidence.
- Coverage/blast radius = apply global `AGENTS.md` Evidence contract.

| Lens | Challenge |
|---|---|
| Architecture | ownership + abstraction + deletion/code-judo opportunity |
| Tests | `$test-quality`; report unproven behavior/strength gaps |
| Ripple | null/empty + concurrency/timezone + permission/network + downstream |
| Security | auth/authz + trust/secrets + injection/exposure + crypto/config |
| Specialist | touched stack + performance + UX + DevOps only |

- Smells = mystery name + duplication + data clump/primitive obsession + repeated switch + shotgun/divergent change + message chain/middle man + speculative layer.
- Also challenge = wrong owner + scattered flags + casts/nullable modes + hidden fallback + non-atomic orchestration + oversized owner + implementation-detail test.
- Required change ≠ taste; prefer deletion + owner reuse + simpler invariant.
- Gates/hooks/pre-push = `$deterministic-checks`; report commands/exits/reports + suppression/wiring gaps.
- Required real UI proof = `$e2e`; absent evidence = unknown, never reviewer-inferred `PASS`.
- Final audit = reject uncited, preference-only, overstated, duplicate, or non-actionable candidates; retain unknowns.

## Complete

- Every hunk/file + applicable lens + blast-radius surface + Spec requirement + gate = reviewed, `N/A`, or unknown.
- Verdict-changing unknown/incomplete coverage → `CONCERNS | FAIL`; never approve.

## Severity

| Level | Meaning |
|---|---|
| Critical | Correctness/security/privacy/data/migration/schema/API/invariant/gate/root-owner/file-size/cross-package blocker |
| Medium | Local maintainability/duplication + missing public-boundary test/docs + brittle special case |
| Low | Cheap local clarity/naming/test/docs fix |
| Info | Optional alternative/education/praise/future cleanup; never required |

## Report

| Section | Content |
|---|---|
| Standards | Findings by severity |
| Spec | Findings by severity or explicit skip |
| Coverage | Hunks/files + lenses + blast radius + requirements + delegation |
| Unknowns | Unverified evidence + impact |
| Gates | Command + result + evidence |
| Verdict | Block / approve with reservations / approve |
| Final line | Count + worst issue per axis |

- Critical → Block; Medium → fix before merge unless explicitly deferred.
