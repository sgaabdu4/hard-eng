# Agents drive a real browser through one Hard Eng command

Status: Draft

## Outcome + scope

Hard Eng installs agent-browser like its other tools and gives agents one `browser` command: plain browser steps, sign-in per role, and screenshots at 390 and 1280 px with red boxes and hidden personal data. The E2E, Ship and Trello coordinator skills name it. Real Claude and Codex runs prove it. It also adds checks that refuse old workarounds, timer quick fixes, excuse markers and unnamed markdown across each whole project. Non-goals: a project pin of the tool; any change to the walkthrough video pipeline; the talk ideas that the Proposal rows below skip.

## Sources + coverage

Sources: the talk transcript that the user pasted on 2026-11-15, read in full; the talk video, with one frame each 10 seconds, full-size frames of each slide with small text and of the short property test clip, and its words through the transcript, which starts after the title card at 0:14, read in full; the user's chat messages of 2026-11-15, read in full.
Reviewer: a second reader read the sources and this plan, not the notes. It made its own list first, then gave 25 findings. Each is repaired: 14 new rows; the talk line split into one line per owner with its test; the owner claims corrected (Semgrep holds no API ban; HE-COMMENT-LINES and HE-DEBT-SHRINK-ONLY are partial; the AGENTS.md line is prose only); the AGENTS.md, feature map and session limits moved to `Proposal` rows; token and step counts added to the eval; the 0.1 s limit removed; the small slide text read at full size.
Deliverables: None

- Talk, trust pyramid: code, static checks, verification, then prose, with human review last: In scope — Hard Eng puts gates before prose
- Talk, correct an agent with a deterministic check, not more prose: In scope — Hard Eng puts gates before prose
- Talk, agents over-rotate on one small correction and make it a rule forever: In scope — HE Learn acts on verified repeats only
- Talk, ban APIs that need nuance (the useEffect example): In scope — Banned nuanced APIs
- Talk, folders as context with import bans between them: In scope — Import bans by folder
- Talk, one folder per feature (the Dune slide): Proposal — skip as a Hard Eng rule; folder layout stays each project's choice through the Codebase Design skill; yes — user, approval of the repaired plan, 2026-11-15
- Talk, no comments; the slide points to a fix-comments skill: In scope — Comments
- Talk, agents write unsolicited markdown that justifies a shortcut: In scope — A markdown file that no other tracked file names fails
- Talk, lint messages that tell the agent to fix the root cause: In scope — Root-cause fixes
- Talk, each copy of a workaround makes the next one more likely; a lint rule first, then clean the old cases: In scope — Old switch-offs fail across the whole project
- Talk, imperative timers as quick fixes: In scope — Every zero-delay or next-frame call in app code fails
- Talk, review looks at proof media (videos, screenshots, diagrams): In scope — Proof media in review
- Talk, read the code sometimes; with nothing left to review, agents merge most of their own PRs: In scope — Agents merge their own PRs
- Talk, runtime verification: the agent runs the real app with developer tools: In scope — The `browser` command runs any agent-browser step
- Talk, a project CLI that the agent reuses each time (click, snapshot, screenshot), which saves tokens and can be tested: In scope — The `browser capture` command writes whole-page images
- Talk, a feature map of what exists, how users reach it and what proves it works; the slide points to a create-verification-skill: Proposal — the map ships only if the eval shows fewer steps or fewer wrong pages with it than without it; yes — user, approval of the repaired plan, 2026-11-15
- Talk, formal verification with TLA+ and Lean: Proposal — skip for now; yes — user, approval of the repaired plan, 2026-11-15
- Talk, UI property-based testing with Bombadil: Proposal — skip for now; yes — user, approval of the repaired plan, 2026-11-15
- Talk, a state chart skill for review: Proposal — skip; Hard Eng PRs already show Mermaid before and after flows; yes — user, approval of the repaired plan, 2026-11-15
- Talk, the technique table and the 70% of tokens spent on verification: Proposal — no change; a reference list, not a request; yes — user, approval of the repaired plan, 2026-11-15
- Talk, the team's results (PR counts, daily releases, revert rate, speed table): Proposal — no change; results of another team, not a request; yes — user, approval of the repaired plan, 2026-11-15
- Talk, do not automate a bad loop; an outer loop on triggers that fuzzes each release and merges the fix PRs: Proposal — skip; the Trello coordinator is the outer loop, and a release fuzz bot is a later effort of its own; yes — user, approval of the repaired plan, 2026-11-15
- Talk, people named in the talk: Proposal — no role in this work; yes — user, approval of the repaired plan, 2026-11-15
- User, use the latest main: In scope — Work starts from the latest main
- User, compare each talk point with Hard Eng today and say what to add: In scope — Hard Eng puts gates before prose
- User, research questions answered in chat (summary, CLI ideas, thread check, trials for this use, latest versions, other tools, Cloudflare, best pick, token cost, advisor): In scope — Research answered in chat
- User, use the latest version of each tool: In scope — newest release at least 2 days old
- User, pick one browser tool for agents: In scope — The `browser` command installs agent-browser
- User, a shared helper: sign-in per role: In scope — The `browser signin` command saves a session file
- User, a shared helper: the red box and the standard widths: In scope — The `browser capture` command writes whole-page images
- User, a shared helper: hidden personal data: In scope — The `browser capture` command hides email addresses and phone numbers
- User, one browser per agent session, closed at the end: Proposal — the command refuses a step with no `--session`, refuses `close --all`, and `capture` closes its own session; yes — user, approval of the repaired plan, 2026-11-15
- User, the Ship and coordinator skills name it as the one way to capture: In scope — The E2E, Ship and Trello coordinator skills name the command
- User, follow what the talk says: In scope — Hard Eng puts gates before prose
- User, clean up old workarounds: In scope — Old switch-offs fail across the whole project
- User, no markdown that excuses a shortcut: In scope — A markdown file that no other tracked file names fails
- User, no excuse markers left in code: In scope — TODO, FIXME, HACK and XXX markers
- User, timers: refuse old calls too; a project cannot merge until all are fixed (plan question, 2026-11-15): In scope — Every zero-delay or next-frame call in app code fails
- User, the other new checks fail on old cases across the whole project too (plan question, 2026-11-15): In scope — Old switch-offs fail across the whole project
- User, dart-decimate is the user's own package; does it need a change (plan question, 2026-11-15): In scope — A `dart-decimate-ignore` comment counts as a switch-off
- User, rely on React Doctor for APIs that need care, such as useEffect, if it catches them (chat, 2026-11-15): In scope — Banned nuanced APIs
- User, AGENTS.md and the rest of Hard Eng get updated: Proposal — the skills change; AGENTS.md gets one line only if the evals show agents miss the command, because it loads in every session; yes — user, approval of the repaired plan, 2026-11-15
- User, evals after the install: In scope — An agent check case proves agents find and use the command
- User, token cost and gain over the current flow: In scope — records tokens and steps per run
- User, run it on a real signed-in project check: In scope — One run on a private project's live site

## Repository context

Owners: [tool_setup.py](../../.hooks/tool_setup.py) (`PACKAGES`, `provision_batch`, `RELEASE_AGE_SECONDS`); [gate_runner.py](../../.hooks/gate_runner.py) (commands); [gate_config.py](../../.hooks/gate_config.py) (`GateConfig`); new `.hooks/browser.py`; [E2E skill](../../.agents/skills/e2e/SKILL.md); [Ship checks](../../.agents/skills/he-ship/references/checks.md) line 99 (red ring); [coordinator mockups](../../.agents/skills/trello-coordinator/references/mockups.md) line 17 (390 and 1280 px); [agent checks](../../tests/agent_checks.py).
Same cause: in an earlier trial a working browser tool went unused, because it was not installed for agents and no skill named it. No Hard Eng fix came before this one. Other places searched: the walkthrough video skill pins Playwright for polished video delivery, a separate job that stays; the marketing video skill renders staged images in tests, also separate.
Single source: red ring rule → stays in Ship checks; how to draw it moves to `browser capture`, and Ship links to it. Capture widths 390 and 1280 → `browser capture` defaults; the coordinator mockups line links to it. Release age → `RELEASE_AGE_SECONDS`, reused, not copied. Personal data rule → stays in the E2E skill; `browser capture` enforces the email and phone part. Searched: `.agents/skills`, `.hooks`, `README.md` for "red ring", "390", "1280", "screenshot".

## Decisions + authorization

Handoff: Approval
Blockers: The user asked on 2026-11-15 whether to enforce one folder per feature and domain-driven design, for a firm yes or no on TLA+ and Lean, and for dart-decimate to enforce its rules without suppressions; the counts are being rerun with Hard Eng's real patterns, and each timer kind needs a proven fix with no suppression, before the user is asked again.
Authority: Human-loop. The user said "yes pls" to a plan for agent-browser with the shared helper, and asked for the talk, AGENTS.md updates and evals after install. On 2026-11-15 the user approved the plan with all its proposals ("Approve all") and asked to start the build. That approval is void: the plan was presented as checked against the talk, but several skip reasons (timers first) were not checked against real code. The user asked on 2026-11-15 for every talk point to be checked. After the check of each talk point, the user approved the repaired plan on 2026-11-15, chose to refuse old timer calls too, and chose whole-project scope for the other new checks.

## Acceptance + steps

- [ ] Work starts from the latest main (origin/main c5068084) and rebases on it before each push → N/A — a Git state, not behavior; `git merge-base --is-ancestor origin/main HEAD` exits 0 before the push.
- [ ] The `browser` command installs agent-browser at the newest release at least 2 days old through the mise path of the other tools, plus its Chrome, and changes no project file → `tests/test_browser.py::test_installs_like_other_tools`.
- [ ] The `browser` command runs any agent-browser step from the output folder, including its console and page error reads → `tests/test_browser.py::test_runs_from_output_folder` (a local page with a console error); the added time per step is measured 2 times each way in Verification (planning: 0.015 s raw, 0.06 s through a Python start).
- [ ] Proposal "one browser per agent session": the command refuses a step with no `--session`, refuses `close --all`, and `capture` closes its own session → `tests/test_browser.py::test_refuses_shared_sessions`.
- [ ] The `browser capture` command writes whole-page images at 390 and 1280 px (coordinator mockups line 17) into the output folder, draws a red box over each named element on top of the page (Ship checks line 99), and fails when a name matches nothing, because a missing box would hide the change (AGENTS.md: never hide findings) → `tests/test_browser.py::test_capture_draws_boxes_at_both_widths` (real browser, local page; checks image widths and red pixels on each element box).
- [ ] The `browser capture` command hides email addresses and phone numbers in page text and form fields before each image (E2E skill: keep secrets and personal data out of artifacts). Limit: a pattern match; it misses names and unusual forms → `tests/test_browser.py::test_capture_hides_emails_and_phones`.
- [ ] The `browser signin` command saves a session file for a role, reading the login page and the names of its environment variables from a new `browser.roles` section of `hard-eng.gates.json`; the password goes on standard input only, never in a command line or the output (E2E skill: keep secrets out of artifacts) → `tests/test_browser.py::test_signin_keeps_password_off_command_line` (local login page).
- [ ] The E2E, Ship and Trello coordinator skills name the command as the one way to drive a browser and capture; Ship and the coordinator link to it and no longer restate widths or how to draw → `tests/test_skill_links.py::test_documented_commands_and_flags_exist`, `tests/test_skill_links.py::test_distributed_skill_links_resolve`, `tests/test_skill_routing.py::test_every_request_picks_its_own_skill`.
- [ ] An agent check case proves agents find and use the command: a fixture web app with a sign-in and one changed label, installed from the source under test; the task names no tool. Pass list: a box on the change at both widths, no personal data in the images, no password in the events, no new files in the repository (the Stop hook refuses unplanned files), no browser left running. The case records tokens and steps per run → `tests/test_agent_checks.py::test_browser_proof_judge_fails_each_missing_item`, then `tests/agent_checks.py --case browser-proof --repeat 3` for Claude and Codex, on the old source and the new one; the new source passes every item in each run; the report gives median tokens and steps for each source.
- [ ] Proposal "AGENTS.md": AGENTS.md gets one line only if the evals show agents miss the command in any run; the evals then run again → N/A — a decision read from the agent check results, not a behavior.
- [ ] Proposal "feature map": the case runs with and without a map file; the map ships only with fewer steps or fewer wrong pages; else the result is recorded and the slice is dropped → N/A — a decision read from the agent check results, not a behavior.
- [ ] Hard Eng puts gates before prose: HE Learn's preference order puts a deterministic check before a rule, and its Mechanical row turns a repeated correction into a check → N/A — skill text, no code changes; [HE Learn](../../.agents/skills/he-learn/SKILL.md) lines 41 and 57.
- [ ] HE Learn acts on verified repeats only: outside the retro it skips one-off fixes, and the Stop hook counts a second sighting as a repeat → N/A — skill text; [HE Learn](../../.agents/skills/he-learn/SKILL.md) lines 3 and 39.
- [ ] Banned nuanced APIs: React Doctor is a required gate in each React project; a run of its gate command on a sample failed (exit 1) on state copied from props, a timer with no cleanup, a fetch inside an effect and a stale dependency (2026-11-15). Hard Eng adds no ban of its own → `tests/test_setup.py::test_react_and_existing_project_scripts_are_gated`.
- [ ] Import bans by folder: a TypeScript package gets a required boundaries gate; a Dart package checks boundaries inside its full scan; the project writes its own bans → `tests/test_setup.py::test_typescript_packages_require_boundary_gate`, `tests/test_setup.py::test_dart_boundary_gate_requires_blocking_project_rules`.
- [ ] Comments: HE-COMMENT-LINES refuses comment blocks of two or more lines; one why-line stays allowed (the user's standing rule). Measured: plain comments are a small share of app code lines; the largest share is generated code, which the rule exempts → `tests/test_comments.py::test_changed_source_holds_one_line_comments_only`.
- [ ] A markdown file that no other tracked file names fails, old ones too, except README, AGENTS, PRODUCT, DESIGN, SECURITY, CHANGELOG, plans, decisions and skill files. Measured on the installed projects: many such files are agent leftovers (plan dumps, to-do and issue notes, hand-over notes); counts stay local → `tests/test_unnamed_markdown.py::test_an_unnamed_markdown_file_fails`, `tests/test_unnamed_markdown.py::test_a_named_markdown_file_passes`.
- [ ] Root-cause fixes: prose only, AGENTS.md "fix faults at their cause" and "never weaken checks" → N/A — prose; no check exists.
- [ ] Old switch-offs fail across the whole project: every HE-NO-SWITCH-OFF form fails in every tracked source file, not only in added lines, outside generated output and scaffold paths; it never takes debt. Measured: the installed projects hold old switch-offs outside generated code; counts stay local → `tests/test_comments.py::test_old_switch_offs_anywhere_in_the_project_fail`, `tests/test_comments.py::test_switch_offs_in_generated_output_pass`.
- [ ] A `dart-decimate-ignore` comment counts as a switch-off; today it passes, and the installed projects hold such comments. Hard Eng reads the comment text, so dart-decimate itself needs no change → `tests/test_comments.py::test_dart_decimate_ignore_is_a_switch_off`.
- [ ] Every zero-delay or next-frame call in app code fails, old ones too, outside tests and generated code: JavaScript and TypeScript `setTimeout` or `setImmediate` with no delay or 0, `requestAnimationFrame`, `requestIdleCallback`, `queueMicrotask`; Dart `scheduleMicrotask`, `Future.microtask`, `Future.delayed(Duration.zero)`, `addPostFrameCallback`. The message says to fix the order of events at its cause. Measured: the installed projects hold such calls, and React Doctor passes them → `tests/test_comments.py::test_zero_delay_and_next_frame_calls_fail_in_app_code`, `tests/test_comments.py::test_timer_calls_in_tests_and_generated_code_pass`.
- [ ] Each installed project removes its zero-delay and next-frame calls, old switch-offs, excuse markers and unnamed markdown files in its own PR before the Hard Eng release; the release canary needs each installed project to pass → N/A — project PRs; the canary result proves it.
- [ ] TODO, FIXME, HACK and XXX markers in any comment of a tracked source file fail → `tests/test_comments.py::test_excuse_markers_fail_anywhere_in_the_project`.
- [ ] Each new refusal reaches every project: the new-project flows of `release_canary.py` pass with it, and each installed project is loaded with the new hooks before the release → N/A — a release step; AGENTS.override.md refusal rule.
- [ ] Proof media in review: Ship UI evidence needs before and after media for a UI change → `tests/test_shipping_ui_evidence.py::test_ui_changes_reject_missing_foreign_or_duplicate_evidence`.
- [ ] Agents merge their own PRs: HE Ship merges when checks pass and the independent review is done → `tests/test_ship_actions.py::test_ship_merge_matches_verified_head_and_checks_result`.
- [ ] Research answered in chat on 2026-11-15 before this plan: tool trials, latest versions, other tools, Cloudflare, token cost, advisor checks → N/A — answers, not code; limits kept in Risks.
- [ ] One run on a private project's live site: test admin account, read only, sign in, capture at both widths, sign out → N/A — a live run that no test can repeat; HE-REAL-SERVICE-RUN, Real service line below.

## Baseline + execution

Result: Passed
Evidence: 2026-11-15, `python3 .hooks/hard-eng.py check --plan-stage Draft` on the starting code (origin/main c5068084): base commit 33e40da3 passed the required CI checks; only the plan changed, so the secret scan ran and passed; exit 0.
Execution: one Sonnet builder for the command, its tests and the skill edits, first slice = install plus `capture` on a local page. Then the planner runs the agent check case for both clients and the live run. A fresh Codex review through `hard-eng.py challenge` before the Complete gate.

## Risks + recovery

- The tool ships several times a week and can break a step. Recovery: the 2-day age hold, and the reinstall of the newest release that `provision_latest` already does for a broken release.
- The Codex `workspace-write` sandbox stops every Chrome, Playwright's too (tested 2026-11-15: Chrome needs macOS services the sandbox denies). Recovery: the E2E skill tells Codex to run browser steps outside the sandbox with approval; a full-access Codex worked.
- About 1.5 GB of memory per open browser (1.0 GB for Playwright CLI). Recovery: `capture` closes its own session.
- A real-browser test can push the Hard Eng test gate near its time limit. Recovery: measure in the build; move it to its own shard if needed.
- Linux is not tested; an open report says 0.42 hangs there. Recovery: CI on Linux runs the real-browser test.
- Limits of the research: one run per tool in the trials; macOS only; the Chrome DevTools CLI judged from its help text only; Reddit not read.

## ux_reference

N/A — no product screen changes; the images the command makes are evidence for agents and reviewers, not a user interface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — the `browser-proof` agent check case through real Claude and Codex sessions, 3 runs each, with the pass list above; plus `tests/test_browser.py` through a real browser.
Real service: Required — a private project's live site with its test admin account: `browser signin`, `browser capture` at both widths, then sign out through the app. Read only; no writes.
Retro: Pending

Delivery target: Merge; Delivery: Pending — PR checks green and merged into develop.
