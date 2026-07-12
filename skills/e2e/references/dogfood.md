# Dogfood And Artifact Checks

Use this when the user asks to dogfood the E2E flow or prove artifact capture works.

## Dogfood Fixture

Prefer a tiny local web fixture when no product app is safe to mutate.
It should include:

- landing screen, auth-like gate, form, validation error, loading state, success state, navigation, and a blocked destructive action;
- stable data attributes plus visible labels so Browser and Playwright-style drivers can use user-facing locators;
- a seeded failure mode to verify issue capture and rerun behavior;
- no external network writes

When Playwright is available, create a real local artifact run with:

```bash
node <skill-dir>/scripts/dogfood-playwright-smoke.mjs --root <repo>
```

## Artifact Checker

Run:

```bash
node <skill-dir>/scripts/check-e2e-run-artifacts.mjs --run-dir <docs/e2e/RUN_ID>
```

The checker should fail when:

- a checked flow lacks `events.jsonl`;
- an action row lacks status or target evidence;
- desktop or mobile 2x video is expected but absent;
- screenshots are missing for failed steps;
- `report.md` omits driver fallback, unresolved issues, or regression commands

## Dogfood Report

The dogfood report should prove:

- the fixture or target app produced at least one UI action row;
- screenshots plus desktop and mobile 2x videos exist for checked steps;
- blocked destructive actions are recorded without executing them;
- console/log capture ran when available;
- regression commands and remaining gaps are listed
