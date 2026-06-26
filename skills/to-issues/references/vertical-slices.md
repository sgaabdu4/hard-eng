# Vertical Slice Issues

A useful issue delivers a narrow end-to-end behavior that can be built, tested,
reviewed, and demoed independently.
Avoid horizontal tasks such as "create database layer" unless they unblock a
specific user-visible slice and cannot be folded into it.

## Drafting Flow

1. Gather the source.
   Use the accepted PRD, plan, issue, or conversation summary.
   Preserve confirmed scope and mark assumptions.

2. Find the slices.
   Each slice should travel through the relevant layers: UI, API, domain logic,
   storage, jobs, tests, docs, or config.
   Split when acceptance criteria, risk, or ownership differs.

3. Order by dependency.
   Start with a tracer slice that proves the main route through the system.
   Put prefactoring first only when it removes real blocker complexity.

4. Add acceptance and verification.
    Every issue needs behavior-facing acceptance criteria and the smallest
    relevant check: unit, integration, E2E, manual, migration, or observability.
   Include the expected owner, likely touched files/modules, and rollback or
   risk note when the slice changes data, auth, schema, deployment, or user
   workflow.

5. Ask one calibration question if needed.
   Only ask when slice granularity, dependency order, or scope boundary is
   genuinely blocked.

## Issue Template

```md
## What to build
<one vertical behavior>

## User outcome
<what the user or operator can do after this slice>

## Why
<user value or engineering risk reduced>

## Scope
- <included>
- <included>

## Out of scope
- <excluded>

## Dependencies
- Blocked by: <issue/title | none>
- Unblocks: <issue/title | none>

## Acceptance criteria
- [ ] <behavior-facing criterion>
- [ ] <edge or failure criterion>

## Verification
- <test/check/manual proof>

## Rollback / risk note
- <rollback, migration, monitoring, or risk note | none>

## Agent context
- Owner files/modules:
- Likely touched files:
- Contracts/routes/schema/storage:
- Risks:
```

## Final Report

Return the issue list in dependency order.
Call out slices that are too large, too small, or risky to parallelize.
