# Five review faults in the UI-source readers and the plan owners

Status: Complete

## Outcome + scope

Five faults found by review of `develop` are fixed at their owners. A stylesheet of custom properties stays a token file when it holds a Tailwind v4 reset (`--color-*: initial;`) or a SCSS `//` comment. A `/*` inside a string no longer opens a comment, so a Tailwind content glob or a route path keeps the file's tokens and exemptions. A functional colour or an arbitrary length that equals a token passes in email and standalone files, as a hex colour does. An old Complete plan that only repoints test names is no plan of the change for the local UI proof and for `ship --stage delivered`. `limit_sessions` reads the empty session list that the real tool prints. Non-goals: any new rule, and any change to which files HE-UI-SOURCE judges.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-26 and its review findings file.

## Repository context

Owners: `.hooks/ui_whole.py` (`TOKEN_BLOCK`, `only_custom_properties`, `is_token_literal`), `.hooks/ui_exempt.py` (`code_of`), `.hooks/ui_raw.py` (`COLOUR_FUNCTION`), `.hooks/browser.py` (`limit_sessions`), `.hooks/change_size.py` (`unedited_plans`, `plan_text_unchanged`), `.hooks/ship_scope.py` (`plan_in`).
Same cause: findings 1 and 2 share one cause with the comment readers: each reader cut text with its own pattern, so the token reader missed `//` and every reader cut inside strings. `code_of` is now the one comment cutter of the token and exemption readers, and `only_custom_properties` uses it; `code_lines` in `ui_whole.py` reads a string with the same `STRING` pattern, because the independent review showed that its old quote count on one line still hid code after a `/*` in a multi-line template or after an escaped quote. Findings 3 and 5 are separate: a pattern that kept only the start of a call, and a fixture written from one reading of the tool output. Finding 4: `unedited_plans` and `plan_in` each judged "the plan did not change" in their own way; both now use `plan_text_unchanged`. Searched `.hooks` for other readers of comments (`CSS_COMMENT` in `ui_rules.py`, `ui_audit_rules.py`, `ui_css_imports.py`) and left them: they cut CSS block comments, where a string holds no `/*` that matters.
Single source: `code_of` for comment cutting in the token readers; `plan_text_unchanged` for an old plan that did not change.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the maintainer's release request to merge to develop and main; the coordinator's brief of 2026-11-26 asks for these fixes, and the coordinator merges the PR into `develop` through `ship`.

## Acceptance + steps

- [x] A token stylesheet with `--color-*: initial;`, `--*: initial;` or a SCSS `//` comment is a token file; a reset beside a real rule is still refused → `tests/test_ui_token_stylesheet.py::test_a_stylesheet_of_custom_properties_with_a_tailwind_reset_or_a_scss_comment_is_a_token_file` and `tests/test_ui_token_stylesheet.py::test_a_reset_or_a_scss_comment_beside_a_real_rule_is_still_no_token_file`
- [x] A `/*` inside a string opens no comment, a real comment is still cut, and a comment grants no exemption → `tests/test_ui_comment_cut.py::test_a_slash_star_inside_a_string_does_not_start_a_comment` and `tests/test_ui_comment_cut.py::test_a_string_with_a_slash_star_keeps_the_page_and_the_email_exempt` and `tests/test_ui_comment_cut.py::test_a_comment_still_grants_no_exemption_and_a_comment_after_prose_is_still_cut` and `tests/test_ui_comment_cut.py::test_the_lines_that_hold_code_keep_a_string_whole_and_cut_each_real_comment`
- [x] An email or standalone literal that equals a token (`rgb(`, `rgba(`, `hsl(`, `oklch(` or an arbitrary length) passes; one that equals none is still one finding with the whole call → `tests/test_ui_token_literal_forms.py::test_an_email_or_standalone_literal_that_equals_a_token_is_allowed_whatever_its_form` and `tests/test_ui_token_literal_forms.py::test_an_email_literal_that_equals_no_token_is_still_one_finding` and `tests/test_ui_token_literal_forms.py::test_an_arbitrary_class_with_a_colour_call_after_an_underscore_is_one_finding` and `tests/test_ui_token_literal_forms.py::test_an_email_class_whose_colour_calls_equal_tokens_is_allowed_after_an_underscore`
- [x] The empty session list `{"sessions":[]}` clears saved init scripts, as the wrapped form does → `tests/test_browser_init_scripts.py::test_the_empty_session_list_of_the_real_tool_clears_saved_init_scripts_and_a_wrapped_one_too`
- [x] An old Complete plan that only repoints test names is no active plan and no `--plan` request; an edited or added plan still is → `tests/test_repointed_old_plans.py::test_a_repointed_or_reformatted_old_complete_plan_is_no_active_plan` and `tests/test_repointed_old_plans.py::test_a_pr_that_adds_or_edits_a_plan_still_names_it`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`b1f87886`) the plan and UI tests pass. The new tests fail there: 13 of 15 UI cases, 2 of 5 browser cases and 3 of 4 plan cases. The two that pass guard valid cases. The two plan cases for `plan_in` fail there on its old signature, which only shows that the function changed; the old function names any plan the PR edits.
Execution: One builder in a linked worktree off `origin/develop`: red tests first, then one commit per fix.

## Risks + recovery

`code_of` keeps strings, so a prose apostrophe that pairs with a later one on the same line can keep a comment on that line; the file is then judged a little more, never less. `plan_in` reads the base and head texts from Git; when the head object is missing it still names the plan, as before. Recovery: revert the commits.

## ux_reference

N/A — hook validation logic and tests only; no visible UI.

## Verification

Result: Passed
Evidence: Focused tests pass: all UI tests plus the local UI proof tests (535 cases) with the one fixture expectation updated from `rgb(` to the whole call; the browser tests (31); the shipping, plan and handoff tests (153). Static gates pass with the exact commands of `hard-eng.gates.json`: format, lint, complexity, annotations, types, dead-code and security. `hot-paths` on the six touched files: 0 findings. Real tool: `limit_sessions` run against agent-browser 0.44.0 on three inputs (empty namespace, one open session, after close): 3 of 3 agree, with the saved init scripts kept for the open session and cleared for the two empty lists. That version printed the wrapped form `{"success":true,"data":{"sessions":[]}}` for an empty list; the unwrapped form `{"sessions":[]}` is from the earlier 0.43.0 record in the `look-followup` plan and was not reproduced, so the reader takes both. The independent review of the first head found two faults, both fixed with tests: the colour-call hit read the raw line, which hid a colour after an underscore in a Tailwind class, and `code_lines` still hid code after a `/*` in a string.
E2E: N/A — hook tests run real temporary Git repositories and real file text; no user journey changes.
Real service: N/A — local Git and Python only; no outside service is called.
Retro: Escaped bug: five faults passed every gate on their PRs; the gate is the focused test of each reader, and each new case fails on the base revision → `tests/test_ui_token_stylesheet.py::test_a_stylesheet_of_custom_properties_with_a_tailwind_reset_or_a_scss_comment_is_a_token_file`. Review correction: none. Ran too late: none. Single source: `code_of`, `plan_text_unchanged`.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
