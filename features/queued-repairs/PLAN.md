# Repair the 22 faults that the rollout of 2026-11-23 and the later notes found in the shipping, plan, browser, look, update, Trello and test code

Status: Ready

## Outcome + scope

Twenty-two faults in Hard Eng's own code each get a failing test first, a fix at the cause and a nearby valid case that stays valid: the delivery timeout message, a missing `--plan` at the delivered stage, a format-only edit of an old plan, fetch waves that are not the same twice, the `look` reviewer that misjudges measured values, the `ui_library` key on update, two test warnings, a slow Vite starter test, the reviewer prompt, a wrapped button label, field actions, `check --static`, the planner question wording, a second card for one client, a DOING card with a waiting fix, a push stopped by a signal, a skip approval with clock times, a plan read for an update branch, the delivery target line, a rule ID in an acceptance line, one owner for each domain question and an old plan that one bad-form line hides from the test name check. Non-goals: raising any time limit, new gates, and changes to the vendored skill package copies.

## Sources + coverage

Sources: the maintainer's brief with faults 1 to 9 of 2026-11-23, read in full; its section "Added 2026-11-24" with faults 10 to 13, read in full; its section "Added 2026-11-24 (2)" with faults 14 to 21, read in full; its section "Added 2026-11-24 (3)" with fault 22, read in full.
Reviewer: A second reader (Opus, given only the brief and this plan) found 17 gaps. Repaired in this plan: the acceptance lines now name the near cases, fault 3 states that it covers the UX gate and that other gates keep the old retry, fault 6 states that no older location of the key exists to migrate, fault 14 states how it reads "that card", and Verification will hold the research of fault 21, the reproduction result of each of faults 16 to 20, the two `look` runs of fault 11 and the hook timings. Not changed: the 150 ms delay is my choice from the 2 ms and 150 ms of the brief, and the move of the attribution check is forced by the file length limit.
Deliverables: None

- Fault 1, the timeout message: In scope — A delivery check that runs past its limit says it timed out and after how many seconds; a program that cannot start still says the query is unavailable
- Fault 2, a missing `--plan`: In scope — The delivered stage without `--plan`, for a PR that changed a plan, says `--plan` is missing and names the plan; a PR that changed no plan still passes
- Fault 3, a format-only plan edit: In scope — A formatter rewrite of an old Complete plan does not reopen its UX gate, a real text change still does, and the rewrite rules equal what a real formatter wrote on 40 sample lines
- Fault 4, fetch waves: In scope — Each step of a session gets the same request delay, fetches that start a few milliseconds apart count as one wave, prefetch requests add no wave, and a chain of four fetches still fails
- Fault 5, `look` and measured values: In scope — The record of an image holds its measured contrast, gaps and sizes, the `look` prompt hands them to the reviewer, and a Fail line that contradicts its own count is refused
- Fault 6, the `ui_library` key on update: In scope — An update adds `shipping.ui_library` in the same commit when a library folder exists, and leaves an existing key alone
- Fault 7, test warnings: In scope — The two test files that returned a list run with no `PytestReturnNotNoneWarning`, and the warning is now an error for every test
- Fault 8, the slow Vite starter test: In scope — The Vite starter test finishes inside bun's default limit on the hosted Mac
- Fault 9, the reviewer prompt: In scope — The challenge prompt tells the reviewer that `pr-text` and `ship` check the PR text and that it reviews the diff and plan only
- Fault 10, a wrapped button label: In scope — A button, or a link drawn as a button, whose label takes more than one line fails `wrapped-label`; a one-line button and a wrapped text link pass
- Fault 11, field actions: In scope — The `Alignment` rule line says that an action on one field is an icon inside that field, and the `look` prompt carries it
- Fault 12, `check --static`: In scope — `check --static` runs the analyzer roles and no tests, and a function over the complexity limit fails it and passes `--quick`
- Fault 13, planner questions: In scope — The Questions line of `he-plan` says that repository facts and user sources are checked first
- Fault 14, a second card for one client: In scope — A second open card that names the same client as an older one is listed unless it is marked checked, and without `clientPattern` no card is compared by client
- Fault 15, a DOING card with a waiting fix: In scope — A card in `doing` or `testing` whose newest comment says the fix waits in an open PR is listed in `waitsOnUs`
- Fault 16, a push stopped by a signal: In scope — A push of the update branch that a signal stopped says to run it again and names no fault
- Fault 17, a skip approval with clock times: In scope — A skip approval whose place of the decision holds clock times is read as the decision of the user, and a skip with clock times and no colon after the place still fails
- Fault 18, an update branch with no plan: In scope — The plan check names the open plan that it read and says that it may belong to another task
- Fault 19, the delivery target line: In scope — A plan line that starts with the words Delivery target and holds more than the target fails the plan check as it fails the merge
- Fault 20, a rule ID in an acceptance line: In scope — A rule ID beside the named test is a citation, and the screen part of the PR text check and the quick check of a plan line judge as the full runs do
- Fault 21, one owner for each domain question: In scope — The review reference tells the reviewer to report a second answer to one domain question
- Fault 22, an old plan skipped whole: In scope — An old Complete plan with one bad-form acceptance line still names its tests to the check of a renamed test

## Repository context

Owners: `.hooks/shipping.py` owns `_run`, `verify` and the delivered stage. `.hooks/change_size.py` owns `plan_words`, `judged_plans` and the plan change rules; `.hooks/local_ui_proof.py` reads them. `.hooks/ui_measure.py` owns the page script and its limits; `.hooks/browser.py` owns the session steps and their environment. `.hooks/look.py` owns the reviewer prompt and the verdict check. `setup.py` and `.hooks/update.py` own what an update writes. `.hooks/challenge.py` owns the challenge prompt. `.agents/starters/vite/tests/app.test.tsx` owns the starter test. `.hooks/gate_schedule.py` owns the role sets, `.hooks/reports.py` `quick_groups` and `.hooks/gate_runner.py` `check` own how a run picks its gates. `.hooks/plan_runs.py` owns the Real service line, `.hooks/plans.py` the plan fields and `validate_plans`, `.hooks/ship_scope.py` the delivery target. `.hooks/update_pr.py` owns the push of the update branch. `.agents/skills/trello-coordinator/scripts/trello_board/report.py` and `config.py` own the board report and `trello.json`. `.agents/skills/he-plan/references/ux.md` owns the Usability rules and Standard patterns; `.agents/skills/code-review/references/review.md` owns the review method.
Same cause: Fault 3: `reformatted_plans` already compares words, but only for a plan that fails today's rules and only on the retry of `judged_stage`; `local_ui_proof` calls `judged_plans` directly, so the same comparison now runs inside `judged_plans`. Fault 4: searched `fetch_waves`, `fetch-waterfall`, `wavesOf` and `performance.getEntriesByType` in `.hooks`, `tests` and the skills; one owner, no other copy of the count. Fault 1 and fault 2: `_run` is the one runner for git, gh and the delivery check. Fault 10: the clipped-label rule and the wrapped-label rule share one loop over `controls`. Fault 12: `quick_groups` takes the role set, so `--quick` and `--static` share one filter. Fault 19: `plans.py` and the merge both call `plan_target_problem` in `ship_scope.py`; the plan check now finds the field with a looser match, the rule stays in one place. Fault 20: `ship` and CI call `pull_problem` in `pr_text.py`. Fault 22: `acceptance_references` in `plans.py` is the one reader of `path::test` names; `acceptance_tests` and `unchanged_plan_test_problem` both call it.
Single source: Fault 14 reads "unless that card is marked as checked" as the card that would be listed. Fault 6 finds no older place of the key, so the update only adds it. The request delay joins `LIMITS` in `.hooks/ui_measure.py`; the browser command reads it from there. The prefetch signs sit in one constant beside it. The plan words rule stays in `plan_words`. The measured values go in the record that `write_record` owns; `look` reads them from that record. The role sets stay in `gate_schedule.py`. The client number and the checked label are read from `trello.json` only. `plans.py` reached 1001 lines, so the attribution check moved to `commit_attribution.py`, its one owner; `known_first_party` lists the new modules.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [ ] A delivery check that runs past its limit says it timed out and after how many seconds; a program that cannot start still says the query is unavailable → `tests/test_shipping.py::test_a_delivery_check_that_runs_too_long_says_it_timed_out_and_after_how_many_seconds` and `tests/test_shipping.py::test_a_program_that_cannot_start_still_says_the_query_is_unavailable`
- [ ] The delivered stage without `--plan`, for a PR that changed a plan, says `--plan` is missing and names the plan; a PR that changed no plan still passes → `tests/test_shipping_delivered.py::test_delivered_without_a_plan_says_the_plan_is_missing_when_the_pr_changed_a_plan` and `tests/test_shipping_delivered.py::test_delivered_without_a_plan_still_passes_for_a_pr_that_changed_no_plan`
- [ ] A formatter rewrite of an old Complete plan does not reopen its UX gate, a real text change still does, and the rewrite rules equal what a real formatter wrote on 40 sample lines → `tests/test_format_only_plans.py::test_a_formatter_rewrite_of_an_old_complete_plan_does_not_reopen_its_ux_gate`, `tests/test_format_only_plans.py::test_a_real_text_change_to_an_old_complete_plan_still_reopens_its_ux_gate` and `tests/test_format_only_plans.py::test_the_words_of_a_plan_survive_what_a_real_formatter_rewrites`
- [ ] Each step of a session gets the same request delay, fetches that start a few milliseconds apart count as one wave, prefetch requests add no wave, and a chain of four fetches still fails → `tests/test_browser.py::test_every_step_of_a_session_gets_the_same_request_delay`, `tests/test_ui_audit_guards.py::test_a_session_without_the_request_delay_is_refused`, `tests/test_ui_audit_guards.py::test_fetches_that_start_a_few_milliseconds_apart_count_as_one_wave`, `tests/test_ui_audit_guards.py::test_prefetch_requests_add_no_wave` and `tests/test_ui_audit_guards.py::test_a_four_xhr_chain_still_fails_with_the_request_delay`
- [ ] The record of an image holds its measured contrast, gaps and sizes, the `look` prompt hands them to the reviewer, and a Fail line that contradicts its own count is refused → `tests/test_ui_audit_guards.py::test_the_record_holds_the_measured_contrast_gaps_and_sizes`, `tests/test_look.py::test_the_prompt_gives_the_reviewer_the_measured_values_of_each_image` and `tests/test_look.py::test_a_fail_line_that_contradicts_its_own_count_is_refused`
- [ ] An update adds `shipping.ui_library` in the same commit when a library folder exists, and leaves an existing key alone → `tests/test_scaffold_replay.py::test_an_update_adds_the_ui_library_key_in_the_same_commit` and `tests/test_scaffold_replay.py::test_an_update_leaves_an_existing_ui_library_key_alone`
- [ ] The two test files that returned a list run with no `PytestReturnNotNoneWarning`, and the warning is now an error for every test → `tests/test_shipped_shapes.py::test_the_template_group_with_a_coverage_gate_and_a_tests_gate_runs`, whose file and `tests/test_fallow_resolved.py` hold the two renamed helpers
- [ ] The Vite starter test finishes inside bun's default limit on the hosted Mac → N/A — the starter runs under bun, not pytest; the proof is the hosted `scaffold-vite` macOS canary job, with the phase timings recorded in Verification
- [ ] The challenge prompt tells the reviewer that `pr-text` and `ship` check the PR text and that it reviews the diff and plan only → `tests/test_challenge.py::test_the_prompt_leaves_the_pr_text_to_pr_text_and_ship`
- [ ] A button, or a link drawn as a button, whose label takes more than one line fails `wrapped-label`; a one-line button and a wrapped text link pass → `tests/test_ui_audit_guards.py::test_each_runtime_audit_guard_finds_one_fault` and `tests/test_ui_audit_guards.py::test_a_one_line_button_and_a_wrapped_text_link_pass_the_label_rule`
- [ ] The `Alignment` rule line says that an action on one field is an icon inside that field, and the `look` prompt carries it → `tests/test_look.py::test_the_prompt_tells_the_reviewer_a_field_action_is_an_icon_inside_its_field`
- [ ] `check --static` runs the analyzer roles and no tests, and a function over the complexity limit fails it and passes `--quick` → `tests/test_quick_check.py::test_a_static_check_runs_the_analyzer_roles_and_no_tests` and `tests/test_quick_check.py::test_a_function_over_the_complexity_limit_fails_the_static_check_and_passes_the_quick_one`
- [ ] The Questions line of `he-plan` says that repository facts and user sources are checked first → N/A — one changed word of skill text; the skill link and size tests pass and the Reader check is recorded in Verification
- [ ] A second open card that names the same client as an older one is listed unless it is marked checked, and without `clientPattern` no card is compared by client → `tests/test_trello_board.py::test_a_second_open_card_for_the_same_client_is_listed_unless_it_is_marked_checked` and `tests/test_trello_board.py::test_two_cards_with_no_client_setting_are_not_compared_by_client`
- [ ] A card in `doing` or `testing` whose newest comment says the fix waits in an open PR is listed in `waitsOnUs` → `tests/test_trello_board.py::test_a_card_whose_fix_waits_in_an_open_pr_is_listed_in_doing_and_testing`
- [ ] A push of the update branch that a signal stopped says to run it again and names no fault, and a refused push still names the fault of the project → `tests/test_update_pr_refusal.py::test_a_push_that_a_signal_stopped_says_rerun_and_names_no_fault` and `tests/test_update_pr_refusal.py::test_a_refused_push_of_the_update_branch_names_the_next_step`
- [ ] A skip approval whose place of the decision holds clock times is read as the decision of the user, and a skip with clock times and no colon after the place still fails → `tests/test_plan_runs.py::test_a_plan_passes_with_its_real_service_run_stated` (row `the-place-of-the-decision-holds-clock-times`) and `tests/test_plan_runs.py::test_a_plan_fails_when_its_real_service_run_is_missing_or_a_fake_is_the_reason` (row `a-skip-with-a-clock-time-and-no-colon-after-the-place`)
- [ ] The plan check names the open plan that it read and says that it may belong to another task → `tests/test_scaffold_replay.py::test_an_update_branch_with_a_repair_commit_names_the_plan_it_read_and_why` and `tests/test_scaffold_replay.py::test_an_update_branch_with_no_plan_of_its_own_names_no_unrelated_draft_plan`
- [ ] A plan line that starts with the words Delivery target and holds more than the target fails the plan check as it fails the merge → `tests/test_shipping_plan.py::test_a_delivery_target_with_more_words_fails_the_plan_check`
- [ ] A rule ID beside the named test is a citation, and the screen part of the PR text check and the quick check of a plan line judge as the full runs do → `tests/test_plan_acceptance.py::test_a_rule_id_beside_the_named_test_is_a_citation_not_a_claim_of_coverage`, `tests/test_pr_text.py::test_ship_reads_the_screen_part_of_the_pr_text_check_as_ci_does` and `tests/test_quick_check.py::test_a_quick_check_refuses_a_bad_plan_line_as_the_full_check_does`
- [ ] The review reference tells the reviewer to report a second answer to one domain question → N/A — the choice is one sentence of review guidance; no check can prove it, and the research that rules a check out is recorded in Verification
- [ ] An old Complete plan with one bad-form acceptance line still names its tests to the check of a renamed test, and the same plan with the test kept passes → `tests/test_plan_acceptance.py::test_an_old_plan_with_one_bad_form_line_still_names_its_tests_to_a_renamed_test` (both rows)

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --quick` on a clean checkout of `origin/develop` at 7b6cefb0 printed PASS for dependencies-locked, shipped-focused-tests, format, lint, annotations, types and secrets-files, exit 0.
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
