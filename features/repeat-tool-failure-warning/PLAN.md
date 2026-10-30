# Warn on a repeated tool error, not on every failure

Status: Complete

## Outcome + scope

The Claude failure hook adds context only when the same tool error happens a third time in a session, and the Stop check no longer counts failures with empty output as one repeat. Non-goals: blocking tool calls, Codex (it has no failure event), counting across sessions.

## Repository context

Owners: `.hooks/agent_hooks.py` (`handle_event` failure branch); `.hooks/failures.py` holds `repeat_note` and the new `failure_context`, because `agent_hooks.py` would pass the 1,000-line limit (HE-FILE-LENGTH); tests in `tests/test_failures.py`, `tests/test_agent_hooks.py` and `tests/test_stop_checks.py`; model eval in `tests/agent_checks.py`.
Same cause: one cause, a failure note that cannot tell a first failure from a loop. `features/repeat-failure-record` keyed Stop failures (helped; a later fix, #433, keyed lines with no fail/error word). Empty output still hashes to one key: `.hard-eng/failures.json` here holds that key with count 41. Replay of 138 local Claude sessions (each call counted once): 1,061 failure notes now; a third-identical-error rule gives 20 warnings, about 13 real loops, 3 false alarms, 4 unclear. Agents opened HE Learn after 14 of 128 repeats, with no clear drop in the error coming back.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid approved building the third-repeat warning on 2026-10-30 ("Yes, build it") after the replay, and asked for a gpt-6-astra Codex adversarial review loop before any PR, fixing genuine substantial findings only.
Decided: key = tool name, subagent id and the error text with numbers, hex runs and UUIDs masked; counts live in the session's existing `.hard-eng/sessions/<id>.json`, written only when that file exists. Left out: interrupts, user or permission refusals, hook errors, timeouts and errors with no text beyond an exit code. Warn from the third sighting on; earlier failures add nothing.

## Acceptance + steps

- [x] A first and second identical tool error add no context; the third adds the warning without echoing the error text → `tests/test_failures.py::test_failure_hook_warns_on_the_third_identical_error`.
- [x] Refusals, interrupts, timeouts and bare exit codes never count → `tests/test_failures.py::test_failure_hook_ignores_errors_that_are_not_agent_mistakes`.
- [x] A session with no recorded state still answers without writing anything → `tests/test_agent_hooks.py::test_failure_checkpoint_preserves_results_without_running_checks`.
- [x] A failed Stop check with no output is never named a repeat → `tests/test_stop_checks.py::test_failures_with_no_output_are_not_counted_as_repeats`.
- [x] The `repeat-failure` eval passes an agent that stops within four runs and reports the failure, and fails one that loops or keeps retrying → `tests/test_agent_checks.py::test_repeat_failure_needs_the_agent_to_stop_and_report`; the live Haiku runs are recorded under Verification.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on `251f2656` (develop, CI passed) → exit 0; only this plan changed, so only the secret scan ran.
Execution: One builder, this session. Failing tests first, then the hook change; the empty-output fix is its own commit.

## Risks + recovery

- A real loop whose error text changes each try (a new temp path) is missed. Recovery: mask that part if real sessions show it.
- Parallel failed calls can race on the session file and lose a count. Writes replace the file whole, so a race costs a missed warning, never a broken file.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_failures.py tests/test_agent_hooks.py tests/test_stop_checks.py tests/test_agent_checks.py` → 159 passed; each new test failed before its fix. Codex adversarial review (gpt-6-astra, against `develop`) → two rounds, no material findings. Haiku eval `agent_checks.py --client claude --model haiku --case repeat-failure --repeat 3`: with Hard Eng 3 of 3 passed, each stopping after 4 runs; `--bare` 1 of 3 passed (8, 1 and 5 runs). An earlier round, re-judged after the judge stopped counting `cat sync.py` as a run, gave 2 of 3 with Hard Eng (one run used a shell loop and `; echo`, which hides the exit code from the hook) and 0 of 3 bare. A kept Haiku session recorded the error count 3 in its session file and stopped after the third run. Limits: Claude main agent only; Codex has no failure event.
E2E: N/A — no user journey; the hook runs in every Claude session, and the Haiku eval drives a real session through the installed hooks.

Delivery target: Merge
Delivery: Pending — PR checks and merge into `develop`.
