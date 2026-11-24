# Fix the agy reviewer command

Status: Ready

## Outcome + scope

`challenge` reaches `agy` again: its command attaches the prompt to the print flag, and its session settings use `agentMode` `plan`, because agy 1.5.15 refuses `default` (valid: `accept-edits`, `auto`, `plan`). The canary command for `agy` gets the same print form. The fallback order of `challenge` stays as main has it: the other agents first, a fresh host session only when all of them are unavailable, and findings never cause a fallback. Non-goals: any change to `look`, which another hotfix owns; adding `agy` to `look`; changing the fallback rules.

## Sources + coverage

Sources: N/A — the request is the failing `challenge` run on this Mac while Codex is out of quota; no user source.
Deliverables: None

## Repository context

Owners: `.hooks/challenge.py` (`command`, `agy_read_only_settings`), `release_canary.py` (`agent_command`).
Same cause: `agy` 1.5.15 reads the word after `-p` as the prompt. The canary command had the same order (`agy -p --dangerously-skip-permissions <task>`), so it gets the same fix. Searched the hooks for `"-p"` in agent commands: no other agent command is built for `agy`.
Single source: N/A — no value gains a second copy.

## Decisions + authorization

Blockers: None. The earlier `RESOURCE_EXHAUSTED (code 429)` answer from agy ended: on 2026-11-24 a real `agy -p="Reply with the single word ok."` printed `ok`. The real run still needs the line `Independent review by agy at <sha>` with a verdict.
Handoff: Clarification
Authority: Autonomous — the user asked on 2026-11-24 to fix the agy launcher, prove a real agy challenge, and release this scoped fix through every normal gate.

## Acceptance + steps

- [x] The `agy` reviewer command attaches the prompt to the print flag and has no bare `-p` → `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings`
- [x] The session settings use `agentMode` `plan` → `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings`. Real agy with the pinned model and the same other keys: `plan` ran git and a file read and blocked a shell write outside the repo; `auto` allowed that write. `accept-edits` was not compared. A second fault, found by the first real `challenge` run: `agentMode: unrecognized value "default"`.
- [x] The models overlay still sets the `agy` model flags in front → `tests/test_challenge.py::test_challenge_honors_local_models_overlay_for_order_and_flags`
- [x] The canary command for `agy` attaches the prompt; the `claude` command is unchanged → `tests/test_release_canary.py::test_agent_command_supports_agy`
- [x] `challenge` tries the other agents first, in `models.json` order → `tests/test_challenge.py::test_challenge_honors_local_models_overlay_for_order_and_flags`
- [x] A fresh host session runs only when every other agent is unavailable → `tests/test_challenge.py::test_challenge_falls_back_to_second_reviewer_when_first_fails` and `tests/test_challenge.py::test_challenge_falls_back_to_a_fresh_host_session_when_every_other_agent_fails`
- [x] Findings never cause a fallback → `tests/test_challenge.py::test_findings_never_send_the_review_to_another_agent`

## Baseline + execution

Result: Passed
Evidence: 2026-11-23, main ce348c30: `agy -p --model x "Reply ok"` exits 2 (`-p took "--model" as its prompt`), and `agy -p="Reply with the single word ok."` prints `ok`. The argv test failed before the change. Codex is out of quota until 2026-11-28, so every `challenge` and `look` on a Claude host failed.
Execution: One builder, this session.

## Risks + recovery

A later `agy` release may change the print flag again. The argv test names the form, and a revert restores the old command.

## ux_reference

N/A — hooks only; no visible UI.

## Verification

Result: Pending
Evidence: 2026-11-24 on this branch, rebased on main 009927fb. Red first: the agy argv test failed on `-p` before the fix (2026-11-23); the new findings test failed against a loop that also fell back on findings. Focused tests: `tests/test_challenge.py` and `tests/test_release_canary.py`, 108 passed.
E2E: N/A — no user journey changes.
Real service: Required — agy 1.5.15: `challenge` on this branch must print `Independent review by agy at <sha>` with a verdict; a clean line from the fresh host fallback does not count. On 2026-11-24 a real `agy -p="Reply with the single word ok."` printed `ok`, so the 429 limit has ended. Before the fix agy exited 2 on `-p took "--model" as its prompt`. Earlier, real agy in `plan` mode ran git and a file read and blocked a shell write.
Retro: (1) agy 1.5.15 read the word after `-p` as the prompt → `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings` and `tests/test_release_canary.py::test_agent_command_supports_agy` (outside cause: an agy release). (2) agy 1.5.15 refused `agentMode` `default` → the same agy test. (3) The rule that findings never cause a fallback had only indirect proof → `tests/test_challenge.py::test_findings_never_send_the_review_to_another_agent`.
Delivery target: Merge
Delivery: Pending
