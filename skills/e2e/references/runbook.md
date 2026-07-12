# E2E Runbook

Read `defaults.md`, `browser-first.md`, and `capture-artifacts.md` before using this runbook when the prompt is underspecified or tool choice is open.

## Execution Rules

- Use Codex Browser first for local/public web when callable; use Chrome
  extension for signed-in browser state when available; use Flutter/device
  tooling for native flows; standalone Playwright is last resort or CI artifact
  work.
- Stop only the failed UI driver after one denied/non-profile-lock probe; follow
  `browser-first.md` fallbacks before accepting missing visual evidence.
- Use Computer Use only when exposed/available or explicitly requested; if it is
  unavailable or denied, record the visual-proof blocker and use local support
  evidence without counting it as E2E proof.
- Before first-run setup or saved auth/flow reuse, check the project pack when
  the helper script is available. Saved auth reuse still needs an automated E2E
  command.
- Never mark resolved from screenshots alone. Reproduce, patch after
  cause/ripple checks, and rerun impacted E2E plus regression checks.
- In auto mode, fix actionable click-time violations within risk limits, rerun
  that step or flow, and continue. Stop only for unsafe side effects or unclear
  ownership.
- Every checked action needs UI evidence: action event, settled assertion,
  screenshot or video frame, and artifact path.
- Every checked flow must use or leave a runnable automated E2E command
  Manual-only runs are incomplete.
- Confirm unknown data mode before running flows. Mock/seeded test data is
  default; production data requires explicit approval and must be read-only
  unless exact writes are separately approved.
- No production writes, deletes, emails/SMS, payments, or sharing unless
  explicitly approved.
- Browser/E2E failure or denied action gets one retry or one fallback path. If
  the same blocker repeats, stop and ask with blocker category, choices, and a
  recommendation.
- For credentials, native prompts, prod/backend writes, payment/email/SMS or
  sharing side effects, cleanup, schema/index/migration/webhook changes, read
  `approval-boundaries.md` and record matching `approvalBoundaries[]`.
- Do not exercise an outdated UI while a known UI/component SSOT issue is
  unresolved; return to the current Hard Eng Build slice.
- UI E2E requires desktop and mobile 2x video artifacts when the driver
  supports video. Native phone counts as mobile.
- Artifacts go under `docs/e2e/<RUN_ID>/`; never overwrite prior runs and never
  count zero UI calls as a pass.
- Keep plans short. Split flows across agents only when independent

## Artifacts

```text
docs/e2e/<RUN_ID>/
  state.json
  plans/INDEX.md
  plans/<flow>.md
  events.jsonl
  issues.md
  screenshots/<flow>/<profile>/<step>_<status>.png
  videos/<flow>_<desktop|mobile>.mp4
  recaps/<flow>_<desktop|mobile>_2x_cursor.mp4
  traces/<flow>.zip
  logs/<flow>.log
  regression.md
  report.md
```

`state.json` tracks run id, scope, stack, mode, fix policy, capture policy, risk limits, desktop/mobile targets, device/url/session/process ids, driver choice, fallback reason, flow statuses, UI action counts, artifact counts, and retry counts.
`events.jsonl` records every click, input, navigation, wait, assertion, issue, fallback, and fix verification.

## Setup

1. Create `RUN_ID=${PI_SESSION_ID:-$(date -u +%Y%m%dT%H%M%SZ)}`.
2. Make artifact dirs.
3. Index/map code with CBM first.
4. Detect stack from target plus `pubspec.yaml`/`package.json`.
5. Choose driver from `browser-first.md`.
6. Boot app: reuse supplied URL/server when live; otherwise start a dev server and store its process id.
7. Record capture policy: default, audit, or report-only.

## Discovery

- `full`: graph routes/screens/views; prioritize auth, checkout/payment, settings/account, write-heavy flows, recent incidents
- `diff`: changed files/symbols -> inbound dependency trace depth 4 -> impacted screens/routes
- specific target: one rooted flow plus downstream screens/actions

## Plan Template

Each flow plan should be 5-12 steps. Include only relevant axes:

- happy path
- inputs and validation
- loading/empty/error/offline state
- navigation/deep links/auth gates
- concurrency/network/timeout/session expiry
- permissions/roles

Use `[ ]`, `[x]`, and `[~] (n/a/spec: reason)`.
Each checked step must name the expected event row and artifact path.

## Runner Prompt

```text
Run E2E flow <flow>.
plan-file: <ARTIFACTS>/plans/<flow>.md
issues-file: <ARTIFACTS>/issues.md
screenshot-dir: <ARTIFACTS>/screenshots/<flow>/
capture-policy: <default|audit|report-only>
events-file: <ARTIFACTS>/events.jsonl
video-paths: <ARTIFACTS>/videos/<flow>_desktop.mp4, <ARTIFACTS>/videos/<flow>_mobile.mp4
run-id: <RUN_ID>
device-id/dev-url/session-name: <value>
risk-limits: <limits>

Drive real UI only. Per step: action -> settle -> verify -> event row -> screenshot/video timestamp.
At flow end, produce desktop and mobile 2x cursor/click recap videos when video is supported.
Tick [x] only with UI evidence. On FAIL, append issue; in auto mode return for fix/rerun before continuing, and in guided/report-only mode halt. Return <=150 words: status, action count, event count, artifacts, and fallback reason if any.
```

## Issue Block

Append atomically:

```md
## <flow>/<step> - <RUN_ID>
Step: <plan line>
Repro: <minimal sequence>
File hint: <screen/component:line via trace>
Logs: <short decisive lines>
Evidence: screenshot/video/log/trace/event paths
UI actions so far: <N>
Category: regression | spec-gap | flake | tooling
Proposed fix: <one line>
Regression: <command/result or pending>
- [ ] resolved
```

## Triage

- Regression: app error/log/stack or changed file involvement
- Spec-gap: expected UI absent and no app error
- Flake: timing/network; one retry passes without code

Guided mode asks before category/fix. Auto mode uses the heuristic; for click-time violations, patch actionable regressions within risk limits, rerun the failing step/flow, then continue. Mark spec gaps, retry flakes once, then escalate after 3 failed loops.
After any fix, rerun the impacted flow and the smallest existing regression command that could catch the breakage.

## Report

Include status, driver used and fallback chain, totals, per-flow summary, UI action audit, fixes, risk controls, artifact paths, desktop/mobile 2x cursor recap paths or fallback reasons, regression commands and results, skipped checks, and cleanup result.
Any flow with zero UI calls makes the run invalid unless the report clearly marks UI proof blocked by tool failure.
Run `scripts/check-e2e-run-artifacts.mjs --run-dir <docs/e2e/RUN_ID>` before marking the report complete.
