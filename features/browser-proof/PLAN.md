# Agents drive a real browser through one Hard Eng command

Status: Ready

## Outcome + scope

Hard Eng installs agent-browser like its other tools and gives agents one `browser` command: plain browser steps, sign-in per role, and screenshots at 390 and 1280 px with red boxes and hidden personal data. The E2E, Ship and Trello coordinator skills name it. Real Claude and Codex runs prove it. Non-goals: a project pin of the tool; the strict refusals and the architecture rules from the same talk, which have their own plans and PRs; any change to the walkthrough video pipeline; the talk ideas that the Proposal rows below skip.

## Sources + coverage

Sources: the talk transcript that the user pasted on 2026-11-15, read in full; the talk video, with one frame each 10 seconds, full-size frames of each slide with small text and of the short property test clip, and its words through the transcript, which starts after the title card at 0:14, read in full; the user's chat messages and question answers of 2026-11-15, read in full.
Reviewer: two second-reader passes read the sources and this plan, not the notes. The first gave 25 findings, all repaired. After the split, the second gave 22: rows added for the three approved checks, dart-decimate parity, the hot-path slide and the framing slides; the moved rows became `Later` rows citing the split answer at 06:13; proposals not named in an earlier question are asked again; the comment and root-cause rows moved or became proposals; claims reworded to what each test proves; new tests marked new. Prose: three Writing Great Skills Reader passes on the changed skill text, by a subagent that did not write it, quoted 12, then 7, then 3 sentences on the final text; each is reworded, and the command detail moved to `.agents/skills/e2e/references/browser.md`.
Deliverables: None

- Talk, trust pyramid: code, static checks, verification, then prose, with human review last: In scope — Hard Eng puts gates before prose
- Talk, correct an agent with a deterministic check, not more prose: In scope — Hard Eng puts gates before prose
- Talk, agents over-rotate on one small correction and make it a rule forever: In scope — HE Learn acts on verified repeats only
- Talk, ban APIs that need nuance (the useEffect example): In scope — Banned nuanced APIs
- Talk, folders as context with import bans between them: In scope — Import bans by folder
- Talk, one folder per feature (the Dune slide): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/architecture-rules/PLAN.md`
- Talk, no comments; the slide points to a fix-comments skill: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md` (comment rules join the whole-project refusals)
- Talk, agents write unsolicited markdown that justifies a shortcut: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- Talk, lint messages that tell the agent to fix the root cause: Proposal — no change: Hard Eng's own refusals already tell the agent to fix the cause; native tool messages belong to each tool; yes — user, answer to the 12 proposals, 2026-11-15
- Talk, each copy of a workaround makes the next one more likely; a lint rule first, then clean the old cases: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- Talk, imperative timers as quick fixes: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- Talk, review looks at proof media (videos, screenshots, diagrams): In scope — Proof media in review
- Talk, read the code sometimes; with nothing left to review, agents merge most of their own PRs: In scope — Agents merge their own PRs
- Talk, runtime verification: the agent runs the real app with developer tools: In scope — The `browser` command runs any agent-browser step
- Talk, a project CLI that the agent reuses each time (click, snapshot, screenshot), which saves tokens and can be tested: In scope — The `browser` command runs any agent-browser step
- Talk, a feature map of what exists, how users reach it and what proves it works; the slide points to a create-verification-skill: Proposal — the map ships only if the eval shows fewer steps or fewer wrong pages with it than without it; yes — user, answer to the 12 proposals, 2026-11-15
- Talk, formal verification with TLA+ and Lean: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/architecture-rules/PLAN.md`
- Talk, UI property-based testing with Bombadil: Proposal — no Hard Eng rule: projects that need property tests already use them, and no check can say where they are needed; yes — user, approval of the repaired plan, 2026-11-15
- Talk, a state chart skill for review: Proposal — skip; Hard Eng PRs already show Mermaid before and after flows; yes — user, approval of the repaired plan, 2026-11-15
- Talk, the technique table and the 70% of tokens spent on verification: Proposal — no change; a reference list, not a request; yes — user, answer to the 12 proposals, 2026-11-15
- Talk, the team's results (PR counts, daily releases, revert rate, speed table): Proposal — no change; results of another team, not a request; yes — user, answer to the 12 proposals, 2026-11-15
- Talk, do not automate a bad loop; an outer loop on triggers that fuzzes each release and merges the fix PRs: Proposal — not part of Hard Eng: the Trello coordinator is the outer loop; yes — user, approval of the repaired plan, 2026-11-15
- Talk, people named in the talk: Proposal — no role in this work; yes — user, answer to the 12 proposals, 2026-11-15
- User, use the latest main: In scope — Work starts from the latest main
- User, compare each talk point with Hard Eng today and say what to add: In scope — Each talk point has a row
- User, research questions answered in chat (summaries, CLI ideas, thread check, trials for this use, latest versions, other tools, Cloudflare, best pick, token cost, advisor, what TLA+ and Lean are, the list of planned work): In scope — Research answered in chat
- User, use the latest version of each tool: In scope — newest release at least 2 days old
- User, pick one browser tool for agents: In scope — The `browser` command installs agent-browser
- User, a shared helper: sign-in per role: In scope — The `browser signin` command saves a session file
- User, a shared helper: the red box and the standard widths: In scope — The `browser capture` command writes whole-page images
- User, a shared helper: hidden personal data: In scope — The `browser capture` command hides email addresses and phone numbers
- User, one browser per agent session, closed at the end: Proposal — the command refuses a step with no `--session`, refuses `close --all`, and `capture` closes its own session; yes — user, answer to the 12 proposals, 2026-11-15
- User, the Ship and coordinator skills name it as the one way to capture: In scope — The E2E, Ship and Trello coordinator skills name the command
- User, follow what the talk says: In scope — Each talk point has a row
- User, clean up old workarounds: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, no markdown that excuses a shortcut: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, no excuse markers left in code: Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, timers: refuse old calls too; a project cannot merge until all are fixed (plan question, 2026-11-15): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, the other new checks fail on old cases across the whole project too (plan question, 2026-11-15): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, dart-decimate is the user's own package; does it need a change (plan question, 2026-11-15): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, rely on React Doctor for APIs that need care, such as useEffect, if it catches them (chat, 2026-11-15): In scope — Banned nuanced APIs
- User, AGENTS.md and the rest of Hard Eng get updated: Proposal — the skills change; AGENTS.md gets one line only if the evals show agents miss the command, because it loads in every session; yes — user, answer to the 12 proposals, 2026-11-15
- User, evals after the install: In scope — An agent check case proves agents find and use the command
- User, token cost and gain over the current flow: In scope — records tokens and steps per run
- User, run it on a real signed-in project check: In scope — One run on a private project's live site
- Proposal, the live run is read only, uses the test admin account and signs out at the end: Proposal — read only, test admin account, sign out; yes — user, answer to the 12 proposals, 2026-11-15
- Proposal, `browser capture` hides email addresses and phone numbers only, by pattern: Proposal — hides emails and phones only; names and other personal data stay the agent's job under the E2E skill; yes — user, answer to the 12 proposals, 2026-11-15
- Proposal, Hard Eng installs the tool for agents; no project pins it and no project file changes: Proposal — Hard Eng provisions the tool, as it does Fallow and React Doctor; yes — user, answer to the 12 proposals, 2026-11-15
- User, APIs that need care in stacks other than React (chat, 2026-11-15 04:22): Proposal — Flutter keeps its rules in flutter_skill_lints; the strict-refusals plan adds rules there; no other stack has such an API in the installed projects; yes — user, answer to the 12 proposals, 2026-11-15
- User, the approved checks: markdown that nothing links to, removal of old switch-offs, `dart-decimate-ignore` as a switch-off (question answer, 2026-11-15 05:03): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, dart-decimate enforces best practices for Dart as Fallow does for JavaScript (chat, 2026-11-15 05:14): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- Talk, a file name that carries a rule (`tick.hot.ts`: runs every tick, no allocations): In scope — Hot paths
- Talk, framing slides (quality and quantity, the trust curve, code is memory, should I build a software factory, the app framework box): Proposal — no change; framing, not a request; the app framework box is covered by the architecture plan; yes — user, answer to the 12 proposals, 2026-11-15
- User, no project-specific data in the Hard Eng repository (chat, 2026-11-15, twice): In scope — No private project data in the plan, code, tests, commits or PR text
- User, check every talk point against Hard Eng and the code (chat, 2026-11-15): In scope — Each talk point has a row
- User, enforce one folder per feature and domain-driven design; firm yes or no on TLA+ and Lean (chat, 2026-11-15): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/architecture-rules/PLAN.md`
- User, never suppress; refactor to the best practice; Hard Eng is hard on purpose (chat, 2026-11-15): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, the user owns flutter_skill_lints, building-flutter-apps and appwrite-backend, and they may change (chat, 2026-11-15): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, refactor every project that uses Hard Eng with Sonnet builders and Opus reviewers, so all end on the latest Hard Eng (chat, 2026-11-15): Later — user, plan split answer, 2026-11-15 06:13: in its own plan and PR, `features/strict-refusals/PLAN.md`
- User, no two threads do the same work; check open PRs and open a PR early (chat, 2026-11-15): In scope — A draft PR claims the work
- User, split, merge each into develop, one release PR to main, then the other repos (plan split question, 2026-11-15): In scope — Delivery order
- User, the GitHub description says "local coding agents", which misleads (chat, 2026-11-15 06:53): In scope — The repository description
- User, the readme says what "hard" means: bad quality is refused, old code too, in simple English with a clear layout (chat, 2026-11-15 06:53): Later — user, plan split answer, 2026-11-15 06:13: old code is refused only once the strict refusals land, so the section ships with them in `features/strict-refusals/PLAN.md`
- User, test the changes on every OS, in git worktrees and remotely; a Windows virtual machine is for checks during this work only, never in CI (chat, 2026-11-15 06:53 to 06:56): In scope — Each OS, worktrees and a remote machine
- User, always check the work with the advisor (chat, 2026-11-15 06:43): In scope — Research answered in chat

## Repository context

Owners: [tool_setup.py](../../.hooks/tool_setup.py) (`PACKAGES`, `provision_batch`, `RELEASE_AGE_SECONDS`); [gate_runner.py](../../.hooks/gate_runner.py) (commands); [gate_config.py](../../.hooks/gate_config.py) (`GateConfig`); new `.hooks/browser.py`; new `tests/test_browser.py`; new `browser-proof` case in `tests/agent_checks.py` with new `tests/test_agent_checks.py::test_browser_proof_judge_fails_each_missing_item`; [E2E skill](../../.agents/skills/e2e/SKILL.md); [Ship checks](../../.agents/skills/he-ship/references/checks.md) line 99 (red ring); [coordinator mockups](../../.agents/skills/trello-coordinator/references/mockups.md) line 17 (390 and 1280 px); [agent checks](../../tests/agent_checks.py).
Same cause: in an earlier trial a working browser tool went unused, because it was not installed for agents and no skill named it. No Hard Eng fix came before this one. Other places searched: the walkthrough video skill pins Playwright for polished video delivery, a separate job that stays; the marketing video skill renders staged images in tests, also separate.
Single source: red ring rule → stays in Ship checks; how to draw it moves to `browser capture`, and Ship links to it. Capture widths 390 and 1280 → `browser capture` defaults; the coordinator mockups line links to it. Release age → `RELEASE_AGE_SECONDS`, reused, not copied. Personal data rule → stays in the E2E skill; `browser capture` enforces the email and phone part. Searched: `.agents/skills`, `.hooks`, `README.md` for "red ring", "390", "1280", "screenshot".

## Decisions + authorization

Blockers: None
Authority: Human-loop. The user said "yes pls" to a plan for agent-browser with the shared helper, and asked for the talk, AGENTS.md updates and evals after install. On 2026-11-15 the user approved the plan with all its proposals ("Approve all") and asked to start the build. That approval is void: the plan was presented as checked against the talk, but several skip reasons (timers first) were not checked against real code. The user asked on 2026-11-15 for every talk point to be checked. After the check of each talk point, the user approved the repaired plan on 2026-11-15, chose to refuse old timer calls too, and chose whole-project scope for the other new checks. On 2026-11-15 the user approved the split into three plans and PRs (merge each into develop, one release PR to main, then the other repos) and approved PRs in the installed projects and the user's own packages. On 2026-11-15 the user approved the 12 open proposals of the split plan.

## Acceptance + steps

- [ ] Work starts from the latest main (origin/main c5068084) and rebases on it before each push → N/A — a Git state, not behavior; `git merge-base --is-ancestor origin/main HEAD` exits 0 before the push.
- [ ] The `browser` command installs agent-browser at the newest release at least 2 days old through the mise path of the other tools, plus its Chrome, and changes no project file (Proposal "Hard Eng provisions the tool"; the age hold is `RELEASE_AGE_SECONDS` in `.hooks/tool_setup.py`) → new `tests/test_browser.py::test_installs_like_other_tools`.
- [ ] The `browser` command runs any agent-browser step from the output folder, including its console and page error reads → new `tests/test_browser.py::test_runs_from_output_folder` (a local page with a console error); the added time per step is measured 2 times each way in Verification (planning: 0.015 s raw, 0.06 s through a Python start).
- [ ] Proposal "one browser per agent session": the command refuses a step with no `--session`, refuses `close --all`, and `capture` closes its own session → `tests/test_browser.py::test_refuses_shared_sessions`.
- [ ] The `browser capture` command writes whole-page images at 390 and 1280 px (coordinator mockups line 17) into the output folder, draws a red box over each named element on top of the page (Ship checks line 99), and fails when a name matches nothing, because a missing box would hide the change (AGENTS.md: never hide findings) → `tests/test_browser.py::test_capture_draws_boxes_at_both_widths` (real browser, local page; checks image widths and red pixels on each element box), new `tests/test_browser.py::test_capture_places_fixed_bars_once_at_their_edge` (fixed bars once at their edge, a full-height side bar keeps its size, fixed decorations off the screen do not grow the page).
- [ ] The `browser capture` command hides email addresses and phone numbers in page text and form fields before each image (E2E skill: keep secrets and personal data out of artifacts). Proposal "hides emails and phones only": a pattern match; it misses names and unusual forms. Text in open shadow roots and same-origin frames is hidden too, and each frame, `object` or `embed` it cannot read becomes a grey box; a frame that slips past leaves no image and fails the capture → `tests/test_browser.py::test_capture_hides_emails_and_phones`, new `tests/test_browser.py::test_capture_replaces_frames_it_cannot_read`, new `tests/test_browser.py::test_capture_fails_with_no_image_when_a_frame_slips_past`.
- [ ] The `browser signin` command saves a session file for a role, reading the login page and the names of its environment variables from a new `browser.roles` section of `hard-eng.gates.json`; the password goes on standard input only, never in a command line or the output (E2E skill: keep secrets out of artifacts) → `tests/test_browser.py::test_signin_keeps_password_off_command_line` (local login page).
- [ ] The E2E, Ship and Trello coordinator skills name the command as the one way to drive a browser and capture; Ship and the coordinator link to it, and only the command holds the widths and the box drawing → new `tests/test_browser.py::test_skills_point_to_the_command`, `tests/test_skill_links.py::test_distributed_skill_links_resolve`, `tests/test_skill_routing.py::test_every_request_picks_its_own_skill`.
- [ ] An agent check case proves agents find and use the command: a fixture web app with a sign-in and one changed label, installed from the source under test; the task names no tool. Pass list: a box on the change at both widths, no personal data in the images, no password in the events, no new files in the repository (the Stop hook refuses unplanned files), no browser left running. The case records tokens and steps per run → `tests/test_agent_checks.py::test_browser_proof_judge_fails_each_missing_item`, then `tests/agent_checks.py --case browser-proof --repeat 3` for Claude and Codex, on the old source and the new one; the new source passes every item in each run; the report gives median tokens and steps for each source.
- [ ] Proposal "AGENTS.md": AGENTS.md gets one line only if the evals show agents miss the command in any run; the evals then run again → N/A — a decision read from the agent check results, not a behavior.
- [ ] Proposal "feature map": the case runs with and without a map file; the map ships only with fewer steps or fewer wrong pages; else the result is recorded and the slice is dropped → N/A — a decision read from the agent check results, not a behavior.
- [ ] Each talk point has a row: a second reader that reads only the sources and this plan finds no talk item without a row → N/A — the second reader's report on the `Reviewer:` line proves it.
- [ ] Hot paths: `hard-eng.py hot-paths` lists known slow patterns, such as allocation in a loop, in the files it is given → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [ ] Hard Eng puts gates before prose: HE Learn's preference order puts a deterministic check before a rule, and its Mechanical row turns a repeated correction into a check → N/A — skill text, no code changes; [HE Learn](../../.agents/skills/he-learn/SKILL.md) lines 41 and 57.
- [ ] HE Learn acts on verified repeats only: outside the retro it skips one-off fixes, and the Stop hook counts a second sighting as a repeat → N/A — skill text; [HE Learn](../../.agents/skills/he-learn/SKILL.md) lines 3 and 39.
- [ ] Banned nuanced APIs: a React package must hold the React Doctor gate; a run of its gate command on a sample failed (exit 1) on state copied from props, a timer with no cleanup, a fetch inside an effect and a stale dependency (2026-11-15); a control showed it does not flag every state write inside an effect. Hard Eng adds no ban of its own → `tests/test_setup.py::test_react_and_existing_project_scripts_are_gated`, new `tests/test_gate_tools.py::test_a_react_package_without_its_react_gate_is_refused`.
- [ ] Import bans by folder: a TypeScript package gets a required boundaries gate; a Dart package checks boundaries inside its full scan; the project writes its own bans → `tests/test_setup.py::test_typescript_packages_require_boundary_gate`, `tests/test_setup.py::test_dart_boundary_gate_requires_blocking_project_rules`.
- [ ] Proof media in review: Ship UI evidence needs before and after media for a UI change → `tests/test_shipping_ui_evidence.py::test_ui_changes_reject_missing_foreign_or_duplicate_evidence`.
- [ ] Agents merge their own PRs: HE Ship merges only when the PR head matches the verified head and its checks pass → `tests/test_ship_actions.py::test_ship_merge_matches_verified_head_and_checks_result`.
- [ ] Research answered in chat on 2026-11-15 before this plan: tool trials, latest versions, other tools, Cloudflare, token cost, advisor checks → N/A — answers, not code; limits kept in Risks.
- [ ] No private project data in the plan, code, tests, commits or PR text: a search of the branch diff, the commit messages and the PR text for private names, paths and contact data finds 0 before each push (publication privacy, Ship checks) → N/A — a text check run before each push; test data uses example.com addresses and fiction phone ranges.
- [ ] A draft PR claims the work: before work, the open PRs, remote branches, local worktrees and recent sessions of the repository are checked, and a draft PR holds the plan from the start → N/A — a process step; PR 636 opened as the claim on 2026-11-15.
- [ ] Delivery order: this PR merges into develop first; the strict-refusals and architecture PRs merge into develop next; one release PR then takes develop to main; the other repositories follow → N/A — a delivery order; the Delivery line below records it.
- [ ] The repository description names no place where agents run, because Hard Eng also runs in CI and on remote machines → N/A — a GitHub setting; `gh repo view --json description` shows the new text.
- [ ] Each OS, worktrees and a remote machine: the browser tests pass on macOS and on a plain Linux machine reached over SSH with no display, from an empty tool folder with parallel workers; `signin` and `capture` work from a linked worktree of an installed project; two worktrees that use the same `--session` name at the same time do not end each other's browser; Windows gets a recorded result, and no Windows code is added here. Faults found there get failing tests first: parallel first runs install Chrome once, install output stays off standard output, and `--no-sandbox` is refused while a Linux with the user namespace limit gets the root step → new `tests/test_browser.py::test_parallel_first_runs_install_chrome_once`, new `tests/test_browser.py::test_refuses_switching_off_the_sandbox`, `tests/test_browser.py::test_installs_like_other_tools`, new `tests/test_browser.py::test_each_tool_path_installs_chrome_once`, new `tests/test_browser.py::test_same_session_name_in_two_checkouts_stays_apart`; the machine runs are recorded one line each in Verification.
- [ ] One run on a private project's live site (Proposal "read only, test admin account, sign out"): sign in, capture at both widths, sign out → N/A — a live run that no test can repeat; HE-REAL-SERVICE-RUN, Real service line below.

Review declined: personal data in closed shadow roots, canvas, images or video, or on a page that works against the capture, such as a frame that appears and goes within milliseconds around the screenshot :: no page script can read those, and a check before and after each image cannot see between them; hiding is a pattern match over page text (Proposal "hides emails and phones only"), each frame it cannot read becomes a grey box, a frame that slips past fails the capture, and the E2E browser reference tells agents to look at each image and use fake data.

Review declined: the browser-proof judge misses moved images whose link holds a space or a URL escape :: the judge is a test tool, not shipped code; the agent names the folder it moves images to, and every failed eval run is read by hand before a result is recorded, so a wrong fail cannot pass unseen.

## Baseline + execution

Result: Passed
Evidence: 2026-11-15, `python3 .hooks/hard-eng.py check --plan-stage Draft` on the starting code (origin/main c5068084): base commit 33e40da3 passed the required CI checks; only the plan changed, so the secret scan ran and passed; exit 0.
Execution: one Sonnet builder for the command, its tests and the skill edits, first slice = install plus `capture` on a local page. Then the planner runs the agent check case for both clients and the live run. A fresh Codex review through `hard-eng.py challenge` before the Complete gate.

## Risks + recovery

- The tool ships several times a week and can break a step. Recovery: the 2-day age hold, and the reinstall of the newest release that `provision_latest` already does for a broken release.
- The Codex `workspace-write` sandbox stops every Chrome, Playwright's too (tested 2026-11-15: Chrome needs macOS services the sandbox denies). Recovery: the E2E skill tells Codex to run browser steps outside the sandbox with approval; a full-access Codex worked.
- The agent check harness keeps Bash sandboxed, and no sandbox starts Chrome. Recovery: the `browser-proof` case alone runs at the access level "approved": Codex with `--approve-for-me` and Claude in auto mode, so an automatic reviewer stands in for the user's approval to leave the sandbox; both sources of one client get the same access, and `tests/test_agent_checks.py::test_only_the_browser_case_may_leave_the_sandbox` keeps every other case sandboxed. A Claude trial in the sandbox (2026-11-15) could not install the tool, and it printed the sign-in file while exploring; the E2E skill now says never to open that file.
- About 1.5 GB of memory per open browser (1.0 GB for Playwright CLI). Recovery: `capture` closes its own session.
- A real-browser test can push the Hard Eng test gate near its time limit. Recovery: measure in the build; move it to its own shard if needed.
- Ubuntu 23.10 and later limit user namespaces through AppArmor, so the downloaded Chrome cannot start its sandbox, and the tool's own hint says to pass `--no-sandbox` (seen 2026-11-15 on Ubuntu 26.04, host and VM). Recovery: the command refuses `--no-sandbox` and prints a one-time root step that adds an AppArmor profile for the downloaded Chrome; Hard Eng never runs sudo on a person's machine. GitHub's Ubuntu runners keep the limit too (since about the 2026-10-18 image), so Hard Eng's own test job runs the same `root_step()` before its tests; the shared workflow template for installed projects does not change. Chrome as root in a container has no fix that keeps the sandbox, so it is not supported.
- Parallel first runs raced on the Chrome download ("Text file busy"), and install output reached standard output. Recovery: one install at a time under a file lock, install output on standard error.
- Limits of the research: one run per tool in the trials; macOS only; the Chrome DevTools CLI judged from its help text only; Reddit not read.

## ux_reference

N/A — no product screen changes; the images the command makes are evidence for agents and reviewers, not a user interface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — the `browser-proof` agent check case through real Claude and Codex sessions, 3 runs each, with the pass list above; plus `tests/test_browser.py` through a real browser.
Real service: Required — a private project's live site with its test admin account: `browser signin`, `browser capture` at both widths, then sign out through the app. Read only; no writes.
Retro: Pending

Delivery target: Merge into develop, then one release PR from develop to main after the strict-refusals and architecture plans also merge into develop; Delivery: Pending — PR checks green and merged into develop.
