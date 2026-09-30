# Correct skill text that no longer matches the code

Status: Ready

## Outcome + scope

Skill references state what the code does today: the Draft/Ready/Complete check exceptions, the storyboard-level blank-frame settings, `build.mjs` failure cases and the Playwright pin. Found by the Claude + Codex skill audit. The native skills also meet `writing-great-skills`: each rule has one owner and every reference is routed.

Non-goals: code changes, the `AGENTS.override.md` commit rule (awaits the user's decision), and the Appwrite/Flutter skill fixes, which ship in their own repositories.

## Repository context

Owners: `.agents/skills/he/references/gates.md` against `.hooks/hard-eng.py` `check`/`proven_elsewhere`; `.agents/skills/marketing-video/references/{recordings,render}.md` against `scripts/clips.mjs`, `scripts/media.mjs` and `scripts/build.mjs`; `.agents/skills/product-walkthrough-video/README.md` against `package.json`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to make every recommended audit change, review it, run adversarial review with GPT-6 Astra, test with GPT-6 Luna and Sonnet 5.5, and open a PR.

## Acceptance + steps

- [ ] `gates.md` names both cases in which `check --base` skips native checks → matches `proven_elsewhere` in `.hooks/hard-eng.py`.
- [ ] `gates.md` states the `E2E:` requirement without migration-relative wording.
- [ ] `recordings.md` documents `blankCrop`/`blankInk` at storyboard level → matches `clips.mjs` and `media.mjs`, which read `board.*`.
- [ ] `render.md` lists the failures `build.mjs` actually throws and the silent unvoiced case.
- [ ] The Playwright README defers the pinned version to `package.json`.
- [ ] `he` routes setup/update/MCP failures to `integrations.md`.
- [ ] One owner each: cleanup safety (`he-ship` checks), Marionette registration (`e2e` Flutter), Stop-check scope (`gates.md`), recurrence (`research` troubleshooting), `pointer: false` + `allowedHttpResponses` (walkthrough README); `testing.md`/`gates.md` defer to AGENTS.md instead of restating it.
- [ ] Pointer-free recorded E2E states the drag limit on its own route.
- [ ] The e2e Flutter Marionette guard skips web and integration-test runs, matching the building-flutter-apps skill.
- [ ] Every relative, `#anchor` and Mermaid `click` link in the native skills resolves.

## Baseline + execution

Result: Passed
Evidence: main `1e995992` passed the Hard Eng workflow on push (run 36756875029).
Execution: One builder on branch `fix/skill-audit-core`.

## Risks + recovery

Documentation-only; recovery is reverting the commit.

## ux_reference

N/A — agent skill text; no product appearance.

## Verification

Result: Pending
Evidence: Pending — `python3 .hooks/hard-eng.py check --base origin/main`, adversarial review and model tests.
E2E: N/A — documentation-only change with no runtime journey; each statement is checked against the code it describes.

Delivery target: PR
Delivery: Pending — PR checks.
