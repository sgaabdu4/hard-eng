# Project Pack

Use this before the first E2E run in a repo and before reusing saved auth, flows, or log commands.

## Purpose

Persist the boring first-run knowledge in the project so future E2E checks start from known safe defaults instead of rediscovering login, target URLs, critical flows, and logs.

## Files

```text
docs/e2e/
  project.json
  auth.md
  automation.md
  logging.md
  regression.md
  issues.md
  flows/README.md
```

`project.json` is the index.
Markdown files hold human-readable setup, safe test data, flow notes, and commands.
Do not store passwords, tokens, cookies, private session dumps, or real customer data.

## Automation Rule

Every E2E flow should be automated before the run is called complete.
Manual Browser, Chrome, Playwright, device, or Computer Use exploration can discover selectors and validate the first run, but the verified flow must be persisted as a runnable command in the repo's E2E runner or in `docs/e2e/project.json`.
If automation cannot be created in the current environment, mark the E2E result incomplete, record the blocker, and do not count it as a passing automated E2E test.
The project pack check must confirm `automation.commands` and each flow's `automationCommand` before reusing saved auth, flows, or regression commands.

## First Run

First-run setup is itself part of E2E.
It is incomplete until the initial login and any persisted main flows have runnable automated commands.

Run:

```bash
node <skill-dir>/scripts/scaffold-e2e-project.mjs --root <repo>
node <skill-dir>/scripts/check-e2e-project.mjs --root <repo>
```

Then fill only what the current run can verify:

- target URL or start command;
- data mode: `mock`, `seeded-test`, `prod-read-only`, or `prod-approved-write`;
- login method and test account owner, without secrets;
- reusable authenticated-state path when safe and intentionally saved;
- critical flows, especially login, primary happy path, settings/account, and write-heavy areas;
- runnable automated E2E commands for every persisted flow;
- console/server/network log commands;
- regression commands that should run after E2E fixes

## Reuse Rule

Every later E2E run checks `docs/e2e/project.json` first.
If the pack exists, reuse known target, auth notes, flows, log commands, and regression commands before asking the user.
If the pack is incomplete, update it from verified facts only and mark unknowns plainly.
Before reusing saved auth state, the project pack check is mandatory.

## Auth State

Saved auth state is allowed only as a path reference to a safe local artifact.
The repo pack may say where state is expected, but it must not commit raw cookies, tokens, or credentials.
Reusing saved auth state still requires a runnable automated E2E command; it is a setup input for automation, not manual proof.

## Data Mode

Persist the intended data mode in `project.json`.
Use `mock` or `seeded-test` by default.
Use `prod-read-only` only with explicit user approval.
Use `prod-approved-write` only when the user approves exact write actions, target environment, account/tenant, and rollback or cleanup plan.

## Logs

Capture logs for each run when available:

- browser console and network errors;
- dev server output;
- mobile/device logs;
- existing test runner output;
- app-specific audit/event logs when safe

The final report must say which logs were captured and which were unavailable.
