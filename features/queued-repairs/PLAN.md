# Repair the nine faults that the 2026-11-23 rollout found in the shipping, plan, browser, look, update and test code

Status: Draft

## Outcome + scope

Nine faults in Hard Eng's own code each get a failing test first, a fix at the cause and a nearby valid case that stays valid: the delivery timeout message, a missing `--plan` at the delivered stage, a format-only edit of an old plan, fetch waves that are not the same twice, the `look` reviewer that misjudges measured values, the `ui_library` key on update, two test warnings, a slow Vite starter test and the reviewer prompt. Non-goals: raising any time limit, new gates, and changes to the vendored skill package copies.

## Sources + coverage

Sources: the maintainer's brief of 2026-11-23 with its nine faults, read in full.
Reviewer: N/A — nine small faults, each with a stated fix and a stated set of cases that must keep working.
Deliverables: None

- Fault 1, the timeout message: In scope — A delivery check that runs past its limit says it timed out and names the seconds; a program that cannot start still says the query is unavailable
- Fault 2, a missing `--plan`: In scope — The delivered stage without `--plan` for a PR that changed a plan says `--plan` is missing and names the plan; a PR that changed no plan still passes without it
- Fault 3, a format-only plan edit: In scope — A formatter rewrite of an old Complete plan does not reopen the UX gate; a real text change still does
- Fault 4, fetch waves: In scope — Fetches that start a few milliseconds apart count as one wave, prefetch requests add no wave, and a four-wave chain still fails
- Fault 5, `look` and measured values: In scope — The reviewer prompt holds the measured contrast, gaps and sizes of each image, and a Fail line that contradicts its own count is refused
- Fault 6, the `ui_library` key on update: In scope — An update adds the key in the same commit when a library folder exists, and leaves an existing key alone
- Fault 7, test warnings: In scope — The two test files run with no `PytestReturnNotNoneWarning`
- Fault 8, the slow Vite starter test: In scope — The starter test finishes inside bun's 5 s limit on the hosted Mac because the slow part is fixed, not the limit
- Fault 9, the reviewer prompt: In scope — The challenge prompt says that `pr-text` and `ship` check the PR text and that the reviewer reads the diff and plan only

## Repository context

Owners: `.hooks/shipping.py` owns `_run`, `verify` and the delivered stage. `.hooks/change_size.py` owns `plan_words`, `judged_plans` and the plan change rules; `.hooks/local_ui_proof.py` reads them. `.hooks/ui_measure.py` owns the page script and its limits; `.hooks/browser.py` owns the session steps and their environment. `.hooks/look.py` owns the reviewer prompt and the verdict check. `setup.py` and `.hooks/update.py` own what an update writes. `.hooks/challenge.py` owns the challenge prompt. `.agents/starters/vite/tests/app.test.tsx` owns the starter test.
Same cause: Fault 3: `reformatted_plans` already compares words, but only for a plan that fails today's rules and only on the retry of `judged_stage`; `local_ui_proof` calls `judged_plans` directly, so the same comparison now runs inside `judged_plans`. Fault 4: searched `fetch_waves`, `fetch-waterfall`, `wavesOf` and `performance.getEntriesByType` in `.hooks`, `tests` and the skills; one owner, no other copy of the count. Fault 1 and fault 2: `_run` is the one runner for git, gh and the delivery check.
Single source: The request delay joins `LIMITS` in `.hooks/ui_measure.py`; the browser command reads it from there. The prefetch signs sit in one constant beside it. The plan words rule stays in `plan_words`. The measured values go in the record that `write_record` owns; `look` reads them from that record.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [ ] A delivery check that runs past its limit says it timed out and after how many seconds; a program that cannot start still says the query is unavailable → `tests/test_shipping.py::test_a_delivery_check_that_runs_too_long_says_it_timed_out_and_after_how_many_seconds` and `tests/test_shipping.py::test_a_program_that_cannot_start_still_says_the_query_is_unavailable`
- [ ] The delivered stage without `--plan`, for a PR that changed a plan, says `--plan` is missing and names the plan; a PR that changed no plan still passes → `tests/test_shipping_delivered.py::test_delivered_without_a_plan_says_the_plan_is_missing_when_the_pr_changed_a_plan` and `tests/test_shipping_delivered.py::test_delivered_without_a_plan_still_passes_for_a_pr_that_changed_no_plan`
- [ ] A formatter rewrite of an old Complete plan does not reopen its UX gate, a real text change still does, and the rewrite rules equal what a real formatter wrote on 40 sample lines → `tests/test_format_only_plans.py::test_a_formatter_rewrite_of_an_old_complete_plan_does_not_reopen_its_ux_gate`, `tests/test_format_only_plans.py::test_a_real_text_change_to_an_old_complete_plan_still_reopens_its_ux_gate` and `tests/test_format_only_plans.py::test_the_words_of_a_plan_survive_what_a_real_formatter_rewrites`
- [ ] Each step of a session gets the same request delay, and a session without it is refused → `tests/test_browser.py::test_every_step_of_a_session_gets_the_same_request_delay` and `tests/test_ui_audit_guards.py::test_a_session_without_the_request_delay_is_refused`
- [ ] Parallel fetches that start a few milliseconds apart count as one wave, prefetch requests add no wave, and a chain of four fetches still fails → `tests/test_ui_audit_guards.py::test_fetches_that_start_a_few_milliseconds_apart_count_as_one_wave`, `tests/test_ui_audit_guards.py::test_prefetch_requests_add_no_wave` and `tests/test_ui_audit_guards.py::test_a_four_fetch_chain_still_fails_with_the_request_delay`
- [ ] The record of an image holds its measured contrast, gaps and sizes, and the `look` prompt hands them to the reviewer with the rule that a measured value beats an eye estimate → `tests/test_ui_audit_guards.py::test_the_record_holds_the_measured_contrast_gaps_and_sizes` and `tests/test_look.py::test_the_prompt_gives_the_reviewer_the_measured_values_of_each_image`
- [ ] A `look` answer whose No clutter line is a Fail with 0 removed is refused → `tests/test_look.py::test_a_fail_line_that_contradicts_its_own_count_is_refused`
- [ ] An update adds `shipping.ui_library` in the same commit when a library folder exists, and leaves an existing key alone → `tests/test_scaffold_replay.py::test_an_update_adds_the_ui_library_key_in_the_same_commit` and `tests/test_scaffold_replay.py::test_an_update_leaves_an_existing_ui_library_key_alone`
- [ ] The two test files that returned a list run with no `PytestReturnNotNoneWarning`, and the warning is now an error for every test → `tests/test_shipped_shapes.py::test_the_template_group_with_a_coverage_gate_and_a_tests_gate_runs`
- [ ] The Vite starter test finishes inside bun's default limit on the hosted Mac → N/A — the starter runs under bun, not pytest; the proof is the hosted `scaffold-vite` macOS canary job, with the phase timings recorded in Verification
- [ ] The challenge prompt tells the reviewer that `pr-text` and `ship` check the PR text and that it reviews the diff and plan only → `tests/test_challenge.py::test_the_prompt_leaves_the_pr_text_to_pr_text_and_ship`

## Baseline + execution

Result: Pending
Evidence: Pending the Draft check on `origin/develop` at eb78609f.
Execution: One builder, one fault at a time: a red test commit, then the fix commit, in the order of the brief. The browser tests run against the real `agent-browser`.

## Risks + recovery

The fixed delay adds 150 ms to each request of a page that a capture or measure opens, so each capture takes a little longer; the same delay for every request keeps the count the same twice. A page that fires fetches more than 150 ms apart on purpose still counts them as separate waves. Recovery: revert the commits.
Not checked: browsers other than the one that `agent-browser` starts, and prefetch signs of other frameworks than the headers that a real Next.js app sends.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — the proof is the real-browser tests above, which drive `browser.browser_command` and a real page; no journey of an app is changed.
Real service: N/A — no outside service is called; the test pages are served from a local folder.
Retro: Pending

Delivery target: Merge
Delivery: Pending — CI, the guarded merge into `develop`.
