# Read Rust test names in plan acceptance lines

Status: Complete

## Outcome + scope

A Complete plan that names a Rust test as `path::name` passes when that function has a test attribute (`#[test]`, a path form such as `#[tokio::test]`, `#[rstest]`, `#[test_case(...)]`, `#[test_matrix(...)]`, `#[wasm_bindgen_test]`, `#[quickcheck]` or `#[gtest]`, with or without arguments, which may hold strings, char literals, slices and `vec![...]`, with other attributes and line comments between), in `tests/` or in a `src/` unit test module, in Acceptance and Retro lines. A function with no test attribute, or one only on comment lines, still counts as missing. A Same cause line names code, so only its test-folder names are read as tests, as for other languages. A long stack of attribute arguments is read at once. Non-goals: other languages, other plan checks.

## Sources + coverage

Sources: N/A — found by a CI run: an installed Rust project's Complete plan named an existing test, `tests/cli_unused_public_members.rs::strict_check_checks_the_members_of_classes_declared_in_entry_files`, and the check said it does not exist.

## Repository context

Owners: `missing_tests` in `.hooks/plans.py` holds one definition pattern per file kind; `.rs` had none, so it fell back to a quoted name, which a Rust test never has. `_is_test` accepts a path in a test folder or with a test file name; Rust unit tests live in `src/` files, so `.rs` files are accepted by the test attribute instead.
Same cause: `claimed_tests` (Same cause and Retro lines) used the same path rule, so it skipped a Rust `src/` name with no check. Retro lines now use `names_tests`; Same cause lines name code, so they keep `_is_test`, as for every other language. Searched `missing_tests` and `_is_test` for other file kinds that define tests by a function header: Python and Swift have patterns; JavaScript, Dart and Ruby name tests in quotes, which the fallback reads.
Single source: the Rust form lives once in `RUST_TEST`; the path rule for named tests lives once in `names_tests`. Reading named tests moved from `.hooks/plans.py` to its owner `.hooks/plan_tests.py`, because `plans.py` passed 1000 lines.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. AGENTS.md line 10 covers Hard Eng design calls; the user approved PRs for the strict rollout (2026-11-15 06:12), which this fault blocks.

## Acceptance + steps

- [x] A Rust test in `tests/` and a Rust unit test in a `src/` test module count, and the same lines commented out do not → `tests/test_plan_acceptance.py::test_a_test_named_only_on_a_comment_line_does_not_count`.
- [x] Each real Rust test form counts: attribute arguments, a line comment after an attribute, a `]` inside a quoted attribute value, `#[rstest]`, `#[test_case(...)]`, `pub(crate) fn`, slices, `vec![...]` and char literals in arguments → `tests/test_plan_acceptance.py::test_each_rust_test_form_counts`.
- [x] A Same cause line may name Rust source code: a function, a method, a struct, a const, or a bare file name → `tests/test_plan_acceptance.py::test_a_same_cause_line_may_name_rust_source_code`.
- [x] A stack of 40 char cases is read in under 1 s → `tests/test_plan_acceptance.py::test_stacked_char_cases_are_read_at_once`.
- [x] A made-up Rust `src/` name in a Retro line is reported → `tests/test_plan_acceptance.py::test_a_missing_rust_unit_test_in_a_retro_line_is_reported`.
- [x] A Rust function with no test attribute does not count → `tests/test_plan_acceptance.py::test_a_rust_function_without_a_test_attribute_is_not_a_test`.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16, develop 80756642 passed CI. On it, the two new Rust cases of `test_a_test_named_only_on_a_comment_line_does_not_count` fail (the real `#[test]` function reads as missing); the other 84 tests in the file pass. With the final tests, develop's code fails 25 and passes 92; the 7 that pass there guard against new wrong refusals and slow reads.
Execution: One builder, this session.

## Risks + recovery

A Rust function name that matches only inside a string, a macro or a block comment could count, as for the other languages. The pattern needs the attribute right before `fn`, with only other attributes and whole line comments between; each attribute argument and each comment reads one way. Recovery: revert the commit.

## ux_reference

N/A — a check message only; no visible UI.

## Verification

Result: Passed
Evidence: `uv run --frozen pytest -q tests/test_plan_acceptance.py`: 117 passed; before each fix its new cases failed (2, then 9, then 8, then 8 plus the time case, then 2 plus the comment time case). A file of 20,000 attributed tests is read in 0.05 s, and 400 stacked char cases in 0.04 s. On the installed Rust project's real file, `missing_tests` finds `strict_check_checks_the_members_of_classes_declared_in_entry_files` and still reports a made-up name and a plain function. `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Ready`: exit 0, 20 gates PASS.
Review: a fresh review of 295114b4 found three refused real forms (attribute arguments, a trailing line comment, a `]` in a quoted value) and the Retro path gap. A fresh review of d6df5290 found refused slice, `vec!` and char literal arguments, and Same cause lines that name Rust source code refused. A fresh review of 32485aae found that a line comment after an attribute could stop part way, so 16 `//` took 8 s and a name inside the comment counted; a comment now runs to its line end (1000 `//` take 0.001 s). A fresh review of 245839d7 found exponential time on stacked char cases (20 cases took 1.3 s, 22 took 28 s), Same cause lines that name a struct, const or bare file refused, and refused `wasm_bindgen_test`, `test_matrix`, `quickcheck`, `gtest` and `unsafe fn` forms. Each is fixed with a failing test first; each argument now reads one way, so 400 stacked cases take 0.04 s. Pending: a fresh review of the final head.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: (0) the pre-push tests gate stopped twice at the 900 s push budget, at 96% with no failure, while builders loaded the Mac; the owner's rule sets a time limit at about 3 times the normal run (489 to 600 s), so `hard-eng.gates.json` `pre_push_seconds` is now 1800 → None — the limit now follows that rule; (1) CI of an installed Rust project refused a plan that named a real Rust test → `tests/test_plan_acceptance.py::test_a_test_named_only_on_a_comment_line_does_not_count` now holds Rust cases; (2) the push refused the change without a plan, because `.hooks/plans.py` always needs one → None — the refusal named the step.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
