# Browser First Driver Policy

Use this before selecting UI automation.

## Driver Choice

- Local or public web app: use Codex Browser first when the in-app Browser tools are callable
- Signed-in browser state, cookies, extensions, or existing user profile: use the Chrome extension/browser plugin when available
- Existing project E2E runner: use it as regression proof after exploratory Browser/device evidence, or as the primary runner when Browser is unavailable
- Flutter/mobile/native dialogs: use the repo's Flutter device tooling, `integration_test`, Patrol, or configured device runner
- Standalone Playwright: use when Browser is unavailable, the repo already owns Playwright tests, or the user asks for durable CI tests
- Computer Use: use as an E2E-owned fallback only when the tool is exposed/available, or when the user explicitly asks for it and the target is desktop/native; keep it target-app scoped and non-destructive unless exact side effects are approved

## Browser Availability

Before saying Browser is unavailable, read the Browser skill if it is listed and bootstrap its `browser-client` through `node_repl`.
If the Browser plugin or `browser-client` path is missing, record that exact missing capability in the run report and continue to Playwright or Computer Use.

## Playwright Availability

Before saying Playwright is unavailable, run:

```bash
node <skill-dir>/scripts/ensure-playwright.mjs
```

If Browser is unavailable and Playwright is justified but missing, provision it into the user cache unless the prompt forbids installs:

```bash
node <skill-dir>/scripts/ensure-playwright.mjs --install --with-browser chromium
```

## Runtime Preflight

Before treating Node, npm, or native bindings as an E2E blocker, run:

```bash
node <skill-dir>/scripts/check-ui-runtime.mjs --root <repo> --native-module better-sqlite3
```

Use the report to pin the command runtime, override `npm_config_ignore_scripts=false` for the repair command only, or switch to a working installed Node.
Do this before downgrading visual proof to server-rendered HTML or static checks.

## Profile Lock Recovery

A Browser or Playwright error that says `Browser is already in use`, `profile is locked`, `mcp-chrome`, or `use --isolated` means the shared automation profile is locked, not that the target UI failed.
Retry once with an isolated browser profile before applying the failure stop.
This profile-lock error alone is not enough to mark E2E blocked or switch to
local scripts, static inspection, or artifact checks.

Use the Browser tool's isolated mode when it is exposed.
If the Browser tool has no isolated option, standalone Playwright with a fresh temporary `userDataDir` is allowed for this recovery only.
Record the original lock error, the isolated-profile driver, and artifact paths in `events.jsonl` and the final report.

Do not delete the locked profile, kill browser processes, open desktop apps, or use `computer-use` to clear the lock.
If the isolated retry fails or is denied, stop that browser profile and continue to standalone Playwright, project runner, device tooling, or Computer Use when exposed.

## Failure Handling

If Browser or `node_repl` probing fails or is denied after any allowed profile-lock recovery, stop that driver and continue to the next E2E-owned fallback: standalone Playwright, project runner, device tooling, or Computer Use when exposed.
Do not jump directly from one Browser or `node_repl` probe failure to Computer Use. Try or explicitly rule out standalone Playwright, the project runner, and relevant device tooling first. Use Computer Use only when those are unavailable/denied, the target is explicitly desktop/native, or the user explicitly asks for it; record why it is target-app scoped rather than random desktop automation.
If Computer Use is also unavailable or denied, do not classify it as a fallback; record the visual-proof blocker and use local scripts, existing tests, static inspection, and artifact checks only as support evidence.
Do not use `open -a`, `osascript`, or unrelated UI channels.
If standalone Playwright fails because of Node, npm, or native bindings, run the runtime preflight before treating it as a blocker.
A Browser or `node_repl` probe failure stops only that driver. It does not mean all UI proof is unavailable, and it is not enough to switch to local scripts, static inspection, or artifact checks.
Use local scripts, existing tests, static inspection, and artifact checks only after every safe UI driver is unavailable, then report exactly which UI proof could not be collected.

## Playwright Last Resort Shape

When standalone Playwright is justified:

- use user-facing locators and web-first assertions;
- record trace on first retry/failure rather than every pass by default;
- retain screenshots/video on failure, or for every step only in audit mode;
- avoid hard waits except for external systems without observable state;
- keep generated tests as small vertical flows, not one giant tour

## Browser Run Shape

Browser-first runs should still emit the same artifact ledger as other drivers:

- action id, timestamp, URL, locator or coordinates, action kind, and result;
- screenshot path or video timestamp after every verified step;
- console/network errors when the tool exposes them;
- fallback reason when switching to local tests or Playwright
