# Fix the agy reviewer command

Status: Complete

## Outcome + scope

`challenge` reaches `agy` again: its command attaches the prompt to the print flag, and its session settings use `agentMode` `plan`, because agy 1.5.15 refuses `default` (valid: `accept-edits`, `auto`, `plan`). The canary command for `agy` gets the same print form. The fallback order of `challenge` stays as main has it: the other agents first, a fresh host session only when all of them are unavailable, and findings never cause a fallback. Non-goals: any change to `look`, which another hotfix owns; adding `agy` to `look`; changing the fallback rules.

## Sources + coverage

Sources: the user's request of 2026-11-24, as the sub-task brief states it: fix the agy launcher, prove a real agy challenge, and release this scoped fix through every normal gate.
Reviewer: N/A — one short source.
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
- [x] A fresh host session runs only when every other agent is unavailable (not installed, non-zero exit, or no VERDICT line) → `tests/test_challenge.py::test_an_agent_that_is_not_installed_passes_the_review_to_the_next_one`, `tests/test_challenge.py::test_challenge_falls_back_to_second_reviewer_when_first_fails` and `tests/test_challenge.py::test_challenge_falls_back_to_a_fresh_host_session_when_every_other_agent_fails`
- [x] Findings never cause a fallback → `tests/test_challenge.py::test_findings_never_send_the_review_to_another_agent`

## Baseline + execution

Result: Passed
Evidence: 2026-11-23, main ce348c30: `agy -p --model x "Reply ok"` exits 2 (`-p took "--model" as its prompt`), and `agy -p="Reply with the single word ok."` prints `ok`. The argv test failed before the change. Codex is out of quota until 2026-11-28, so every `challenge` and `look` on a Claude host failed.
Execution: One builder, this session.

## Risks + recovery

A later `agy` release may change the print flag again. The argv test names the form, and a revert restores the old command.
Not checked: a full release canary run with `agy` and its real task; only the command form ran for real, with a one-word prompt.

## ux_reference

N/A — hooks only; no visible UI.

## Verification

Result: Passed
Evidence: 2026-11-24 on this branch, rebased on main 009927fb. Red first: the agy argv test failed on `-p` before the fix (2026-11-23); the new findings test failed against a loop that also fell back on findings, and the new not-installed test failed with that cause removed from `unavailable()`. Focused tests: `tests/test_challenge.py` and `tests/test_release_canary.py`, 109 passed. `check --base origin/main --plan-stage Ready` at 05f82af7 exit 0: every gate passed, 7674 tests passed. Full check: the `check --plan-stage Complete` run on the final head and the CI runs of the PR.
E2E: N/A — no user journey changes.
Real service: Passed — agy 1.5.16, 2026-11-24: a real `agy -p="Reply with the single word ok."` printed `ok`, so the 429 limit had ended. Then `challenge` on this branch, with agy first in a temporary machine-local `challenge_order` overlay (removed after the run), printed `Independent review by agy at 05f82af706208293a77df9206abb5d6a547d994d: clean`. The reviewer text names the command line of its own session: `--print=...` and `agentMode` `plan`. The canary command form ran for real in an empty scratch folder: `agy --dangerously-skip-permissions "--print=Reply with the single word ok."` exited 0 and printed `ok`; the old form `agy -p --dangerously-skip-permissions <prompt>` exited 2 with `-p took "--dangerously-skip-permissions" as its prompt`. Fake against real: the test fake prints review text, then a last `VERDICT:` line, and exits 0; real agy printed its review text on stdout, ended with `VERDICT: clean`, and exited 0, which are the only fields `challenge` reads. Handled refusals seen for real: exit 2 on the old argument form and exit 3 on the 429 limit; `challenge` treats each non-zero exit as unavailable and tries the next reviewer. Before the fix agy exited 2 on `-p took "--model" as its prompt`. Earlier, real agy in `plan` mode ran git and a file read and blocked a shell write.
Retro: (1) agy 1.5.15 read the word after `-p` as the prompt → `tests/test_challenge.py::test_agy_reviewer_runs_read_only_with_session_settings` and `tests/test_release_canary.py::test_agent_command_supports_agy` (outside cause: an agy release). (2) agy 1.5.15 refused `agentMode` `default` → the same agy test. (3) The rule that findings never cause a fallback had only indirect proof → `tests/test_challenge.py::test_findings_never_send_the_review_to_another_agent`. (4) The "not installed" cause of a fallback had no test that failed without it → `tests/test_challenge.py::test_an_agent_that_is_not_installed_passes_the_review_to_the_next_one`.
Delivery target: Merge
Delivery: Pending — CI, then the merge into `main` and the join of `main` into `develop`.
