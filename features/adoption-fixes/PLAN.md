# Let an adoption whose tools fix files pass its first full check

Status: Complete

## Outcome + scope

A brownfield project whose lint fixes touch commented files passes its first full check after `adopt`, and the Stop hook counts only real repeats (#433). Non-goals: changing the comment rule for later changes, changing which gates run.

## Repository context

Owners: `.hooks/comments.py::validate_comments` (HE-COMMENT-LINES), `.hooks/debt.py` (adoption debt), `.hooks/hard-eng.py::adopt`, `.hooks/agent_hooks.py::repeat_note`, `release_canary.py` (brownfield sample).
Same cause: the brownfield canary failed after its sample moved to Python 3.11. `adopt` ran the gates once, and the sample's lint config applied safe fixes during that run. The fixes changed `timed.py`, so the comment check counted its old comment blocks in the install change, and the debt held the lint gate's own fix report, which the next run no longer printed. Every brownfield adopter with fixing lint hits this. Separately, `repeat_note` keyed every failure without a fail or error line on the empty text, so unrelated plan findings were called one repeat (#433). No earlier fix of either cause.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-28: "why file issue, you fix in a pr"; on 2026-10-29: fix #433 too, Codex review loop before the PR, then release, with full authority.
Decision: the comment rule stays whole-file for every later change; only the change that installs Hard Eng treats a block the file already held as old code. Adoption reruns the gates once when they changed files and records what the fixed code still fails with. The canary sample keeps only the lock upgrade, so it proves both fixes end to end.

## Acceptance + steps

- [x] In the install change, a block the file already held passes when install tools touch the file; a new block fails; a later change answers for every block → `tests/test_comments.py::test_the_install_change_keeps_older_blocks_in_files_its_tools_fixed`.
- [x] A changed old block fails in the install change, even with a blank comment line inside it → `tests/test_comments.py::test_the_install_change_compares_each_older_block_whole`.
- [x] When adoption's gates fix files, the debt holds what the fixed code still fails with, not the fix report → `tests/test_debt.py::test_adoption_records_what_the_fixed_code_still_fails_with`.
- [x] Two failures with no fail or error line keep separate counts; the same one twice is a repeat → `tests/test_stop_checks.py::test_failures_without_a_fail_or_error_line_keep_their_own_count`.
- [x] Earlier repeat counting still holds → `tests/test_stop_checks.py::test_a_failure_seen_before_in_this_checkout_is_named_as_a_repeat`.
- [x] The brownfield sample still drops the ended Python 3.10 → `tests/test_release_canary.py::test_the_brownfield_upgrade_drops_the_ended_python`.

## Baseline + execution

Result: Passed
Evidence: Branch point develop after PR #432, whose CI passed every check.
Execution: One builder, this session; Codex adversarial review before the PR.

## Risks + recovery

An install change could keep an old comment block that the user meant to clean. Recovery: the next change to that file answers for it, as before.

## ux_reference

N/A — check and hook behavior only; no visible UI.

## Verification

Result: Passed
Evidence: Each new test fails on the old code and passes now. The local brownfield canary failed with only the Python 3.10 drop (comment check, then lint and annotation debt) and passes with these fixes. Comment, debt, stop hook and canary tests pass. Codex adversarial review (gpt-6-astra): round 1 found the old-block match stopped short of blocks with a blank comment line, fixed; round 2 no material findings.
E2E: The brownfield canary jobs install Hard Eng into the public sample and run its first full check.
Delivery target: Merge
Delivery: Pending — merges into develop, then releases to main.
