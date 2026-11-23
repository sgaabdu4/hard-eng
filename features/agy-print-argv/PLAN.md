# Fix the agy reviewer command and let look fall back when a reviewer cannot run

Status: Ready

## Outcome + scope

`challenge` reaches `agy` again: its command attaches the prompt to the print flag. `look` tries the next supported reviewer when one exits non-zero, then a fresh session of the host agent. The canary command for `agy` gets the same print form. Non-goals: adding `agy` to `look`, retrying a review that ran but gave a bad answer, changing the proof rules of `look`.

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

Result: Pending
Evidence: Pending
E2E: N/A — no user journey changes.
Real service: Required — agy 1.5.15: `challenge` on this branch, and one `look` run on an invented image while Codex is out of quota
Retro: Pending
Delivery target: Merge
Delivery: Pending
