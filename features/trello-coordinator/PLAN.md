# Optional Trello coordinator skill

Status: Complete

## Outcome + scope

A project with a `trello.json` file gets an optional `trello-coordinator` skill: one scheduled coordinator run reads the Trello board through the REST API with a key + token from a gitignored `.env.trello.local`, reports every item that needs an answer or action, and acts through one stdlib script; on-demand Hard Eng guidance gains the generic usability, tone, triage and release rules learned from a live coordinator. Non-goals: an always-on service or webhooks, an MCP server, a proof-gate hook, removing build tools from the coordinator, a watchdog script, an automatic Sentry fix loop, scheduling owned by Hard Eng, changes to projects other than a trial copy of one private project.

## Repository context

Owners: stack skill detection `.hooks/agent_hooks.py::integrated_services` + `setup.py::STACK_SKILLS`/`unused_skills`; scaffold file set `.hooks/update.py::scaffold_files`/`without_skills`; integrations `.agents/skills/he/references/integrations.md`; planning UX `.agents/skills/he-plan/references/ux.md`; product template `.agents/skills/he/templates/PRODUCT.md`; workflow `.agents/skills/he/references/workflow.md`; shipping checks `.agents/skills/he-ship/references/checks.md`; skill authoring `.agents/skills/writing-great-skills/SKILL.md`.
Same cause: N/A — new optional capability; no earlier Hard Eng fix. Source evidence: a private project's coordinator (rules file, board scripts, 10-part thread history 21 Oct to 5 Nov 2026) and its failure log; Trello REST docs (key + token for unattended jobs, 100 requests/10 s per token, `filter=all`, edits send no mentions reliably); the official Trello MCP (OAuth only, no upload, no activity log) and DeepSeek's dsh-superagent prototype (router never works, code gate before model, follow-ups to the same worker, a healthy state takes no space).

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-05 approved the plan in chat ("go"): optional `trello-coordinator` skill, key + token in a gitignored env file, config in `trello.json`, roles/models/timing configurable with reasons, host-native scheduling (T3 Code, Claude Code, Codex), confusion → simplify the app, trial on a private trial project. No commit or push without approval (AGENTS.override.md). PR targets `develop`.
Decision: secrets file = `.env.trello.local` (both known consumers already ignore it); the script refuses to run when git does not ignore it. The script finds the main checkout through `git rev-parse --git-common-dir`, so worktrees need no copy; state, posted-comment log and lock live under the common git dir (`trello-coordinator/`), never tracked and shared by worktrees on one machine.
Decision: the account behind the token posts as the owner (same as the source project); the script checks the account matches `trello.json` before any write.
Decision: `check` only reads and reports; writes are explicit commands (`comment`, `move`, `label`, `upload`, `download`). Comments are always new, never edits (Trello edits notify nobody). A move into the testing list needs proof images.
Decision: a comment counts as a request only when its author is in `trello.json` allowed members; every other comment is information. The script decides this, not the model.
Decision: rules land as on-demand guidance text without new HE- IDs; nothing new in AGENTS.md. Tap size = at least 24 px everywhere, platform number for native apps. Tone default = calm, positive, no blame, in the product template, changeable per project.

## Acceptance + steps

- [x] A repository with `trello.json` reports Trello as integrated and setup installs `trello-coordinator`; one without it does not → `tests/test_trello_coordinator.py::test_trello_json_installs_the_skill_only_when_present`.
- [x] The script refuses to run when git does not ignore `.env.trello.local`, and reads the main checkout's file from a worktree → `tests/test_trello_coordinator.py::test_secrets_file_must_be_ignored_and_is_found_from_a_worktree`.
- [x] Output, errors and logs never contain the key or token → `tests/test_trello_coordinator.py::test_key_and_token_never_printed`.
- [x] `trello.json` holding a key-like value is refused → `tests/test_trello_coordinator.py::test_config_with_a_secret_is_refused`.
- [x] A token for another account than `trello.json` names is refused before any write → `tests/test_trello_coordinator.py::test_wrong_account_is_refused`.
- [x] `check` lists unanswered comments of any age, new images and description edits, owner comments the tool did not post, promises older than the configured hours, requests silent past the chase hours, tags that reach nobody, Needs labels without an open question, testing cards whose newest coordinator comment says they wait on us, and cards without a number → `tests/test_trello_coordinator.py::test_check_reports_every_missed_item` (fake Trello built from recorded API shapes).
- [x] A comment from a member outside `allowed` is reported as information, never as a request → `tests/test_trello_coordinator.py::test_only_allowed_members_make_requests`.
- [x] `check` reads activity with `filter=all` and `since`, and retries a 429 after the wait the rate headers allow → `tests/test_trello_coordinator.py::test_activity_query_and_rate_limit_retry`.
- [x] `comment` always posts a new comment, logs its id, and refuses text with an email address or phone number → `tests/test_trello_coordinator.py::test_comment_posts_new_and_blocks_private_data`.
- [x] `move` to the testing list without proof images is refused; with them it uploads, then moves to the top → `tests/test_trello_coordinator.py::test_testing_move_needs_proof`.
- [x] A second run while one holds the lock exits without writes; state saves atomically → `tests/test_trello_coordinator.py::test_one_run_at_a_time`.
- [x] The skill states host-native scheduling for T3 Code, Claude Code and Codex, roles/models/timing from `trello.json` with reasons, a stop when a configured model is unavailable, and the confusion → simplify loop → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop` + reader review (writing-great-skills).
- [x] The CLI matches the command contract in the skill reference → `tests/test_trello_coordinator.py::test_cli_matches_the_reference_contract`.
- [x] Usability, tone, Sentry triage, release and never-yes-man guidance is reachable from its owners, and always-installed skills name the optional skill by plain name only → `tests/test_skill_links.py::test_distributed_skill_links_resolve` + `tests/test_skill_links.py::test_installed_skill_links_resolve_without_stack_skills`.
- [x] Real board journey: the script from this worktree, run in a scratch project worktree holding an uncommitted `trello.json`, `probe` names the expected account and `check` returns the six lists and a report without writes → N/A — no repository test can reach a real board without its private key; the dry run and its output are recorded under Verification E2E.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on branch point origin/main 0128d78a: base commit 217cc394 passed required CI, so only the secret scan ran; it passed, exit 0.
Execution: One builder (Sonnet) for script, detection and tests; skill and guidance text written against writing-great-skills with a fresh reader subagent; one fresh Opus reviewer before ship; trial run by this session.

## Risks + recovery

Board writes reach real people → `check` never writes, every write is an explicit command, and the trial wrote only to its own test cards. A leaked token reaches the whole account → secrets file ignored + refused otherwise, never printed, revocable in Trello account settings.

## ux_reference

N/A — skill, script and guidance text; no visible UI.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Ready` exit 0, 2258 tests passed; 63 focused coordinator, board and routing tests passed.
E2E: Passed — three coordinator runs on a private trial board, six test cards. `probe` named the expected account and lists. `check` reported every planted item; the coordinator answered each card, closed one on the owner's reply, posted a mockup, built only after a plain yes and stopped a second worker in one worktree. Gaps found (lost owner replies with no first-check time, labels on any tag, repeated `--image`, worker notes in a tracked file, stalled-worker overlap, no security review for personal data) are fixed, each script fix with a failing-first test.
Delivery target: PR
Delivery: Pending — PR into develop after approval to commit and push.
