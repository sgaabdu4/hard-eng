# Starter speed tests ignore one slow run on a busy runner

Status: Complete

## Outcome + scope

The Flutter and Python starter speed tests time 5 runs and check the fastest against the same budget, so a pause on a shared CI runner does not fail a new project. Non-goals: changing the budgets, the bundle-size tests of the JavaScript starters.

## Repository context

Owners: `.agents/starters/flutter/test/performance/counter_notifier_performance_test.dart`, `.agents/starters/python/tests/performance/test_greeting_performance.py`.
Same cause: Canary job `new project (scaffold-flutter, macos-latest)` on develop e4cd000 failed with 304 ms against the 250 ms budget; the same job passed on PR #408 a few minutes before with the same Flutter files. The Python starter times one run the same way, so it gets the same fix. The Next.js, OpenNext and Vite starters check bundle size, not time, so they cannot fail this way.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid asked on 2026-10-26 whether anything is left to do; standing approval to fix and merge into develop.

## Acceptance + steps

- [x] The Python starter speed test passes with the fastest of 5 runs and still fails over budget → `.agents/starters/python/tests/performance/test_greeting_performance.py::test_greeting_builds_100k_messages_within_budget` passed; with the budget set to 0.000001 s it failed.
- [x] The Flutter starter speed test passes on both Canary runners → N/A — no Dart or Flutter SDK in the cloud container; this PR's Canary jobs `new project (scaffold-flutter, ubuntu-latest)` and `(scaffold-flutter, macos-latest)` run it.

## Baseline + execution

Result: Passed
Evidence: develop e4cd000 `hard-eng` passed; its Canary failed only in the Flutter macOS speed test (304 ms, budget 250 ms), the failure this plan fixes.
Execution: One builder, this session.

## Risks + recovery

A real slowdown hidden in 4 of 5 runs passes. The fastest run still has to meet the same budget, so a slower build still fails.

## ux_reference

N/A — test code only; no visible UI.

## Verification

Result: Passed
Evidence: Python starter test passed, and failed with a 0.000001 s budget. `check --plan-stage Complete --base origin/develop`: every gate passed except 6 Dart/Swift tests that need `dart` and `swiftc`, which this cloud container lacks; CI has both.
E2E: N/A — the Canary new-project jobs run each starter's gates on real runners.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR, including both Flutter jobs.
