# Look reviewer lines: fix after a list, count note after the verdict

Status: Ready

## Outcome + scope

The reviewer's answer is read by rule block. A rule block is the rule line plus every line below it up to the next rule line or image line. The `Fix:` check and the stored text read the whole block. A count note right after the verdict, such as `No clutter: Fail (kept: 40, removed: 3). text`, is stored like the note before the colon. The prompt shows the one form with the note before the colon. Non-goals: any other look change, the count guard, the px guard and the measured values of develop.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's hotfix brief of 2026-11-25.

## Repository context

Owners: `.hooks/look.py` (`clean_line`, `judge`, `PROMPT`). `plans.split_rule_line` reads the stored dash form and stays as it is.
Evidence: two real reviewer answers on a client pull request were refused as not done. The first has a Fail rule line that ends in a colon, then a numbered list, a blank line and a paragraph that holds `Fix:`. The parser read only the rule line. The second has `Fail (kept: 40, removed: 3).` after the verdict, a form that `COUNT_NOTE` does not read. `origin/main` is `4b75d2c0`.
Same cause: both refusals come from `look.judge` reading one physical line as the whole rule. On develop the `Fix:` check sits in `rule_refusal`, which also holds the count guard and the px guard; `main` has no `rule_refusal`. The join takes develop's side and keeps both new cases green. Searched `.hooks` for other readers of the reviewer's raw lines: `_scope_verdict_problem` reads plan text, not reviewer answers, and `pr_text`, `ui_proof` and `local_ui_proof` read the stored dash form, so they need no change. Not checked: the `building-flutter-apps` copy of the hooks.
Single source: `look.clean_line` stays the one owner of the stored line form; the new block step feeds it the joined block.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to put client unblocking first and to release scoped client fixes to main through every normal gate; these refusals block a client's push.

## Acceptance + steps

- [ ] A Fail rule line that ends in a colon, followed by a numbered list, a blank line and a paragraph with `Fix:`, is read as one block, and the stored line holds the whole block → `tests/test_look.py::test_a_fix_after_a_list_belongs_to_its_rule_block`
- [ ] A Fail block with no `Fix:` anywhere, or a `Fix:` that sits in another rule's block, is still refused → `tests/test_look.py::test_a_fail_block_with_no_fix_is_still_refused`
- [ ] A count note right after the verdict is stored in the same form as a note before the colon → `tests/test_look.py::test_a_count_note_after_the_verdict_is_stored_like_one_before_the_colon`
- [ ] A count note with no number after the verdict is still refused → `tests/test_look.py::test_a_count_note_with_no_number_after_the_verdict_is_still_refused`
- [ ] The prompt shows the count note before the colon → `tests/test_look.py::test_the_prompt_shows_the_count_note_before_the_colon`

Steps:

1. Commit this plan.
2. Add the red tests and see each fail on `main`.
3. Add the block step to `judge`, the after-verdict note to `clean_line` and the prompt form. Run the focused tests.
4. Run the static gates, `check --plan-stage Ready --base origin/main`, `challenge` until clean for the exact head, then `check --plan-stage Complete --base origin/main` once.
5. Open the PR to `main`, run `pr-text`, wait for CI, run `ship --stage ready`, merge with the exact head, run `ship --stage delivered`, then join `main` into `develop`.

## Baseline + execution

Result: Passed
Evidence: `tests/test_look.py` passes on `origin/main` at `4b75d2c0`.
Execution: One builder in a new worktree off `origin/main`. A fresh reviewer runs `challenge` on the candidate head before the Complete check.

## Risks + recovery

1. A reviewer line outside any rule block that follows a rule line now joins that rule's text. The block ends at the next rule or image line, and the last line must be the verdict. A stray paragraph after the last rule line and before the image lines lands in that rule's text, which only widens the `Fix:` search for that rule.
2. Recovery: revert the merge on `main` with a new hotfix PR.
Not checked: any installed project.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Pending
E2E: N/A — hook code with no app journey; the two real client reviewer answers replay through `look.judge`: main refuses both with the reported messages, this head reads both as findings with 10 rule lines each.
Real service: Passed — the Claude reviewer CLI: one real `look` review of an invented image with the new prompt returned 10 rule lines in the shown forms with no refusal, and its count notes read into the stored form.

Delivery target: Merge
Delivery: Pending — `hard-eng` passes on the PR to `main`, the merge on `main`, then the join PR merged into `develop`.
