---
name: product-walkthrough-video
description: Record polished Playwright walkthrough videos of a real web product, then review, approve, and convert them through a hash-bound pipeline. Use when the user asks for a product walkthrough video or e2e video proof of a UI journey.
disable-model-invocation: true
---

# Polished Playwright product walkthroughs

Use this skill when the user wants a complete video of a real web-product journey in any repository.

The task is not complete when a script runs. It is complete only when the exact final MP4 has survived a strict start-to-finish journey check, automated frame review, visual review, hash- and journey-bound uninterrupted real-time playback, source-hash gate, conversion validation, and a second review of the delivered MP4.

## Non-negotiable recording method

- Use Playwright 1.62+ `page.screencast.start()` after the opening state is fully ready.
- Do not use browser-context `recordVideo` for the delivery recording. It starts during page creation and can capture blank or loading frames.
- Use one pointer only: the exact 20px red v17 ring in Playwright's `page.screencast.showOverlay()` plane.
- Do not put the persistent pointer in application DOM. Keep it in Playwright's user-overlay plane. The same-state reload guard may use the prior checkpoint as a transient document-start bitmap in a recorder-owned closed shadow root; it is not an interactive pointer and must be removed after readiness.
- Move Playwright's real mouse with timed intermediate events. `mouse.move({ steps })` alone is not pacing.
- Express canvas and drag-and-drop input with the strict locator-relative `drag` action. Do not replace the runner with custom Playwright code or use unexplained viewport coordinates.
- Use `typeKeys` for one paced text string after a visible action focuses a canvas or keyboard-driven editor. Do not create one held step per character.
- For a same-state full-document reload with an unavoidable bootstrap paint, `preserveVisualDuringReload` may bridge Playwright's post-commit overlay reattachment with the exact prior checkpoint from document start through readiness. Never use it for route changes or to conceal a meaningful product state; the zero-blank navigation audit includes the handoff immediately before navigation.
- Use timed smooth wheel increments. Never use one large wheel event for a product walkthrough.
- Use locators for final actions. Never click stale absolute coordinates.
- Use fixed waits only as presentation holds after a deterministic product-state wait or assertion.

The scripts in this directory implement these rules. Do not replace them with an improvised recorder.

## Required inputs

Determine these by inspecting the repository and the user's request:

- repository path;
- existing command that starts the application;
- local base URL;
- product-specific selector that proves the opening page is ready;
- intended start state;
- complete user journey;
- final state and assertion that proves success;
- stable accessible locator for every interaction;
- explicitly allowed API origins;
- safe seeded fixture, storage state, or test account if authentication is required.

Never record credentials, tokens, real customer data, private payloads, or an uncontrolled production session.

## Phase 1: inspect the repository

Read the package manifest, existing test and preview scripts, routes, application entry points, relevant feature code, existing Playwright tests, fixtures, and seed data.

Build the journey from the real product:

1. Start state.
2. Meaningful user action.
3. Visible product response.
4. Gate or decision.
5. Next action.
6. Final assertion.

Do not invent text, selectors, routes, or product behavior. Prefer role, label, placeholder, test-id, and exact text locators. Use stable CSS only for state markers that have no accessible locator.

## Phase 2: scaffold and configure

```bash
node scripts/scaffold.mjs \
  --repo /absolute/path/to/repository \
  --out /absolute/path/to/repository/.walkthrough \
  --base-url http://127.0.0.1:3000/ \
  --name feature-walkthrough
```

Replace the generated examples. Keep:

- `strictE2E: true`;
- a first `goto` step;
- a product-specific `readySelector`;
- `reducedMotion: "reduce"`;
- `captureStepScreenshots: true`;
- `blockExternalRequests: true`;
- the Playwright screencast pointer;
- `pointer.moveDurationMs` around 700–1000ms;
- `scrollDurationMs` at or above 600ms;
- `dragDurationMs` at or above 600ms for gesture journeys;
- holds at or above `minReadableHoldMs`;
- a final assertion within the final four steps;
- a final pause.

Strict preflight must remain enabled. Do not weaken the gate to make a broken config run.

## Phase 3: establish safety boundaries

Set:

- `allowedOrigins` to the local app and only the APIs needed by the journey;
- `allowedHttpResponses` only for deliberate negative-path responses, matched by exact status and narrow URL substring;
- `blockExternalRequests: true`;
- `blockEventStreams: true` unless an event stream is part of the feature;
- `acceptDownloads: false`;
- an uncommitted `storageState` only when needed.

Use a local safe proxy when an open-source demo references analytics, remote fonts, avatars, or other unrelated third-party assets. Replace those assets locally rather than allowlisting the internet.

An expected failed-auth or validation request must remain visible in evidence. Configure its exact status and a narrow URL substring in `allowedHttpResponses`; the runner records it as `expected-http-response`. If Chromium emits a matching generic console error, allowlist that exact message separately. Never use broad status-only suppression.

Use `textFromEnv` only for a browser-masked password field. A visible field must reject environment text unless `allowVisibleEnvText: true` explicitly marks known non-sensitive fixture copy. Never expose credentials, tokens, customer data, or private payloads in a visible field.

## Phase 4: start and verify the application

Use an existing repository command. Do not modify product code merely to make the recorder pass.

Confirm:

- the base URL returns successfully;
- the configured ready selector becomes visible;
- required local APIs respond;
- the safe fixture is reset;
- no unrelated process owns the expected port.

## Phase 5: record a numbered attempt

Never overwrite a prior attempt.

```bash
node scripts/run-walkthrough.mjs \
  --config /absolute/path/to/repository/.walkthrough/walkthrough.config.json \
  --output-dir /absolute/path/to/repository/.walkthrough/artifacts-attempt-01
```

The recorder must produce:

- `<name>.webm`;
- `<name>-run-report.json`;
- `<name>-timeline.json`;
- `<name>-opening.png`;
- one PNG under `step-checkpoints/` for every step.

The complete run report must include the current skill package name and version. Source review, conversion, and derived MP4 review must preserve that provenance through the run-report hash.

Reject the attempt immediately if the run report is not `passed`, contains an error finding, contains a sensitive finding, or lacks a checkpoint.

## Phase 6: run the unapproved mechanical review

```bash
node scripts/review-video.mjs \
  --video /path/to/artifacts-attempt-01/feature-walkthrough.webm \
  --timeline /path/to/artifacts-attempt-01/feature-walkthrough-run-report.json \
  --output-dir /path/to/artifacts-attempt-01/video-review \
  --report /path/to/artifacts-attempt-01/video-review.json
```

Exit code `2` with `status: "review-required"` is expected only when all automated checks pass. Any `failed` status requires another attempt.

The reviewer enforces:

- complete decode;
- monotonic frame timestamps;
- no blank opening and no single near-white or near-black frame;
- stable opening hold;
- persistent pointer around its expected recorded trajectory;
- no blank, partially styled, or pointerless frame around reloads and full navigations;
- gradual motion across each scroll window, with locator-targeted no-op scrolls rejected;
- gradual locator-bound motion and pointer continuity across each drag window;
- no failed journey step;
- readable holds;
- all checkpoints present;
- a 10fps action sequence for every journey step;
- source-video SHA-256.

## Phase 7: inspect the complete attempt

Do all of the following:

1. Play the WebM from frame one to the end at 1x.
2. Inspect `opening-review-10fps.jpg`.
3. Inspect every `contact-sheet-*.jpg`.
4. Inspect every image under `action-review-10fps/`.
5. Inspect every image under `step-checkpoints/`.
6. Compare every state-changing action with the visible response.
7. Compare the visible journey with the requested start and end states.

Specifically reject:

- any first-frame flash, refresh, blank paint, font swap, layout jump, or duplicated opening;
- pointer disappearance, reset, style change, teleport, duplicate pointer, or inconsistent click cue;
- abrupt, bouncing, reversed, repeated, or unexplained scrolling;
- a click without a visible result;
- a state change without an action or expected response;
- a hidden future stage appearing before its gate;
- a loader that vanishes too quickly to explain waiting;
- a state that is held too briefly to read;
- an unexplained overlay, popup, download, dialog, external page, or broken asset;
- a final frame that does not prove the requested outcome.

Contact sheets do not replace sequential playback. A clean report does not override a visible defect.

## Phase 8: repair and rerun

When anything fails:

1. Identify whether the cause is readiness, locator choice, pointer pacing, scroll timing, fixture state, application state, or journey design.
2. Fix the root cause.
3. Record to `artifacts-attempt-02` or the next unused number.
4. Run the complete mechanical review again.
5. Repeat the full visual review.

Do not approve an attempt and then patch the video. The accepted video must come from a clean real journey.

Continue until both the automated report and complete visual review are clean.

## Phase 9: approve the accepted WebM

```bash
node scripts/review-video.mjs \
  --video /path/to/accepted/feature-walkthrough.webm \
  --timeline /path/to/accepted/feature-walkthrough-run-report.json \
  --output-dir /path/to/accepted/video-review \
  --report /path/to/accepted/video-review.json \
  --approve \
  --reviewer "Copilot" \
  --notes "Watched the complete video at 1x and inspected the opening sheet, all contact sheets, every checkpoint, all navigations, pointer continuity, and smooth scrolls."
```

Approval must name the reviewer and state what was inspected. Never copy approval from another attempt.

The approval command must itself play the exact current file from zero through `ended` in Chromium at 1x. It rejects pauses, buffering stalls, seeking, playback-rate changes, non-monotonic media time, sampling gaps, wall-clock drift, early completion, and media errors. It binds schema-v2 `playbackEvidence` to the video hash, dimensions, duration, and complete run-report SHA-256. The command therefore takes approximately the video's full duration; approval notes alone can never satisfy this gate.

## Phase 10: convert through the hash gate

```bash
node scripts/convert-mp4.mjs \
  --input /path/to/accepted/feature-walkthrough.webm \
  --review /path/to/accepted/video-review.json \
  --output /absolute/path/to/Downloads/feature-walkthrough.mp4
```

Conversion must fail when the WebM hash differs from the approved report, the report lacks passed schema-v2 playback evidence, the proof does not match the video metadata, or the review is not bound to a complete run-report hash. The converter must produce a delivery manifest and validate H.264, yuv420p, dimensions, duration, full decode, and fast-start delivery settings.

## Phase 11: review the final MP4

Run the reviewer against the MP4 with a distinct output directory and report. Bind it to the accepted source review:

```bash
node scripts/review-video.mjs \
  --video /absolute/path/to/Downloads/feature-walkthrough.mp4 \
  --timeline /path/to/accepted/feature-walkthrough-run-report.json \
  --derived-from /path/to/accepted/video-review.json \
  --output-dir /absolute/path/to/Downloads/feature-walkthrough-mp4-review \
  --report /absolute/path/to/Downloads/feature-walkthrough-mp4-review.json
```

Repeat the complete 1x playback and visual inspection, inspect the MP4's generated sheets, then rerun with `--approve`, `--reviewer`, and descriptive `--notes`. This produces a separate MP4 playback proof; source evidence cannot be reused. The derived review must use the same complete run report as the source approval. Never reuse the WebM report path for the MP4.

Open the delivered MP4 through a fresh preview URL with a new cache-busting query or a new browser panel. Verify the displayed duration and first frame match the current file.

Do not rely on a previously opened preview.

## Completion gate

Do not report completion until all conditions are true:

1. The accepted run report is `passed`.
2. No runtime, safety, network, or sensitive-data error exists.
3. Recording began after the real opening state was ready.
4. Every frame decoded with monotonic timestamps.
5. Opening stability, pointer continuity, smooth-scroll, pacing, blank-frame, and journey checks passed.
6. Every step checkpoint exists and was inspected.
7. The complete WebM was watched and approved with passed, hash-bound real-time playback evidence.
8. The MP4 was generated from the exact approved WebM hash.
9. The complete MP4 was watched and approved separately with its own passed playback evidence.
10. A fresh preview displays that exact MP4.

If the user finds a defect, the prior approval is invalid. Reopen the task, reproduce the issue, improve the enforcement that missed it, and create a new attempt.
