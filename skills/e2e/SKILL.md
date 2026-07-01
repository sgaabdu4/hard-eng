---
name: e2e
description: Use for real UI E2E smoke/regression proof across web, Flutter, browser, Chrome, or device flows, with artifacts.
---

# E2E

Run real UI only. Unit tests, typechecks, static scans, and `curl` can support the run, but never count as E2E proof.
Default to `auto-full-safe`: infer the target, run the fullest non-destructive coverage, capture proof, and ask only for missing auth, target, data mode, or risky side effects.

## Load

Read the focused reference that matches the task:

- `references/defaults.md` for underspecified runs, onboarding questions, scope, and regression gates
- `references/project-pack.md` before the first run in a repo, and before reusing saved auth/flows/log commands
- `references/browser-first.md` before choosing Browser, Chrome, device tooling, or standalone Playwright
- `references/capture-artifacts.md` before running/delegating flows or judging evidence
- `references/runbook.md` for plans, runner prompts, triage, fixes, and final reports
- `references/dogfood.md` for dogfood fixtures and artifact checks

## Rules

- Use Codex Browser first for local/public web when callable; use Chrome extension for signed-in browser state when available; use Flutter/device tooling for native flows; standalone Playwright is last resort or CI artifact work
- Stop only the failed UI driver after one denied/non-profile-lock probe; continue through `references/browser-first.md` fallbacks before accepting missing visual evidence
- Use Computer Use only when the tool is exposed/available or the user explicitly asks for it; if Computer Use is unavailable or denied, record the visual-proof blocker and use local support evidence without counting it as E2E proof
- Before first-run setup or saved auth/flow reuse, check the project pack when the helper script is available; saved auth reuse still needs an automated E2E command
- Never mark resolved from screenshots alone; reproduce, patch only after cause/ripple checks, and rerun impacted E2E plus regression checks
- In auto mode, fix actionable click-time violations within risk limits, rerun that step/flow, and continue; stop only for unsafe side effects or unclear ownership
- Every checked action needs UI evidence: action event, settled assertion, screenshot or video frame, and artifact path
- Every checked flow must use or leave a runnable automated E2E command; manual-only runs are incomplete
- Confirm data mode before running flows when it is unknown: mock/seeded test data is default; prod data requires explicit approval and must be read-only unless exact writes are separately approved
- No prod writes/deletes, email/SMS, payments, or sharing unless explicitly approved
- Browser/E2E failure or denied action gets one retry or one fallback path; if the same blocker repeats, stop and ask with blocker category, choices, and a recommendation
- Real credentials, generated users/passwords, native permission prompts, prod/backend writes, backend permission/schema/index/migration/webhook changes, production payment/email/SMS/sharing side effects, and prod cleanup are approval boundaries; record `approvalBoundaries[]` with `id`, `category`, `status`, `reason`, non-empty `evidence[]`, exact `sideEffectKey` when side effects differ, `redactedCredentialRef` and `dataScope` for credentials, and positive `cleanupProof[]` for generated credentials
- Do not exercise an outdated UI when a known UI/component SSOT issue is unresolved; route back to `/he:implement`
- UI E2E requires desktop and mobile 2x video artifacts so exact appearance is reviewable; native phone counts as mobile
- Capture by default: `events.jsonl`, desktop+mobile cursor/click videos, step screenshots, supported logs/traces, and desktop+mobile 2x cursor recaps. If video is blocked after driver fallbacks, report it as an artifact limit instead of a clean pass
- Artifacts go under `docs/e2e/<RUN_ID>/`; never overwrite prior runs and never count zero UI calls as a pass
- Keep plans short; split flows across agents only when independent

## Runbook

Read `references/runbook.md` after the relevant policy references above.

## Exit

Final output: report path, driver used/fallbacks, flow/step/action totals, artifact links, fixes, unresolved issues, regression commands, skipped checks and why.
