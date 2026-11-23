# Let reviews fall back to a fresh host session when no other agent can run

Status: Complete

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
- [x] `challenge` prints `Review by a fresh <host> session at <sha>: <outcome>` for a fresh host review, never `Independent review` → `tests/test_challenge.py::test_challenge_falls_back_to_a_fresh_host_session_when_every_other_agent_fails`
- [x] `ship` names a fresh host review as such, never as independent → `tests/test_challenge.py::test_challenge_falls_back_to_a_fresh_host_session_when_every_other_agent_fails`
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

Result: Passed
Evidence: 2026-11-23 on this branch. Red first: the fresh-host test and the three-reason test failed before the `challenge` change; the look fallback test failed before the `look` change. Focused tests: `tests/test_challenge.py`, `tests/test_look.py`, `tests/test_release_canary.py` and `tests/test_skill_links.py`, 142 passed. The `branch` fixture in `tests/test_challenge.py` puts failing fakes of all three agent CLIs first on PATH, because four tests reached the real `claude` CLI once the fallback existed. After the review fix: `tests/test_challenge.py`, `tests/test_look.py` and `tests/test_skill_links.py`, 90 passed; the label test failed first on `Independent review by claude: clean`. Second hotfix, 2026-11-23: the headline test failed first on the old `Independent review by claude at <sha>` line; then `tests/test_challenge.py` and `tests/test_look.py`, 77 passed.
E2E: N/A — no user journey changes.
Real service: Passed — Codex, agy and Claude CLIs, `challenge` and `look` at 3d970a2c. Codex exited 1 with its usage limit on the last stderr line, as the fake's exit 1 and error line. agy exited 2 on the old `-p` form with its message on the last stderr line, the same shape. A fresh Claude session then exited 0 and its last line was the exact `VERDICT: findings`, as the fake's last line. `look`: Codex failed and `skipped` holds its real limit text, read from the JSON error row the fake `turn.failed` row copies; a fresh Claude session opened the invented image and wrote a record with `fresh_same_agent` true and one line per rule. No refusal was caused on purpose; the quota refusals came from the services.
Retro: (1) User correction: reviews must not block when Codex and agy are out → `tests/test_challenge.py::test_challenge_falls_back_to_a_fresh_host_session_when_every_other_agent_fails`. (2) `look` stopped when the other agent exited non-zero → `tests/test_look.py::test_look_falls_back_when_the_other_agent_cannot_run`. (3) Four challenge tests reached the real `claude` CLI → the `branch` fixture in `tests/test_challenge.py` fakes every agent CLI. (4) Review: a fresh host review showed in `ship` as independent → the same fresh-host test checks the `ship` line. (6) Review of the develop join: `challenge` still printed `Independent review by claude` for a fresh host review, and a separate project's coordinator repeated that line → the same fresh-host test now checks the headline; the earlier round had noted it as not a finding, so a noted mislabel is now treated as a finding. (5) Review: the first plan wrote `Real service: Passed` for agy with no agy verdict → None — the agy fix moved to its own branch, held as Draft until a real agy verdict.
Delivery target: Merge
Delivery: Pending
