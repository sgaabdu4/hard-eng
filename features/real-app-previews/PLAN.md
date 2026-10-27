# Real-app UI previews instead of hand-made mock pages

Status: Complete

## Outcome + scope

A proposal for an existing screen is shown as before and after captures of the real app, and every Claude Code Artifact call in a Hard Eng project gets a note that says so at the moment of choice. Non-goals: blocking or prompting on any Artifact call, Codex changes, other MCP design tools, the user's own global instructions, a model eval of the skill text.

## Repository context

Owners: `.agents/skills/he-plan/references/ux.md` (preview rule), `.agents/skills/he-plan/references/wayfinding.md:49` (prototype row), `.agents/skills/he-plan/templates/PLAN.md:38` (Surface order), `.hooks/polling.py` (existing PreToolUse hook pattern), `.hooks/agent_hooks.py:240-244` (`POLL_HOOK`), `setup.py:145` (installs PreToolUse), `.claude/settings.json` (this repo's own hooks), `.agents/skills/he/references/requirements.md` (registry, next to the foreground-poll entry), `DECISION.md:44`.
Same cause: Trigger: a session asked to redesign an existing admin area published a hand-made HTML Artifact page and never captured the real app. Causes found: the Claude desktop Artifact tool text says a visual-design request starts with its quickstart call and that Claude may publish without being asked; `ux.md` says "choose the cheapest useful preview", lists Mock first and says no live-app build is needed; the session never loaded `he-plan` for that request after context compaction, so the rule was not in view when it chose. Earlier fix a03e373b (#92, grounded UX evidence + Surface/Before checks) helped for written plans but had no effect when no plan was written. 104e327f (foreground-poll hook) is the same PreToolUse pattern and works. Other places: `wayfinding.md:49` says "build the smallest isolated artifact"; the PLAN template and `gates.md:54` list Mock first; `plans.py::ux_proof` already lets only New or Mock explain a missing Before image, so no plan-check change is needed. Codex side: N/A — Codex has no Artifact tool.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: User on 2026-10-27: real-app captures required for existing screens in `ux.md`; no hard stop on Artifacts, because an artifact is sometimes the best way to show something; approved a note-only hook (the call always proceeds, the note reaches Claude). The note arrives with the tool result: on a quickstart call this is before the page is written; on a direct publish it is right after, and Claude can follow up with real captures. Rejected: deny, deny-once and ask prompts (user rejected a hard stop; ask hides its reason from Claude); allowing only after `/design` (blocks reports and other artifacts). User approved build, push to develop and a release to main.

## Acceptance + steps

- [x] An Artifact publish or quickstart call proceeds and gets a note that says to build a proposed change to the project's screens in the real app and send before and after captures, and to carry on for anything else → `tests/test_previews.py::test_notes_artifact_page_calls`: no permissionDecision; additionalContext names the registry entry and those steps.
- [x] A subagent's Artifact call gets the same note → `tests/test_previews.py::test_notes_artifact_page_calls`.
- [x] `read`, `list`, `open`, `delete`, `pin` and `unpin`, other tools and bad input produce no output → `tests/test_previews.py::test_ignores_artifact_reads_and_other_tools`.
- [x] The installed command runs the hook from the project root → `tests/test_previews.py::test_installed_command_adds_the_note`.
- [x] Setup installs the `Artifact` PreToolUse entry next to the poll entry in `.claude/settings.json` only → `tests/test_hook_setup.py::test_hook_registrations_invoke_shared_runner`: PreToolUse equals `[POLL_HOOK, PREVIEW_HOOK]`.
- [x] An update restores both entries in a project installed by an older release and keeps a project's own PreToolUse group → `tests/test_adoption.py::test_update_that_migrates_setup_files_is_scaffold_only_unless_edited` (an update rewrites the installed settings file) and `tests/test_adoption.py::test_update_retires_old_generation` (the project's own group stays first, then both entries).
- [x] `ux.md` requires `Existing` for a screen that exists and `New` rendered in the app for a new screen in an app; it allows `Mock` only when the app cannot be built or rendered locally, with the reason in the Before field; it drops "cheapest useful preview" and "no mandatory live-app build" → N/A — skill text; reviewed diff, plus the registry check for the new entry.
- [x] `wayfinding.md:49`, the PLAN template and `gates.md:54` list Existing first and say a visual prototype is rendered in the app → N/A — skill text; reviewed diff.
- [x] HE-REAL-APP-PREVIEW exists next to HE-NO-FOREGROUND-POLL and `tests/test_previews.py` cites it; `DECISION.md:44` no longer says there is no Hard Eng PreToolUse hook → `check --quick` registry check passes.
- [x] This repo's own `.claude/settings.json` has the new entry → reviewed diff; the live desktop check is N/A — hooks load at session start, so only a new session after merge can show the note; the tests run the real script and the installed command.

## Baseline + execution

Result: Passed
Evidence: Branch point origin/develop 1d404337: `Hard Eng`, `Canary`, `Release source` and `PR text` passed in CI. `python3 .hooks/hard-eng.py check --plan-stage Draft` on this branch: exit 0 (plan valid; secret scan found no leaks; no package reads the change).
Execution: One builder in this session on branch `real-app-previews`: hook + tests first, then setup and settings, then skill text and registry.

## Risks + recovery

The hook payload's tool name is assumed to be `Artifact`, as in session transcripts. If it differs, the note never appears and nothing else changes; the fix is the matcher string. The note is advice, so Claude can still choose a mock; the `ux.md` rule and plan checks still apply.

## ux_reference

N/A — hook, setup and skill text only; no visible UI.

## Verification

Result: Passed
Evidence: `uv run pytest -q tests/test_previews.py tests/test_polling.py tests/test_hook_setup.py tests/test_adoption.py tests/test_skill_links.py`: 114 passed; after the shared hook list change, `tests/test_previews.py tests/test_hook_setup.py tests/test_adoption.py`: 92 passed. `check --quick` found one finding, `tests/test_adoption.py` at 1002 lines; fixed by naming the hook list once in `agent_hooks.CLAUDE_TOOL_HOOKS`. The first push's full check found two more: jscpd matched the new hook's input code and test helper to the poll hook's (now shared through `polling.respond` and `test_polling.run`), and Biome reformatted the `ux.md` table; after that, jscpd found 0 clones, `biome ci` passed, the hook tests passed (46) and `check --quick` passed. Limit: the note in a live desktop session is unchecked until a new session starts after merge.
E2E: N/A — no user interface; tests run the real hook script and the installed command.
Delivery target: Merge
Delivery: Pending — `Hard Eng` CI passes on the PR and it merges into develop; then the develop to main release PR merges.
