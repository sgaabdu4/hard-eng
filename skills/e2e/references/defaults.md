# E2E Defaults

Use this when the prompt says to make E2E easy, asks for a full/default flow, or lacks setup detail.

## Default Contract

`auto-full-safe` means:

- infer the app target from repo files, scripts, open servers, and user prompt;
- run the broadest non-destructive UI coverage the current tools can support;
- capture each meaningful click, input, navigation, assertion, error, and fallback;
- leave or reuse a runnable automated E2E command for every checked flow;
- ask only when auth, target, data mode, seeded data, or risky side effects cannot be inferred;
- patch actionable click-time violations within risk limits after evidence identifies a cause;
- finish with impacted E2E reruns plus the smallest existing regression checks

Default scope is dirty tree or requested diff when local changes exist, otherwise full product smoke.
Default data mode is mock or seeded test data.
Production data requires explicit approval and stays read-only unless exact writes are separately approved.
Default risk limit is no prod mutation, no deletes, no payment, no email/SMS, no external sharing, and no DB writes.
Default evidence is desktop+mobile 2x video plus `events.jsonl` when a driver supports it, step screenshots, console/network logs when available, and traces only on retry/failure unless audit mode is requested.
Manual UI operation can help discover a flow, but a passing E2E result needs an automated UI command that an AI can rerun.

## Onboarding Questions

Ask one short block only when missing information blocks a safe run:

```text
I can run `auto-full-safe` by default.
I only need: target URL/start command, auth or test account, data mode (`mock`, `seeded-test`, or `prod-read-only`), and any flows that must not write externally.
```

If the user asks for an onboarding list, use these questions as the product flow inventory:

- What roles should be covered?
- What is the first screen and the expected signed-out state?
- Which happy path creates the most business value?
- Which forms, uploads, filters, search, exports, or payments are highest risk?
- Should this run use mock data, seeded test data, or production data read-only?
- Which clicks cause writes, emails, notifications, payments, deletes, or sharing?
- Which mobile, tablet, desktop, browser, or native-device targets matter?
- Which existing unit, integration, or E2E commands should guard regressions?
- Which screenshots or video moments would prove each feature works to a human reviewer?

## Coverage Matrix

Plan only the axes the app actually has:

- auth gates and role redirects;
- primary happy path;
- form validation, empty/loading/error/offline states;
- navigation, back/forward, deep links, refresh, session expiry;
- permissions, files, camera/location/native dialogs;
- data persistence and cross-screen refresh;
- responsive layout and basic accessibility affordances;
- regression command for existing tests/lint/typecheck/build

Use `full-safe` for normal work, `diff-safe` when a dirty patch should be contained, `audit` when every step needs screenshots/video/traces, and `report-only` when the user forbids changes.
