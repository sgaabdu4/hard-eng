# Read Rust test names in plan acceptance lines

Status: Ready

## Outcome + scope

A Complete plan that names a Rust test as `path::name` passes when that function has a `#[test]` attribute (or a path form such as `#[tokio::test]`), in `tests/` or in a `src/` unit test module. A function with no test attribute, or one only on comment lines, still counts as missing. Non-goals: other languages, other plan checks.

## Sources + coverage

Sources: N/A — found by a CI run: an installed Rust project's Complete plan named an existing test, `tests/cli_unused_public_members.rs::strict_check_checks_the_members_of_classes_declared_in_entry_files`, and the check said it does not exist.

## Repository context

Owners: `missing_tests` in `.hooks/plans.py` holds one definition pattern per file kind; `.rs` had none, so it fell back to a quoted name, which a Rust test never has. `_is_test` accepts a path in a test folder or with a test file name; Rust unit tests live in `src/` files, so `.rs` files are accepted by the test attribute instead.
Same cause: N/A — searched `missing_tests` and `_is_test` for other file kinds that define tests by a function header: Python and Swift have patterns; JavaScript, Dart and Ruby name tests in quotes, which the fallback reads.
Single source: N/A — the patterns have one owner, the table in `missing_tests`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. AGENTS.md line 10 covers Hard Eng design calls; the user approved PRs for the strict rollout (2026-11-15 06:12), which this fault blocks.

## Acceptance + steps

- [ ] A Rust test in `tests/` and a Rust unit test in a `src/` test module count, and the same lines commented out do not → `tests/test_plan_acceptance.py::test_a_test_named_only_on_a_comment_line_does_not_count`.
- [ ] A Rust function with no test attribute does not count → `tests/test_plan_acceptance.py::test_a_rust_function_without_a_test_attribute_is_not_a_test`.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16, develop 80756642 passed CI. On it, the two new Rust cases of `test_a_test_named_only_on_a_comment_line_does_not_count` fail (the real `#[test]` function reads as missing); the other 84 tests in the file pass.
Execution: One builder, this session.

## Risks + recovery

A Rust function name that matches only inside a string or a macro could count. The pattern needs the attribute right before `fn`, with only other attributes between. Recovery: revert the commit.

## ux_reference

N/A — a check message only; no visible UI.

## Verification

Result: Pending
Evidence: Pending
Review: Pending
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: Pending
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
