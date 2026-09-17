# Flutter Marionette registration and recorded E2E route

Status: Complete

## Outcome + scope

Register the Marionette MCP server for Flutter projects that depend on `marionette_flutter`, pinned to the version in `pubspec.lock`, and give the E2E skill a Flutter route that drives the app through Marionette while `xcrun simctl io recordVideo` or `adb shell screenrecord` records the screen. Web walkthrough content (Playwright) and Flutter content live in separate files; only `e2e/SKILL.md` routes between them. Raise this repository's pre-push and CI time budgets from 180 to 300 seconds, because the suite alone now takes about 190 seconds locally and in CI. No new scripts, recorder wrapper or extra MCP servers.

## Repository context

Owners: `.hooks/mcp_setup.py` `detected_servers` (already emits `dart run marionette_mcp@` when the binding call is found), `.hooks/agent_hooks.py` `integrated_services` (binding regex), `tests/test_mcp_setup.py` (parametrized detection test), `.agents/skills/e2e/SKILL.md` (routes and shared proof rules; the web-only visual bullets sit inline there), `.agents/skills/product-walkthrough-video/` (Playwright recorder owner), `.agents/skills/he/references/integrations.md` line 27 and `README.md` line 27 (Marionette rows), `DECISION.md` Conditional MCPs decision. `.agents/skills/building-flutter-apps` is a submodule symlink and is linked to, not edited. The observed failure in a Flutter project was not missing code: no route told the agent to add the dependency, the binding call and the connect step, and no recorded-proof route exists for Flutter. `dart run marionette_mcp@0.6.0 --help` accepts an exact version descriptor, so the pin is a valid command.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for Marionette to work for Flutter applications, for the walkthrough or E2E skill to gain a Flutter route authored under the writing-great-skills rules with web and Flutter content separated, and for screen recording through `xcrun simctl io recordVideo` while Marionette drives; implementation delegated to Opus 5 subagents. Commit and PR need a separate go-ahead.

## Acceptance + steps

- [x] `detected_servers` registers `marionette` as `dart run marionette_mcp@<lock version>` when `marionette_flutter` is a dependency in `pubspec.yaml` and `pubspec.lock` records its version; falls back to `dart run marionette_mcp@` when the lock lacks it; registers nothing without the dependency → red/green tests in `tests/test_mcp_setup.py`.
- [x] `e2e/SKILL.md` holds routes plus shared rules only: web recorded proof routes to the walkthrough skill, Flutter recorded proof routes to `references/flutter.md`; the moved web bullets have one owner in the walkthrough skill.
- [x] `references/flutter.md` gives the app-side setup (regular dependency, debug-only binding before Sentry, test-entrypoint guard, version match, new session after registration), the connect and drive loop, simulator and emulator recording with SIGINT stop, and media verification with ffprobe and extracted frames; it never names Playwright, and the walkthrough skill never names Flutter.
- [x] `integrations.md`, `README.md` and `DECISION.md` state the dependency trigger and the pin.
- [x] Gates pass on the final tree; the E2E journey below is run.

## Baseline + execution

Result: Passed
Evidence: Starting revision ea6ea7c (same commit as this branch point) in a clean detached worktree earlier today: `uv run --no-project --with pyyaml python .hooks/hard-eng.py check` exit 0, 739 tests passed, all 17 native checks passed.
Execution: Two Opus 5 subagents with disjoint files (hooks plus tests; skills plus docs); the coordinator owns this plan, runs the gates and the E2E journey.

## Risks + recovery

`configure_mcp` preserves existing entries, so a written pin does not follow a later lock upgrade; the Flutter reference states the manual edit. A wrong pin surfaces at `connect` as a version mismatch, not silently. Marionette works only in debug or profile builds; the reference says so. Recovery is reverting the single hook change and the skill files.

## ux_reference

N/A — hook and skill text changes have no visual interface.

## Verification

Result: Passed
Evidence: Red on the unmodified hooks (`git stash` of `mcp_setup.py`/`agent_hooks.py`): four cases of `test_installer_registers_only_detected_service_mcps` failed, the binding-only case registering `marionette` it should not, and the dependency-with-lock, dev-dependency-without-lock and lock-without-entry cases registering nothing; those three fail at the server-key assertion, so the pinned and fallback argument values are proven by green only. Green: `tests/test_mcp_setup.py` and `tests/test_agent_hooks.py`, 103 passed; ruff format/check variants, pyrefly and vulture clean on the touched files; `mcp_setup.py` 289 and `agent_hooks.py` 370 lines. The binding regex in `integrated_services` had no consumer other than registration and no test, so it was removed rather than kept as a dead trigger. Skill text: greps for Playwright/TypeScript/walkthrough/WebM/pnpm over `flutter.md` and Flutter/Marionette/simctl/adb over the walkthrough skill return nothing; all seven relative links resolve; gitleaks clean. The Sentry ordering claim in `flutter.md` matches the upstream troubleshooting doc (issue 96). Review corrected one claim: `-sseof` on a one-frame file returns that frame, verified with ffmpeg 9.0.1. The web bullets removed from `e2e/SKILL.md` already had owners in the walkthrough README and SKILL, so nothing was added there. Review after the first green full check (742 tests) found that a bare `dev_dependencies:` header in any `pubspec.yaml` made `marionette_server` raise `TypeError` (reproduced against the function), which would have failed setup for that repository; both lookups now default to an empty mapping and a parametrized case covers the bare header. The updater re-detects servers only when it applies a newer verified revision, so the reference and integrations row state that a dependency added between updates needs a manual `.mcp.json` entry. The Flutter route edges are now labelled `Recorded proof needed` like the web edge. The final full check is recorded in the delivery line below.
E2E: Passed — `dart run marionette_mcp@0.6.0 --help` printed the server usage (exit 0), proving the exact-version descriptor; on the booted iPhone 17 Pro simulator `xcrun simctl io recordVideo --codec=h264 --force` ran in the background while the simulator appearance was toggled, `kill -INT` stopped it with "Recording completed. Writing to disk." and exit 0, ffprobe read h264 1206x2622, 74 frames, 4.38 s, and the extracted first and last frames were viewed and show the app screen; the earlier static-screen run produced 1 frame at 0.07 s, which the reference now documents.

Delivery target: PR
Delivery: Pending — full `hard-eng.py check --base origin/main` on the final tree passed: exit 0, 743 tests in 192 s, every native check passed. The first push was rejected by the pre-push hook after every check passed because the run exceeded the 180-second budget, matching the CI cancellation on PR #115; the user chose to raise both budgets to 300 seconds (workflow timeout 5 minutes) and push with `--no-verify`.
