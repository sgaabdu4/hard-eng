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

## Exit

Read `references/runbook.md` after the relevant policy references above.
Final output: report path, driver/fallbacks, flow and action totals, artifacts,
fixes, unresolved issues, regression commands, and skipped checks with reasons.
