# The slowest tests run their independent parts as separate cases

Status: Ready

## Outcome + scope

The `tests` gate finishes inside its limit on a busy machine because the three slowest tests, which each ran several independent expensive runs in one call, now run as separate cases that the test workers share: two ran one Semgrep scan over all fixtures, and one ran the full Hard Eng check fifteen times. Non-goals: a higher limit, a removed or weaker test, a change of a rule, a change of the hot path scan in production code.

## Sources + coverage

Sources: N/A — the request is the only source.
Deliverables: None

## Repository context

Owners: `tests/test_hot_paths.py` and `tests/test_agent_checks.py` (the three tests), `.hooks/hot_paths.py::findings` (one scan; unchanged), `hard-eng.gates.json` (the `tests` gate, `-n auto`, 6 shards that split by test file).
Same cause: one test that makes one long call cannot share workers, so it ends last and decides the wall time. Searched the slowest-30 list of the full run. The workflow judge test of `tests/test_agent_checks.py` ran `hard-eng.py check` fifteen times on fixtures, one run for each recorded action list, so it is split the same way. The browser test and the three Dart coverage tests each run one dependent chain (open, capture, read the result; or `dart pub get`, `dart test`, `format_coverage`, assert), so they stay whole; a split would change what each proves.
Single source: the expected parse gaps and the chunk counts live once, at the top of `tests/test_hot_paths.py`. Searched `tests/` for other copies of the parse gap list: none.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The maintainer assigned this change.
Decisions:

1. Each of the two tests takes a chunk index. Chunk `i` holds each fixture whose place in the sorted name list is `i` modulo the chunk count, so each chunk mixes languages and sizes. Six chunks for the 481 annotated fixtures; twelve for the 1,828 reported inputs.
2. Each chunk keeps the old exact assertions on its own files: the found rule, file and line list equals the annotated or expected list, and the parse gap list equals the expected gaps whose file is in the chunk.
3. One cheap test per fixture folder replaces what a whole scan proved by union: the chunks read each fixture once, each rule id has an annotation, each expected file exists, and each parse gap file exists. With the exact match per chunk, the old claim that every rule fires still holds.
4. The workflow judge test becomes one case for each recorded action list (8 that must be judged as missing a passing check, 7 that must not), each in its own fixture folder, plus one test for the failed baseline part. The lists and the asserted text are unchanged.
5. `findings` passes no `--jobs`, so Semgrep starts one worker for each core in each of the 16 test workers. Eight concurrent chunk scans ran in 40 s and 34 s with `--jobs 1` and in 48 s and 48 s with the default, and in 82 s against 131 s on the first pair, on a machine whose load moved between 95 and 250. The gain is real in direction but the machine was not quiet, and `findings` also serves the production scan, where one scan alone gains from every core. No change is made.

## Acceptance + steps

- [ ] Each rule still fires exactly on its annotated lines and nowhere else, over every fixture → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines` (6 cases) and `tests/test_hot_paths.py::test_the_annotated_chunks_cover_every_fixture_and_every_rule`
- [ ] The reported inputs keep every expected finding and the exact parse gap list → `tests/test_hot_paths.py::test_exact_reported_inputs_keep_all_expected_findings` (12 cases) and `tests/test_hot_paths.py::test_the_reported_input_chunks_cover_every_input_and_every_expectation`
- [ ] A workflow judge case still fails each recorded action list that has no passing check after its last edit, passes each list that has one, and the failed baseline judge keeps its asserts → `tests/test_agent_checks.py::test_a_workflow_without_a_passing_check_after_its_last_edit_is_judged`, `tests/test_agent_checks.py::test_a_workflow_with_a_passing_check_after_its_last_edit_is_not_judged` and `tests/test_agent_checks.py::test_a_failed_baseline_is_judged_from_recorded_output`
- [ ] The full test run as the gate runs it ends sooner, with no test removed or loosened and no limit raised → N/A — wall time on a shared machine has no repeatable test; two timed runs of the gate command on each side prove it, and the table is in Verification

## Baseline + execution

Result: Passed
Evidence: base `a7909cdb`; a full run without coverage at load 100 passed 7061 tests in 1318 s. The two hot path tests took 441.6 s and 217.5 s, and the workflow judge test 110.1 s.
Execution: one builder; the split, then the timing runs, then the static gates and the full gate once.

## Risks + recovery

- More Semgrep starts: each start costs CPU, so total CPU rises while wall time falls.
- Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes; the change is test code.

## Verification

Result: Pending
Evidence: pending
E2E: N/A — no user journey changes.
Real service: N/A — no outside service is called.
Retro: Required on Complete plans.

Delivery target: PR
Delivery: Pending — required remote proof.
