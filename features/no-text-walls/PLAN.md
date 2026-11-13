# Screen text comes in short blocks

Status: Complete

## Outcome + scope

A new change rule, HE-NO-TEXT-WALLS, refuses a change that adds or edits a block of screen text above the caps. The caps are 25 words in a block, 3 sentences in a block and 20 words in a sentence. The rule reads TSX and JSX files first, then the Dart files of Flutter packages. It runs in the quick check, the full check, the push check and CI of every installed project, with no change to a project's gates file.

Non-goals: a debt file or a list of old hits, an allowlist or an ignore comment, a check of `.ts` or `.js` files, a check of translated message catalogs other than the template ARB file, a check of Vue, Svelte, Astro, SwiftUI or Compose screens (those print a `Gap:` line), a new load rule for the gates file.

## Repository context

Owners: `.hooks/comments.py::validate_suppressions` (the place where change rules run, next to `ui_source_check`); new `.hooks/text_walls.py` (settings, scope, measure, the three rules, the list command, the `--stdin` judge); new `.hooks/text_readers.py` (reader cache, install, run); new `.hooks/text_reader_programs.py` (the two reader programs as text); `.hooks/gate_runner.py` (the `text-walls` command, the `merge` shard); `.hooks/update.py::scaffold_files` (ships the pin files); `.hooks/basic_mode.py::announce` (`Gap:` lines); `.agents/skills/he/references/requirements.md` (the requirement entry).
Same cause: N/A — a new rule, not a repair. HE-UI-SOURCE is the nearest earlier rule, and this rule reuses its place and its changed-line data.
Single source: the three caps and their defaults live only in `text_walls.settings`. The word and sentence count lives only in `text_walls.measure`; the change rule, the list command and the `--stdin` judge all call it. The readers return parts and never count. The Dart reader reuses the analyzer pin of `.hooks/dart_declarations.pubspec.yaml`. Searched `.hooks` and `.agents` for another word count or caps value: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner gave the rule text on 2026-11-13, asked how to enforce it, accepted the answer with "go", and gave full authority for design, merge and release.
Decisions:

1. Caps: an optional `text_walls` key in `hard-eng.gates.json` holds the three numbers and an optional `paths` list of folder globs. Older releases ignore the key. A project can change a number, never exempt a file.
2. Scope: every screen file by default. `paths` can only narrow by folder.
3. Old text: the rule judges only blocks whose own text lines a change touches. An old block that a change only moves or re-indents passes, by a comparison with the base text. There is no debt file.
4. Parsers: `oxc-parser` with Bun for TSX and JSX; the Dart analyzer, compiled once, for Dart. A reader starts only when a change touches a screen file.
5. Stored free text renders only inside a `UserContent` component, or in an element with a clamp of 2 lines or fewer inside a control that a tap opens. The component name is fixed.
6. Structural skips: `script`, `style`, `code`, `pre`, objects with `@context` or `@type`, and the Next.js `metadata` export. Tests, stories and generated files are exempt.
7. The template ARB file of a Flutter package is read, because the Flutter starter keeps its text there.
8. A missing tool fails closed with its install step. The `merge` shard of CI skips the rule, because that job has no Bun and the other jobs run the rule.
9. Cut line: the TSX and JSX part ships first in this branch. If the Flutter part cannot pass its gates, the release ships TSX and prints a `Gap:` line for Flutter.

## Acceptance + steps

- [x] A 46-word literal paragraph is refused with its step → `tests/test_text_walls.py::test_a_46_word_literal_paragraph_is_refused_with_its_step`
- [x] Three short sentences pass, a fourth sentence and a 21-word sentence are refused → `tests/test_text_walls.py::test_the_three_caps_each_refuse_one_block`
- [x] One interpolation counts as one word, and a conditional counts its longer branch → `tests/test_text_walls.py::test_measure_counts_words_and_sentences`
- [x] Inline elements merge into one block; text props, object keys and prose constants are blocks; a class string constant passes → `tests/test_text_walls.py::test_each_text_form_is_one_block`
- [x] A stored body in a banner is refused; with a clamp of 2 lines and a tap it passes; with 3 lines or no tap it is refused → `tests/test_text_walls.py::test_stored_text_needs_user_content_or_a_short_clamp_with_a_tap`
- [x] `UserContent` passes an expression and refuses literal text → `tests/test_text_walls.py::test_user_content_takes_expressions_only`
- [x] Structured data and `script`, `style`, `code` and `pre` are skipped → `tests/test_text_walls.py::test_structural_skips_are_not_judged`
- [x] An untouched old wall passes, a re-indented one passes, an edited one is refused, and a deleted break judges the merged block → `tests/test_text_walls.py::test_only_touched_text_is_judged`
- [x] Tests, stories, generated files and files outside `paths` are not judged → `tests/test_text_walls.py::test_exempt_files_and_paths_are_not_judged`
- [x] The caps default with no setting, and an invalid setting is refused with its fix → `tests/test_text_walls.py::test_settings_default_and_refuse_invalid_values`
- [x] The list command prints every current wall, and `--stdin` judges server strings with the same caps → `tests/test_text_walls.py::test_the_list_command_and_the_stdin_judge_share_the_caps`
- [x] A change with no screen file starts no reader and loads no rule module → `tests/test_text_readers.py::test_a_change_with_no_screen_file_starts_no_reader_and_loads_no_rule_module`
- [x] A missing Bun or Dart fails closed with its install step, and a file that the reader cannot parse is a finding → `tests/test_text_readers.py::test_a_missing_tool_fails_closed_with_its_step`
- [x] The `merge` shard skips the rule, and the pin files ship with the hooks → `tests/test_text_readers.py::test_the_merge_shard_skips_the_rule`
- [x] An updated old project refuses a new wall with its gates file unchanged → `tests/test_text_walls_update.py::test_an_updated_old_project_refuses_a_new_wall_with_its_gates_file_unchanged`
- [x] 1,000 screen files take under one second of processor time → `tests/performance/test_text_walls_speed.py::test_one_thousand_screen_files_take_under_one_second_of_cpu`
- [x] A Flutter text wall is refused, rich text spans merge, stored text needs `maxLines` of 2 or fewer and a tap → `tests/test_text_walls.py::test_flutter_text_follows_the_same_rules`
- [x] Other screen stacks print a `Gap:` line → `tests/test_text_walls.py::test_other_screen_stacks_print_a_gap_line`
- [x] No starter screen holds a text wall → `tests/test_text_walls.py::test_no_starter_screen_holds_a_text_wall`

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at af5c7ea4, and the Hard Eng check run of that commit passed. No Draft check ran on this branch before the first edit.
Execution: one builder for the TSX part end to end (wiring, readers, tests, update test, speed test), then the same builder for the Flutter part; a fresh reviewer for the final diff. The first slice is the red test of the 46-word paragraph through `validate_suppressions`.

## Risks + recovery

- The tests gate runs near its time limit. Tests that start a reader stay few, and the word and sentence table is a pure test. The gate time is measured after the first slice.
- A false refusal blocks a push in every project. The rule judges only touched text, and each refusal names the file, the line, the count and the fix. Recovery: revert the commit that wires the rule into `validate_suppressions`; the modules then never load.
- The JavaScript reader needs one install with network access. An offline first run fails closed with that step.
- Text behind `t('key')` or `l10n.x` is not visible to the rule, except in the template ARB file.

## ux_reference

N/A — no app screen changes; the rule prints text lines in a terminal.

## Verification

Result: Passed
Evidence: each test of the acceptance list failed before its code and passes now, except the tests that pin a behavior the first slice already had (the no-reader test, the structural skips and the speed test). The 62 tests of the four new test files pass. The list command ran on 31 real installed projects with screen files, 16 with web screens and 15 with Flutter screens: no reader error, and 1,362 web files took 1.4 seconds. A quick check with one changed Python file took the same time before and after, within 15 milliseconds in two runs each. A thousand screen files cost 0.18 seconds of processor time. An independent review ran probes on the web part and found eight faults; each one has its own repair commit and test.
Review: the web part and the two update repairs had one independent review with real reader probes. The Flutter part and the nine repair commits came after that review; the independent challenge on the final commit covers them.
E2E: N/A — a check rule has no user journey; the update test runs a real update of an old project and a real check there.
Retro: (1) The review found a refusal for a guard or a list call on a stored field, and walls inside were not read → `tests/test_text_walls.py::test_a_guard_or_map_on_a_stored_field_reads_the_elements_inside`. (2) The comparison with old text let real edits pass and refused a renamed file → `tests/test_text_walls.py::test_only_touched_text_is_judged`. (3) A reader folder with a missing part failed at each run, an install that hung gave a traceback, and one release removed the reader of another → `tests/test_text_readers.py::test_a_half_deleted_reader_folder_is_built_again`, `tests/test_text_readers.py::test_an_install_that_hangs_or_fails_to_start_is_a_plain_refusal`, `tests/test_text_readers.py::test_a_reader_of_another_release_keeps_its_folder`. (4) A run on a real project refused the inline code of a `Script` component → `tests/test_text_walls.py::test_structural_skips_are_not_judged`. (5) Phrasing tags split one paragraph, a stored field in a prop was refused, and the list command hid a reader error → `tests/test_text_walls.py::test_html_phrasing_tags_stay_in_one_block`, `tests/test_text_walls.py::test_a_stored_field_passed_into_a_prop_is_not_stored_text_rendering`, `tests/test_text_walls.py::test_the_list_command_reports_a_file_that_it_cannot_read`. (6) The speed test passed with no file read → `tests/performance/test_text_walls_speed.py::test_one_thousand_screen_files_take_under_one_second_of_cpu` now asserts one reported wall.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
