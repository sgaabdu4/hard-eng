# Let reviews fall back to a fresh host session when no other agent can run

Status: Ready

## Outcome + scope

`challenge` tries a fresh read-only session of the host agent last, when every other agent fails, records why and prints it. `look` tries the next supported reviewer when one exits non-zero, then a fresh session of the host agent, and records the real failure text from a Codex JSON error row. Non-goals: changing the `agy` command (its own branch waits for a real agy verdict), retrying a review that ran but gave a bad answer, changing the proof rules of `look`.

## Sources + coverage

Sources: the user's message of 2026-11-23, read in full: "It's fine to use opus as adversarial reciewer if codex or aft is not available, we shouldn't be blocked".
Reviewer: N/A — one short source.
Deliverables: None

- User message, a fresh host session reviews when Codex and agy cannot: In scope — `challenge` falls back to a fresh host session when every other agent fails

## Repository context

Owners: `.hooks/challenge.py` (`challenge`), `.hooks/look.py` (`reviewer_attempts`, `run_first_reviewer`, `run_reviewer`, `failure_message`, `review`).
Same cause: both review commands stopped when the other agents could not run. `look` already had a fresh-session fallback, but only for a missing CLI; `challenge` had none. Both now fall back on a failed run. Searched `.hooks` for other agent-review callers: none.
Single source: N/A — the order of the other agents stays in `reviewers_for`; both commands add the host last.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user's message of 2026-11-23 quoted above, and the user's standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [x] `challenge` falls back to a fresh host session when every other agent fails, records why, and prints it → `tests/test_challenge.py::test_challenge_falls_back_to_a_fresh_host_session_when_every_other_agent_fails`
- [x] `challenge` does not call the host when another agent completes → `tests/test_challenge.py::test_challenge_falls_back_to_second_reviewer_when_first_fails`
- [x] `challenge` records `not done` with every reason when all three fail → `tests/test_challenge.py::test_unavailable_reviewer_records_not_done`
- [x] `look` falls back to a fresh same-agent session when the other agent exits non-zero → `tests/test_look.py::test_look_falls_back_when_the_other_agent_cannot_run`
- [x] `look` does not replace a review that ran with no VERDICT line → `tests/test_look.py::test_look_does_not_replace_a_bad_review_with_a_retry`
- [x] The attempt list keeps the old choice when no agent is installed → `tests/test_look.py::test_look_passes_models_json_flags_and_supports_agy_host_fallback`

## Baseline + execution

Result: Passed
Evidence: 2026-11-23, main ce348c30: Codex answered its usage limit and agy exited 2 on its command, so every `challenge` and `look` on a Claude host ended `not done`. The fallback tests failed before the change.
Execution: One builder, this session.

## Risks + recovery

A host review is less independent than another agent's. The record keeps `fresh` with the reasons, and the command prints them. A revert restores the old order.

## ux_reference

N/A — hooks only; no visible UI.

## Verification

Result: Pending
Evidence: 2026-11-23 on this branch. Red first: the fresh-host test and the three-reason test failed before the `challenge` change; the look fallback test failed before the `look` change. Focused tests: `tests/test_challenge.py`, `tests/test_look.py`, `tests/test_release_canary.py` and `tests/test_skill_links.py`, 142 passed. The `branch` fixture in `tests/test_challenge.py` puts failing fakes of all three agent CLIs first on PATH, because four tests reached the real `claude` CLI once the fallback existed.
E2E: N/A — no user journey changes.
Real service: Required — Codex, agy and Claude CLIs: `challenge` and one `look` at the final head; compare each refusal and the fresh Claude verdict with the fakes.
Retro: Pending
Delivery target: Merge
Delivery: Pending
