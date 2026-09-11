# Reuse walkthrough checks for recorded E2E

Status: Complete

## Outcome + scope

Give E2E a recorded-web verification route through the existing walkthrough recorder and checkers, separate from MP4 delivery. Strengthen the fix/retest and user-reported-defect loop. Preserve native browser/device/API/CLI verification and durable-state assertions. No new runner, dependencies, checker implementation or he-build skill.

## Repository context

E2E owns real journey assertions; product-walkthrough-video owns recording, mechanical review and playback proof. Its existing pointer=false configuration supports proof recordings. review-video.mjs requires the recorder's WebM and full run report; it is not a generic device-video checker. Existing gesture smoke tests cover both pointer modes and reject ambiguous keyboard activation and no-op scrolling.

## Decisions + authorization

Blockers: None

The user approved fixing E2E first and reusing walkthrough checkers, suggesting two walkthrough sides called by E2E. Continue under the existing autonomous rebuild authorization and YAGNI constraint. One builder; local skill/document changes and disposable test execution only. No commit, push, global installation or other-project changes. This effort has a separate compact plan because the existing root plan records completed planning-gate work.

## Acceptance + steps

- [x] E2E routes recorded web proof to existing walkthrough checks; ordinary tests and native surfaces keep their current tools.
- [x] Shared WebM verification requires mechanical and actual visual review; review-required is not completion. MP4 conversion and separate final review apply only to video delivery.
- [x] User-reported defects reopen original-case verification and strengthen the missed check; fix/retest continues within authorization or reports an exact blocker.
- [x] Preserve invocation policy, inspect package links/metadata, and review the diff for duplicate rules or unnecessary machinery.
- [x] Run existing browser smoke tests, including proof mode and checker rejection cases, and pass applicable repository checks.

## Baseline + execution

Result: Passed
Evidence: `uv run python .hooks/hard-eng.py check --plan-stage Draft` exited 0 before skill edits; all 17 gates passed. Log: `/tmp/he-e2e-baseline.log`.

One builder updates the two entrypoints, existing walkthrough README and its UI metadata to describe both routes. Reuse the bundled Playwright 1.62.1 runtime in a disposable package copy for browser smoke tests; FFmpeg is already installed. No runtime installation needed. Ready-stage native check passed before these edits: `/tmp/he-e2e-ready.log`.

## Risks + recovery

Polished capture changes pacing and can bridge reload paint; it cannot prove raw timing/rendering behavior. Keep those claims on unmodified native capture. Mechanical checks cannot establish product correctness or actual visual inspection. Revert only these skill/document edits if routing regresses.

## ux_reference

N/A — guidance routing changes have no product UI. Browser fixtures verify existing recorder/checker behavior, not a new interface design.

## Verification

Result: Passed
Evidence: Existing `node tests/gesture-smoke.mjs`, `node tests/native-dialog-pointer-smoke.mjs` and `node tests/view-transition-pointer-smoke.mjs` each exited 0 in `/tmp/he-e2e-walkthrough-20260910/package`, using unchanged source scripts and bundled Playwright 1.62.1. Logs: `/tmp/he-e2e-walkthrough-20260910/{gesture,dialog,transition}.log`. Gesture smoke passed full motion assertions, normal and pointer-free recorder/reviewer paths, and rejection of ambiguous keyboard evidence and no-op scrolling. The initial `pnpm test` wrapper aborted dependency preparation; direct script runs avoided installation and supplied the actual passing proof.

Both skills passed the available native quick validator; all 11 local links/anchors resolve. The actual diff preserves explicit-only walkthrough invocation, centralizes defect reopening in E2E, reuses every checker and adds no implementation machinery. Manual route review covered ordinary browser regression, recorded web proof, polished delivery, native-device capture and raw timing claims. This validates routing instructions and existing checker behavior, not automatic host skill selection or a newly approved customer video.

Final `uv run python .hooks/hard-eng.py check --plan-stage Complete` exited 0 with all 17 gates passing; log: `/tmp/he-e2e-complete.log`. `git diff --check` passed. No source commit, push, global install or other-project change was made. Prior root PLAN.md and DECISION.md changes were preserved.

User-requested small sandbox follow-up: `/tmp/he-e2e-sandbox-20260910/check.mjs` exited 0 using a disposable Save preference app and unchanged walkthrough scripts. The same ordinary browser test rejected a visible Saved message without persistence, then passed after the fixture owner was fixed, including reload and localStorage readback. Pointer-free recording passed mechanical checks with status review-required (exit 2), preserving actual visual-review requirements. Removing a checkpoint caused checkpoint-missing/exit 1; restoring it returned zero findings and review-required/exit 2. Conversion rejected the unapproved WebM and created no MP4. Logs: `/tmp/he-e2e-sandbox-20260910/results.log` and `restored.log`; reports remain under `proof-attempt-01`. The final Saved checkpoint was visually inspected. Browser and local server were closed. No regression found in these bounded cases; full MP4 approval/delivery and automatic agent skill selection were not exercised. Source checker/test files remain unchanged relative to HEAD; this follow-up changes only this evidence paragraph.
