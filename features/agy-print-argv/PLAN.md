# Fix the agy reviewer command and let look fall back when a reviewer cannot run

Status: Complete

## Outcome + scope

`challenge` reaches `agy` again: its command attaches the prompt to the print flag, and its session settings use `agentMode` `plan`, because agy 1.5.15 refuses `default` (valid: `accept-edits`, `auto`, `plan`). `look` tries the next supported reviewer when one exits non-zero, then a fresh session of the host agent. The canary command for `agy` gets the same print form. Non-goals: adding `agy` to `look`, retrying a review that ran but gave a bad answer, changing the proof rules of `look`.

## Sources + coverage

Sources: N/A — the request is the failing `challenge` and `look` runs on this Mac while Codex is out of quota; no user source.
Deliverables: None

## Repository context

Owners: `.hooks/challenge.py` (`command`), `release_canary.py` (`agent_command`), `.hooks/look.py` (`reviewer_attempts`, `run_first_reviewer`, `run_reviewer`, `review`).
Same cause: `agy` 1.5.15 reads the word after `-p` as the prompt. The canary command had the same order (`agy -p --dangerously-skip-permissions <task>`), so it gets the same fix. Searched the hooks for `"-p"` in agent commands: no other agent command is built for `agy`.
Single source: N/A — no value gains a second copy; the `look` fallback reuses `reviewers_for` order.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user's standing rule: merge each task PR once its checks pass; this hotfix unblocks every installed project's review.

## Acceptance + steps

- [x] The `agy` reviewer command attaches the prompt to the print flag and has no bare `-p` → `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings`
- [x] The session settings use `agentMode` `plan` → `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings`. Real agy with the pinned model and the same other keys: `plan` ran git and a file read and blocked a shell write outside the repo; `auto` allowed that write. `accept-edits` was not compared. A second fault, found by the first real `challenge` run: `agentMode: unrecognized value "default"`.
- [x] The models overlay still sets the `agy` model flags in front → `tests/test_challenge.py::test_challenge_honors_local_models_overlay_for_order_and_flags`
- [x] The canary command for `agy` attaches the prompt; the `claude` command is unchanged → `tests/test_release_canary.py::test_agent_command_supports_agy`
- [x] `look` falls back to a fresh same-agent session when the other agent exits non-zero → `tests/test_look.py::test_look_falls_back_when_the_other_agent_cannot_run`
- [x] `look` does not replace a review that ran with no VERDICT line → `tests/test_look.py::test_look_does_not_replace_a_bad_review_with_a_retry`
- [x] The attempt list keeps the old choice when no agent is installed → `tests/test_look.py::test_look_passes_models_json_flags_and_supports_agy_host_fallback`

## Baseline + execution

Result: Passed
Evidence: 2026-11-23, main ce348c30: `agy -p --model x "Reply ok"` exits 2 (`-p took "--model" as its prompt`), and `agy -p="Reply with the single word ok."` prints `ok`. The argv test failed before the change. Codex is out of quota until 2026-11-28, so every `challenge` and `look` on a Claude host failed.
Execution: One builder, this session.

## Risks + recovery

A later `agy` release may change the print flag again. The argv test names the form, and a revert restores the old command.

## ux_reference

N/A — hooks only; no visible UI.

## Verification

Result: Passed
Evidence: 2026-11-23 on this branch. Red first: the agy argv test failed on `-p` before the fix; the fresh-host test and the three-reason test failed before the `challenge` change. Focused tests: `tests/test_challenge.py`, `tests/test_look.py` and `tests/test_release_canary.py`, 129 passed; `tests/test_skill_links.py` 13 passed. Static gates with the commands of `hard-eng.gates.json`: format, lint, complexity, annotations, types and dead-code exit 0. The test setup now puts failing fakes of all three agent CLIs first on PATH, because four tests reached the real `claude` CLI once the fallback existed, and one ran a real review. Real `look` on an invented image, twice: Codex exited 1, a fresh Claude session opened the image and wrote a record; the second record holds the real limit text from the Codex JSON error row. `skipped` is a new look record key and `fresh` a new challenge record key; each says why the host ran, and neither reaches the PR block or `ship`.
E2E: N/A — no user journey changes.
Real service: Passed — agy 1.5.15, Codex and Claude CLIs: `challenge` on d6019c86 ran all three. Codex answered its usage limit (exit 1). agy took the new command and answered `RESOURCE_EXHAUSTED (code 429)` (exit 3); before the fix it exited 2 on `-p took "--model" as its prompt`. A fresh Claude session then reviewed and printed `VERDICT: clean`. Earlier, before the quota ran out, real agy in `plan` mode ran git and a file read and blocked a shell write. A full agy verdict waits for its quota reset (about 126 hours from 2026-11-23).
Retro: (1) agy 1.5.15 read the word after `-p` as the prompt → `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings` and `tests/test_release_canary.py::test_agent_command_supports_agy` (outside cause: an agy release). (2) agy 1.5.15 refused `agentMode` `default` → the same agy test. (3) `look` stopped when the other agent exited non-zero → `tests/test_look.py::test_look_falls_back_when_the_other_agent_cannot_run`. (4) User correction: reviews must not block when Codex and agy are out → `tests/test_challenge.py::test_challenge_falls_back_to_a_fresh_host_session_when_every_other_agent_fails`. (5) Four challenge tests reached the real `claude` CLI → the `branch` fixture in `tests/test_challenge.py` fakes every agent CLI. (6) The Ready check ran before the `agentMode` commit → None — the Complete check runs at the final head.
Delivery target: Merge
Delivery: Pending
