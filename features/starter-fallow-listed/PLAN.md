# Starters list the fallow package their boundaries script runs

Status: Complete

## Outcome + scope

The vite, nextjs and opennext starters add a `lint:boundaries` script that runs `fallow`, but do not list the `fallow` package. fallow 3.40.0 reports that as an unlisted binary, so the dead-code gate fails on a new project before any change. Now each starter lists `fallow` as a dev package, and the new-project upgrade pins it like every other package. Non-goals: existing projects (each fixes its own manifest or gate), other starters.

## Repository context

Owners: `.agents/starters/{vite,nextjs,opennext}/package.json` (starter scripts and packages).
Same cause: the starters relied on the gate's own fallow install, which the newest fallow no longer accepts for a package script.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid's standing rule to fix problems found mid-task in the same session; found on 2026-11-07 while repairing project gates; merge after green checks.
Decision: list the package, so each starter keeps its own `fallow architecture` flags.

## Acceptance + steps

- [x] A new vite project lists `fallow` as a dev package → `tests/test_new_project.py::test_vite_starter_replaces_oxlint_and_pins_after_the_scaffold`.
- [x] The nextjs and opennext starters list `fallow` beside their boundaries script → N/A — same starter data shape; proven by the dead-code gate on a project made from them, not a separate test.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after the last release; the new assertion failed before the change.
Execution: one session; failing assertion first, the starter edits, the full check, PR, release.

## Risks + recovery

A new project installs one more dev package. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete --base origin/develop` result recorded in the pull request.
E2E: N/A — no user journey; the new-project test runs the real starter merge.
Delivery target: PR
Delivery: Pending — PR into develop.
