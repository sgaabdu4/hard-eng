# Shipped skill files pass the focused-tests gate

Status: Complete

## Outcome + scope

Issue 318: the JavaScript `focused-tests` gate (`biome lint --only=suspicious/noFocusedTests --error-on-warnings .`) fails in installed projects on the shipped marketing-video template, because its helper `fit()` matches Biome's Jasmine `fit()` rule. Rename the helper to `fitBox`, and make this repository run the same rule over every shipped skill so the fault cannot return. Non-goals: other Biome rules, skill-source submodules (their copies come from Hard Eng updates).

## Repository context

Owners: `.agents/skills/marketing-video/assets/template/engine.js` (the helper and its two calls); `hard-eng.gates.json` `shared`, beside `shipped-format`, which already lints shipped skills with Biome but did not catch this rule.
Scan: the rule over all 36 tracked JavaScript and TypeScript files outside the skill-source submodules found only the two calls in `engine.js`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked for the rename at the owner, a fix for any other shipped file the gate flags, a check only where shipped files are already proven, a Codex review loop, the canary and a rebase merge.

## Acceptance + steps

- [x] The installed gate command fails on the old template and passes after the rename → Verification.
- [x] `shipped-focused-tests` fails when a file with the old helper sits in `.agents/skills` and passes on the fixed tree → Verification.
- [x] Full `hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: main `12ffb69a` passed the Hard Eng workflow on push.
Execution: One builder on branch `fix/318-template-fit-helper`.

## Risks + recovery

The template keeps the same behavior; only the name changes. Recovery is reverting this branch.

## ux_reference

N/A — template helper name and gate configuration; no product appearance.

## Verification

Result: Passed
Evidence: Biome 2.5.15. The gate command on the old `engine.js` exited 1 with two "Don't focus the test" findings at lines 109 and 112; after the rename it exited 0. The new `shipped-focused-tests` command exited 1 with a copy of the old file placed in `.agents/skills`, and 0 without it. `node --check` passes on the template.
E2E: N/A — no user journey changes; the gate command itself is the proof.
Canary at `a0bf66dd`: 22 of 30 installed projects pass update and full check. `focused-tests` passes in every project that has it, including the root gate that hit the issue. The 8 failures are project tests, types, builds, version and audit gates this change does not touch.
Not checked: rendering a video with the template.

Delivery target: Merge
Delivery: Pending — PR checks, canary and rebase merge.
