# Whole-project pass: no switch-off inside a literal, and parent Dart excludes judged where they apply

Status: Complete

## Outcome + scope

HE-NO-SWITCH-OFF counts a switch-off only where a tool reads it: text inside a string, template or regex literal in Dart, JavaScript, TypeScript, Swift or Python is not a switch-off, in added lines and in the whole-project pass alike. A comment after a literal on the same line still fails, and a mark that its tool reads on the raw line still fails inside a string: Semgrep (`nosemgrep`, `nosem`), coverage.py (`pragma: no cover`), flake8 (`noqa`), isort (`isort: skip`), Pyre (`pyre-ignore`, `pyre-fixme`, `type: ignore`), c8, v8 and istanbul ignore, Dart coverage (`coverage:ignore-`), Gitleaks, and the forms of tools whose reading is unknown (`jscpd:ignore`, `fallow-ignore`, `dart-decimate-ignore`, `shellcheck disable=`, `zizmor: ignore`). Only forms whose tool parses comments or code are masked in literals. `.js`, `.jsx`, `.tsx` and `.swift` files are not masked, because the scanner misreads JSX text and Swift raw strings. A `/` after a postfix `++`, `--` or a TypeScript non-null `!` divides, so it opens no regex; a keyword after `.` or `$` is a name, and a `/` after `...`, `default` or `return!` opens a regex. A Dart `${...}` expression inside a string is skipped, and a Python t-string counts as a string. A Dart exclude written in a parent folder's own `analysis_options.yaml` and included by a child package is judged from the folder of the options file the analyzer reads, where it applies it (a pattern with braces or a partial `**` fails, because Python glob cannot expand it; a folder form such as `lib/a.dart/**` is judged as the path it names): a pattern that matches nothing there passes, and one that hides a child file fails and names the parent file that holds it. Non-goals: Markdown prose that names a marker and unchanged Flutter starter comments; both have a project fix (reword the sentence; delete the two template comment lines).

## Sources + coverage

Sources: N/A — found by the sealed scan of the installed projects for the strict rollout (`features/strict-rollout/PLAN.md`): lint test samples in raw strings, a migration script regex, and a package example whose options include the root file were refused.

## Repository context

Owners: `pattern_switch_offs` and `security_hits` in `.hooks/comments.py` match each raw line; the literal-aware scanner that `comment_spans` uses lived in the same file, which is at its 1000-line limit, so the scanner moves to its owner `.hooks/source_scan.py`. `validate_dart_exclusions` lived in `.hooks/project_setup.py` while only Dart analysis calls it; it moves to `.hooks/dart_boundaries.py`, its only caller in the hooks.
Same cause: excuse markers already read comments only (`comment_map`), so they had no such fault. The changed-line check (`added_switch_offs`) and the whole-project pass share `pattern_switch_offs` and `security_hits`, so both get the fix. `validate_dart_typing` and `apply_dart_typing` pass the folder's own file and keep the strict rule.
Single source: one scanner (`scanned_spans`) gives comments and literals for the comment checks and the literal mask alike.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. AGENTS.md line 10 covers Hard Eng design calls; the user approved PRs for the strict rollout (2026-11-15 06:12), which these faults block.

## Acceptance + steps

- [x] Switch-off text inside a Dart raw string, a Dart string, a template, a template expression's string, a JavaScript regex and Python strings passes in added and old lines → `tests/test_strict_refusals.py::test_switch_off_text_inside_a_literal_passes`.
- [x] A switch-off comment after a literal still fails, a Dart string with a `${...}` expression holding a quote does not hide a later comment, and every raw-read mark (Semgrep, coverage, c8, v8, Gitleaks, fallow, Dart Decimate) inside a string, in Dart, JavaScript and Python, still fails; JSX and Swift raw-string lines keep the strict reading; Pyre marks and JavaScript slashes after a property named like a keyword, `...`, `export default` or `return!` keep it too → `tests/test_strict_refusals.py::test_switch_off_after_a_literal_or_a_gitleaks_mark_in_one_fails`.
- [x] A `/` after a TypeScript non-null `!` divides, so a later line's switch-off still fails → `tests/test_strict_refusals.py::test_a_division_after_a_non_null_mark_hides_no_later_line`.
- [x] Every earlier switch-off form still fails → `tests/test_strict_refusals.py::test_old_switch_offs_anywhere_in_the_project_fail`.
- [x] A parent folder's exclude that matches nothing in the child passes; one that hides a child file fails and names the parent file; the child's own file keeps the strict rule → `tests/test_dart_exclusions.py::test_an_included_parent_exclude_is_judged_where_it_applies`.
- [x] A parent exclude with braces or a partial `**` fails → `tests/test_dart_exclusions.py::test_an_inherited_pattern_with_braces_or_a_partial_double_star_is_refused`; a nested `test/analysis_options.yaml` that includes a file above the package is judged from `test/` → `tests/test_dart_exclusions.py::test_an_inherited_pattern_is_judged_from_the_folder_of_the_analyzed_options_file`.
- [x] A Python t-string's text passes where its tool reads no comment (needs Python 3.14 or later) → `tests/test_strict_refusals.py::test_switch_off_text_inside_a_literal_passes`.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16, develop 80756642 passed CI. On it, the 6 literal cases and the parent exclude case fail; the 4 near-miss cases pass.
Execution: One builder, this session.

## Risks + recovery

A hit inside a literal that the scanner reads wrongly (an unclosed quote) would hide a real switch-off on later lines; the scanner is the one the comment rule already trusts. The literal check runs only on a line that already matches, and scans the file only then; no in-process cache, which Hard Eng's own Semgrep rule refuses. A tool that reads a mark raw is a closed list in `RAW_OFF` and `SECURITY_OFF`; a new tool that parses comments needs a masked form added deliberately, and an unknown tool stays raw. Speed: the scan skips a hit line with no quote, slash or backtick before the hit when the file has no multi-line string opener, and the scanner jumps to the next quote, slash, brace or raw prefix. The scan gives identical output on 91,428 source files. CPU time of `validate_whole_project` (3 runs each, alternating, seconds; old = develop, which has no literal masking): fsl 1.19, 1.11, 1.11 old against 1.12, 1.10, 1.12 new; P30 0.79, 0.74, 0.72 old against 0.70, 0.75, 0.69 new; `validate_suppressions` 0.10 to 0.14 on both sides. Before the jump change the new side was about 0.2 s slower on fsl. After the cache was removed (3 runs each, alternating, wall seconds): fsl 0.92, 0.92, 0.84 old against 0.88, 0.90, 0.87 new; P30 0.62, 0.61, 0.59 old against 0.60, 0.57, 0.60 new. Recovery: revert the commits.

## ux_reference

N/A — check messages only; no visible UI.

## Verification

Result: Passed
Evidence: `uv run --frozen pytest -q tests/test_strict_refusals.py tests/test_dart_exclusions.py tests/test_comments.py`: 569 passed at 71204636; after the cache removal, `tests/test_strict_refusals.py tests/test_comments.py`: 538 passed. Before each fix its new cases failed (the last 8 near-miss cases on 0d51fefe). Timing is in Risks + recovery.
Review: a fresh review of 33570c48 found raw-read marks passing inside strings, JSX and Swift misreads, Dart `${...}` strings, brace and nested-folder Dart excludes, and a slower suppression pass; a fresh review of 353d254a found a division after a non-null `!` or postfix `++` opening a false regex, JSX in `.js`, flake8 `noqa` and isort marks read on the raw line, and folder-form Dart excludes. A fresh review of 0d51fefe found Pyre marks hidden inside Python strings (Pyre reads them on the raw line) and JavaScript slashes misread after `o.in`, `$in`, `d.with(1)`, `...`, `export default` and `return!`. Each is fixed with a failing test first. A run of these hooks in an installed project found the in-process cache refused by Hard Eng's own Semgrep rule; it is removed. Not fixed: an `if (` condition longer than 200 characters before a regex, because the back scan has a 200-character window to keep each slash cheap. Pending: a fresh review of the final head.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: (1) three fresh reviews found switch-off forms read the wrong way and Dart excludes judged in the wrong folder → `tests/test_strict_refusals.py::test_switch_off_after_a_literal_or_a_gitleaks_mark_in_one_fails` and `tests/test_dart_exclusions.py::test_an_inherited_pattern_with_braces_or_a_partial_double_star_is_refused` hold each case; (2) Hard Eng's Semgrep rule refused the in-process cache in an installed project's run of these hooks → None — the push's security gate holds the same rule; that run only came first; (3) the push refused a Ready plan → None — the refusal named the step.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
