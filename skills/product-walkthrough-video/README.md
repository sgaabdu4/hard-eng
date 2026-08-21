# Playwright walkthrough skill

A strict recording, review, and delivery pipeline for polished product walkthroughs. Version 2.7 starts recording only after the real page is ready, keeps one Playwright-owned pointer across drag gestures and navigations, bridges the new-document reload seam before first paint, rejects single-frame blanks and no-op scrolls, supports paced keyboard-driven canvas text, records intentional negative-path HTTP evidence, captures every journey checkpoint, scans every video frame, and blocks approval until the exact file completes an uninterrupted, no-seek 1x Chromium playback.

## What version 2.7 fixes

| Previous failure | Enforced fix |
| --- | --- |
| Blank or flashing opening frames | `page.screencast.start()` begins only after navigation, the product ready marker, fonts, visible images, and layout stability |
| Pointer disappears or resets on a new document | The exact v17 ring is rendered through Playwright's persistent screencast overlay plane, not inside application DOM |
| Pointer jumps too quickly to see | Real Playwright mouse events are paced over 900ms by default; `steps` adds intermediate events but does not control elapsed time |
| Scroll jumps, “dances,” or does nothing | Wheel input is split across timed, eased increments; the reviewer rejects both non-smooth motion and a locator-targeted no-op |
| Canvas or drag-and-drop journeys require custom Playwright code | A strict `drag` action uses locator-relative start/end points, paced real mouse input, a pressed persistent pointer, and a frame-level gesture audit |
| Canvas clicks depend on stale screen coordinates | `click` and `hover` accept positions relative to a stable target box, never unexplained viewport coordinates |
| Keyboard-driven canvas text requires one held step per character | `typeKeys` sends one paced string to the focused editor and produces one action sheet/checkpoint |
| Playwright reapplies overlays one frame after a new document commits | `preserveVisualDuringReload` prewarms the exact checkpoint in Playwright's overlay plane and installs a one-shot, recorder-owned closed-shadow snapshot at document start, then removes both only after readiness |
| A run passes despite a bad journey | Strict preflight requires a real ready selector, readable holds, smooth scroll timing, and a final assertion |
| Contact sheets miss fast defects | The reviewer scans every frame, creates 2fps contact sheets, and creates a separate 10fps opening sheet |
| Fast actions are hard to inspect | The reviewer creates a 10fps action sequence for every journey step |
| A one-frame flash slips below the old duration threshold | Every near-white or near-black frame is rejected, and guarded navigation review includes the compositor handoff immediately before the recorded reload interval |
| Pointer review is subjective | The run records its pointer trajectory; the reviewer checks the expected ring around that position in every frame |
| A visible moving pointer fails when overlay timing drifts under load | Moving-frame detection validates the ring along its recorded path corridor; stationary checks remain position-exact |
| An agent can claim playback it did not perform | Every approval command plays the exact hash-matched file from zero through `ended` at 1x and records wall-clock, media-time, interruption, seek, rate-change, and browser evidence |
| Playback proof can be copied to another file or journey | Every proof is bound to the video hash, dimensions, duration, and SHA-256 of the complete run report |
| A report cannot prove which runner produced it | The run report records the skill package name/version; source review, derived review, and conversion manifest preserve that hash-bound provenance |
| Intentional failed-auth/API flows look like unexplained HTTP warnings | `allowedHttpResponses` requires an exact status and URL substring, records the event as informational evidence, and leaves every unmatched 4xx/5xx visible |
| An unreviewed file is converted | MP4 conversion requires a passed review whose SHA-256 matches the source WebM |
| Conversion is treated as final | The generated MP4 must pass the same complete review again |

## Setup

```bash
cd skills/product-walkthrough-video
npm ci --ignore-scripts
npx playwright install chromium
brew install ffmpeg
```

On Linux, install FFmpeg with `sudo apt-get install -y ffmpeg` instead of Homebrew.

The skill is pinned to Playwright 1.62.1, which provides `page.screencast`, persistent user overlays, and exact recording start/stop control.

## Complete workflow

### 1. Scaffold the repository journey

```bash
node scripts/scaffold.mjs \
  --repo /absolute/path/to/repository \
  --out /absolute/path/to/repository/.walkthrough \
  --base-url http://127.0.0.1:3000/ \
  --name checkout-walkthrough
```

Keep `.walkthrough` ignored or uncommitted.

### 2. Author the real end-to-end flow

Replace the scaffold examples. A strict journey must have:

1. A first `goto` step that defines the start state.
2. A product-specific `readySelector`; `body`, `html`, and `*` are rejected.
3. Stable accessible targets.
4. Holds at or above `minReadableHoldMs`.
5. Scroll durations of at least 600ms.
6. A final assertion within the last four steps.
7. A final pause that lets the viewer read the proven end state.
8. `blockExternalRequests: true`; use a local fixture or proxy for unrelated third-party assets.

Example:

```json
{
  "action": "click",
  "label": "Approve the product brief",
  "target": {
    "role": "button",
    "name": "Approve brief",
    "exact": true
  },
  "readySelector": "[data-stage='research'][data-status='ready']",
  "holdMs": 1500
}
```

Prefer role, label, placeholder, test-id, and exact text targets. CSS selectors are acceptable for stable product states. Never use generated class chains or coordinates as the target.

Supported actions:

| Action | Purpose |
| --- | --- |
| `goto` | Open a path or URL |
| `click` | Move visibly, check actionability, then click a locator |
| `drag` | Drag between stable locator-relative points with paced real mouse input |
| `type` | Focus, clear, and type with `pressSequentially` |
| `typeKeys` | Type paced text into the currently focused keyboard-driven surface |
| `select` | Select a native option |
| `press` | Press a key |
| `hover` | Move the real pointer over a locator |
| `scroll` | Perform a timed smooth wheel scroll or reveal a target smoothly |
| `waitForSelector` / `waitForText` / `waitForUrl` | Wait for explicit application readiness |
| `assertVisible` / `assertText` / `assertUrl` | Prove journey outcomes |
| `pause` | Presentation hold only |
| `screenshot` | Capture an extra named state |
| `reload` / `back` / `forward` | Exercise browser navigation |

Use `textFromEnv` for sensitive input only when the target is a browser-masked password field. Visible fields reject environment text unless `allowVisibleEnvText: true` explicitly marks known non-sensitive fixture copy. Never place credentials, tokens, customer data, or private payloads in the JSON file or a visible field.

Use `typeKeys` only when a canvas or keyboard-driven editor has already established focus through a visible preceding action. It sends paced real keyboard events as one reviewable step. Do not split a word into separate `press` steps, and do not use environment text unless `allowVisibleEnvText` marks known non-sensitive fixture copy.

Canvas clicks and drags must remain anchored to a stable locator. Use ratios when the surface scales:

```json
{
  "action": "drag",
  "label": "Draw the selected shape",
  "target": { "selector": "[data-testid='canvas']" },
  "from": { "xRatio": 0.2, "yRatio": 0.35 },
  "to": { "xRatio": 0.65, "yRatio": 0.7 },
  "durationMs": 900,
  "holdMs": 1400
}
```

`from`, `to`, and optional click `position` values may use `xRatio`/`yRatio` between 0 and 1 or non-negative `x`/`y` pixel offsets within the target. A drag may instead provide `toTarget` and omit `to` to use that target's center. Strict mode rejects drags shorter than 600ms, destinations outside stable target bounds, and motion that does not survive the frame-level gesture audit.

For a full-document reload that is expected to return to the same visual state, set `"preserveVisualDuringReload": true` on that reload step. The runner reuses the previous required checkpoint, prewarms it in Playwright's user-overlay plane, and installs the same bitmap through a one-shot document-start host with a closed shadow root. This narrow bridge exists because Playwright 1.62 reapplies user overlays only after the new document commits. It is recorder-owned, pointer-events-free, outside the application's component tree, and removed after the new document passes the complete readiness contract. The normal zero-blank, zero-pointer-loss audit includes the compositor handoff and real `page.reload()` interval. Never use this on a route change or to hide a meaningful loading state.

### 3. Start the application

Use the repository's existing development or preview command. Confirm the configured local URL and required API origins are available.

### 4. Record

```bash
node scripts/run-walkthrough.mjs \
  --config /absolute/path/to/repository/.walkthrough/walkthrough.config.json \
  --output-dir /absolute/path/to/repository/.walkthrough/artifacts-attempt-01
```

The runner:

- validates the complete journey before opening Chromium;
- blocks unexpected origins, event streams, downloads, popups, dialogs, and file choosers;
- waits for the real product readiness contract, fonts, visible image decoding, and stable layout;
- installs the exact 20px red v17 ring in Playwright's screencast overlay plane;
- starts `page.screencast` only after the opening page is fully rendered;
- moves Playwright's real mouse on a readable timed path;
- performs smooth wheel input rather than one abrupt scroll event;
- performs locator-bound, visibly paced mouse drags without custom recorder code;
- checks target actionability and position immediately before clicking;
- captures one PNG checkpoint after every step;
- records step times and the pointer trajectory;
- writes a WebM, run report, timeline, opening frame, and checkpoint directory.
- records the exact skill package name and version in the hash-bound run report.

Readiness waits are based on product state. Fixed waits are used only for viewer pacing.

### 5. Run the independent review

```bash
node scripts/review-video.mjs \
  --video /path/to/artifacts-attempt-01/checkout-walkthrough.webm \
  --timeline /path/to/artifacts-attempt-01/checkout-walkthrough-run-report.json \
  --output-dir /path/to/artifacts-attempt-01/video-review \
  --report /path/to/artifacts-attempt-01/video-review.json
```

An otherwise clean first review exits with code `2` and `status: "review-required"`. It does not approve itself.

Automated checks cover:

- full decode and frame count;
- monotonic presentation timestamps;
- dimensions, duration, and SHA-256, with codec and pixel format reported for inspection;
- near-white and near-black frame runs;
- flashing or layout changes during the opening hold;
- long runs without page or pointer motion;
- abrupt transitions;
- the expected pointer around its recorded position in every frame;
- full-navigation windows with no reload flash, intermediate paint, or pointer loss;
- smooth scroll duration and motion across multiple frames, with no no-op scroll accepted as a gesture;
- smooth drag duration, distance, active-frame motion, and pointer continuity;
- failed steps and unreadable holds;
- one existing checkpoint for every journey step;
- a 10fps action sequence for every journey step.

### 6. Inspect, reject, and rerun

Watch the complete WebM at 1x from the first frame through the end. Inspect:

- `opening-review-10fps.jpg`;
- every `contact-sheet-*.jpg`;
- every image under `action-review-10fps/`;
- every image under `step-checkpoints/`;
- every state-changing action at full speed.

Reject the attempt if anything flashes, jumps, refreshes, resets, disappears, changes without cause, moves too quickly, pauses too briefly, or fails to prove the final outcome. Fix the config, timing, fixture, or application state and record to a new attempt directory. Do not overwrite or approve a flawed attempt.

### 7. Approve the clean WebM

After the full review:

```bash
node scripts/review-video.mjs \
  --video /path/to/artifacts-attempt-02/checkout-walkthrough.webm \
  --timeline /path/to/artifacts-attempt-02/checkout-walkthrough-run-report.json \
  --output-dir /path/to/artifacts-attempt-02/video-review \
  --report /path/to/artifacts-attempt-02/video-review.json \
  --approve \
  --reviewer "Copilot" \
  --notes "Watched the complete video at 1x and inspected the opening sheet, all contact sheets, checkpoints, navigations, pointer continuity, and smooth scrolls."
```

Approval fails without a reviewer and descriptive review notes.

`--approve` also runs a mandatory local Chromium playback of that exact video. It starts at zero, locks playback to 1x, rejects pauses, buffering stalls, seeking, rate changes, non-monotonic media time, sampling gaps, and wall-clock drift, then requires the `ended` event with no media error. The report binds `playbackEvidence` to the video hash, dimensions, duration, and complete run-report hash. Expect the command to take approximately as long as the video.

### 8. Convert only the approved source

```bash
node scripts/convert-mp4.mjs \
  --input /path/to/artifacts-attempt-02/checkout-walkthrough.webm \
  --review /path/to/artifacts-attempt-02/video-review.json \
  --output ~/Downloads/checkout-walkthrough.mp4
```

The converter requires schema-v2 playback evidence bound to the approved WebM, rehashes the referenced complete run report, rejects any recorded error finding, verifies the source hash and metadata again, creates H.264/yuv420p with CRF 18, the slow preset, and `+faststart`, fully decodes the result, checks dimensions and duration, and writes a delivery manifest.

### 9. Review the final MP4

Use a distinct output directory and report. `--derived-from` binds the MP4 review to the approved source-WebM review:

```bash
node scripts/review-video.mjs \
  --video ~/Downloads/checkout-walkthrough.mp4 \
  --timeline /path/to/artifacts-attempt-02/checkout-walkthrough-run-report.json \
  --derived-from /path/to/artifacts-attempt-02/video-review.json \
  --output-dir ~/Downloads/checkout-walkthrough-mp4-review \
  --report ~/Downloads/checkout-walkthrough-mp4-review.json
```

Watch the MP4 itself at 1x, inspect its generated sheets, and rerun this command with `--approve`, `--reviewer`, and descriptive `--notes`. The MP4 approval performs a separate exact-file real-time playback; source evidence cannot be reused. The derived review also rejects a source approval created from a different run report. Open the delivered file through a fresh preview URL or cache-busting query so an older browser cache cannot masquerade as the current artifact.

## Important configuration

```json
{
  "strictE2E": true,
  "readySelector": "[data-testid='app-ready']",
  "allowedHttpResponses": [
    { "status": 400, "urlIncludes": "/AuthService/SignIn" }
  ],
  "reducedMotion": "reduce",
  "videoQuality": 90,
  "visualStabilityMs": 300,
  "scrollDurationMs": 900,
  "dragDurationMs": 900,
  "captureStepScreenshots": true,
  "pointer": {
    "enabled": true,
    "color": "#ff3b30",
    "size": 20,
    "rippleSize": 38,
    "rippleMs": 520,
    "moveDurationMs": 900,
    "moveHoldMs": 320
  },
  "stepHoldMs": 1400,
  "minReadableHoldMs": 1200,
  "pointerMissingFailMs": 160,
  "openingStableMs": 800
}
```

Use `allowedHttpResponses` only for an intentional, asserted negative-path step. Match both the exact status and a narrow URL substring. It does not suppress the event: the run report records `expected-http-response` at informational severity. If Chromium also emits a generic console error for that response, allowlist its exact message separately with `allowedConsoleMessageSubstrings`. Unmatched 4xx responses remain warnings and unmatched 5xx responses remain errors.

Set `"pointer": false` to record undecorated evidence media with every other strict protection still enforced. The pointer ring and its review audits are skipped. Drag steps require the pointer's frame-level gesture audit, so pointer-free journeys use click, scroll, type, and press instead.

`reducedMotion: "reduce"` asks the application to honor `prefers-reduced-motion`; it does not rewrite application behavior. Keep meaningful product loaders and state changes. Remove decorative motion in the application or a safe recording fixture rather than masking real behavior in post-production.

## Delivery gate

A walkthrough is complete only when:

1. The run report is passed with no safety, runtime, or sensitive-data findings.
2. Recording started after the real opening state became ready.
3. Every frame decoded and timestamps are monotonic.
4. The opening stability, pointer continuity, smooth-scroll, smooth-gesture, blank-frame, pacing, and scenario checks pass.
5. Every step checkpoint exists and matches the intended journey.
6. The full WebM was watched at 1x and its approval contains passed, hash-bound real-time playback evidence.
7. The MP4 was generated from the exact approved WebM hash.
8. The full MP4 was reviewed and separately approved with its own passed playback evidence.
9. A fresh preview shows the current MP4, not a cached predecessor.

If any condition fails, create another attempt. The skill must not describe a flawed video as complete.

## Why this architecture

- Playwright [`Screencast`](https://playwright.dev/docs/api/class-screencast) gives exact start/stop control and supports persistent non-intercepting overlays.
- Playwright's own [video recording guidance](https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/tools/skills/playwright-cli/references/video-recording.md) recommends a scripted hero journey, reasonable pauses, `pressSequentially`, chapters, and overlays.
- [`mouse.move({ steps })`](https://playwright.dev/docs/api/class-mouse#mouse-move) sends intermediate events but does not add elapsed time, so the runner adds deliberate pacing.
- [Actionability](https://playwright.dev/docs/actionability) supplies visibility, stability, event-reception, and enabled checks; the runner uses locator trial clicks rather than stale coordinates.
- Playwright discourages [`networkidle`](https://playwright.dev/docs/api/class-page#page-goto-option-wait-until) as a readiness signal. The skill requires explicit product state instead.
- [`reducedMotion`](https://playwright.dev/docs/api/class-browser#browser-new-context-option-reduced-motion), [`document.fonts.ready`](https://developer.mozilla.org/en-US/docs/Web/API/FontFaceSet/ready), and [`HTMLImageElement.decode()`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decode) reduce avoidable layout changes before recording.
- FFmpeg's [H.264 guidance](https://trac.ffmpeg.org/wiki/Encode/H.264) and [`+faststart`](https://ffmpeg.org/ffmpeg-formats.html) provide crisp, broadly playable delivery files.

## Safety

Use seeded fixtures and test accounts. Keep authentication state uncommitted. Traces are optional because they can contain DOM, headers, request bodies, response bodies, and other sensitive data. Never record a real customer session.
