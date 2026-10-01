# Correct skill text that no longer matches the code

Status: Complete

## Outcome + scope

Skill references state what the code does today: the Draft/Ready/Complete check exceptions, the storyboard-level blank-frame settings, `build.mjs` failure cases and the Playwright pin. Found by the Claude + Codex skill audit. The native skills also meet `writing-great-skills`: each rule has one owner and every reference is routed.

Non-goals: code changes and the Appwrite/Flutter skill fixes themselves, which ship in their own repositories; this PR only advances their submodules to the merged fixes.

## Repository context

Owners: `.agents/skills/he/references/gates.md` against `.hooks/hard-eng.py` `check`/`proven_elsewhere`; `.agents/skills/marketing-video/references/{recordings,render}.md` against `scripts/clips.mjs`, `scripts/media.mjs` and `scripts/build.mjs`; `.agents/skills/product-walkthrough-video/README.md` against `package.json`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to make every recommended audit change, review it, run adversarial review with GPT-6 Astra, test with GPT-6 Luna and Sonnet 5.5, and open a PR; after the PR opened, the user approved merging it.

## Acceptance + steps

- [x] `gates.md` names both cases in which `check --base` skips native checks → matches `proven_elsewhere` in `.hooks/hard-eng.py`.
- [x] `gates.md` states the `E2E:` requirement without migration-relative wording.
- [x] `recordings.md` documents `blankCrop`/`blankInk` at storyboard level → matches `clips.mjs` and `media.mjs`, which read `board.*`.
- [x] `render.md` lists the failures `build.mjs` actually throws and the silent unvoiced case.
- [x] The Playwright README defers the pinned version to `package.json`.
- [x] `he` routes setup/update/MCP failures to `integrations.md`.
- [x] One owner each: cleanup safety (`he-ship` checks), Marionette registration (`e2e` Flutter), Stop-check scope (`gates.md`), recurrence (`research` troubleshooting), `pointer: false` + `allowedHttpResponses` (walkthrough README); `testing.md`/`gates.md` defer to AGENTS.md instead of restating it.
- [x] Pointer-free recorded E2E states the drag limit on its own route.
- [x] The e2e Flutter Marionette guard skips web and integration-test runs, matching the building-flutter-apps skill.
- [x] Every relative, `#anchor` and Mermaid `click` link in the native skills resolves.
- [x] `.agents/skill-sources/appwrite-backend` and `building-flutter-apps` point at their merged audit PRs (fast-forward) → `check --base origin/main` (skill links) passes.

## Baseline + execution

Result: Passed
Evidence: main `1e995992` passed the Hard Eng workflow on push (run 36756875029).
Execution: One builder on branch `fix/skill-audit-core`.

## Risks + recovery

Documentation-only; recovery is reverting the commit.

## ux_reference

N/A — agent skill text; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main` passed. GPT-6 Astra adversarial review approved rounds 1–3 and a confirmation pass on `ea57ced4`. GPT-6 Luna (max) found the console allowlist described as exact-match, fixed in `ea57ced4`; Sonnet 5.5 (high) passed. Every relative, `#anchor` and Mermaid `click` link in the native skills resolves.
E2E: N/A — documentation-only change with no runtime journey; each statement is checked against the code it describes.

Delivery target: Merge
Delivery: Pending — squash merge and post-merge CI on the base branch.
