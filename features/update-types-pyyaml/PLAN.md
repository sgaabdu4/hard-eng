# Update types-pyyaml to clear the freshness gate

Status: Complete

## Outcome + scope

The dev dependency `types-pyyaml` moves to 6.0.12.20261030, so the `freshness` gate passes again. Non-goals: other dependencies, code changes.

## Repository context

Owners: `pyproject.toml` dev group and `uv.lock`; the `freshness` gate named the command `uv add --dev 'types-pyyaml>=6.0.12.20261030'`.
Same cause: N/A — a new upstream release passed the 2-day minimum release age; no other direct dependency is outdated.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Baseline repair for Abid's 2026-11-01 request to ship the fork subagent setting to develop and main.

## Acceptance + steps

- [x] `freshness` reports no outdated direct dependency → N/A — no test can prove an upstream release; the `freshness` gate passed in a local `check` on this branch.
- [x] Type checks still pass with the new stubs → N/A — the `types` gate is the proof; it passed in a local `check` on this branch.

## Baseline + execution

Result: Passed
Evidence: develop b4f5c6d: Hard Eng CI run 41262777417 passed. A local `check` on 2026-11-01 failed only `freshness` for this release, plus 6 Dart and Swift tests that need `dart` and `swiftc`, which this container lacks.
Execution: One builder, this session.

## Risks + recovery

N/A — type stubs only; no runtime code uses them.

## ux_reference

N/A — dependency only; no visible UI.

## Verification

Result: Passed
Evidence: local `check`: every gate passed except 6 Dart and Swift tests, which fail only for the missing `dart` and `swiftc`; CI installs both. 2103 tests passed.
E2E: N/A — no user journey changes.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
