# The two slowest scan tests run as capped parts

Status: Complete

## Outcome + scope

The two hot path tests that each ran one Semgrep scan over all fixtures now run as several smaller scans, each capped at two Semgrep jobs, so the test workers share them and no one test is the last to finish. Non-goals: a higher limit, a removed or weaker test, a change of a rule, a change of the production hot path scan.

## Sources + coverage

Sources: N/A — the request is the only source.
Deliverables: None

## Repository context

Owners: `tests/test_hot_paths.py` (the two tests), `tests/conftest.py` (the collection order hook), `pyproject.toml` (the `scan` marker), `.hooks/hot_paths.py::findings` (one scan; unchanged), `hard-eng.gates.json` (the `tests` gate, `-n auto`, 6 shards that split by test file).
Same cause: one test that makes one long call cannot share workers, so it ends last. Searched the slowest-30 list of the full run. The workflow judge test of `tests/test_agent_checks.py` runs the full check fifteen times, but it took 14 s alone on a quiet machine; its split into 16 cases took 100 CPU seconds instead of 14, so it stays whole. The browser test and the Dart coverage tests each run one dependent chain, so they stay whole too.
Single source: the chunk counts, the Semgrep job cap and the expected parse gaps live once, at the top of `tests/test_hot_paths.py`. Searched `tests/` for other copies of the parse gap list: none.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The maintainer assigned this change. Merge: maintainer, chat 2026-11-20, "yes" to the request to merge PR 665 and PR 666 into `develop`; this PR merges into `develop` by rebase after CI passes.
Decisions:

1. Each of the two tests takes a chunk index. Chunk `i` holds each fixture whose place in the sorted name list is `i` modulo the chunk count, so each chunk mixes languages and sizes. Four chunks for the 481 annotated fixtures; eight for the 1,828 reported inputs.
2. Each chunk keeps the old exact assertions on its own files: the found rule, file and line list equals the annotated or expected list, and the parse gap list equals the expected gaps whose file is in the chunk.
3. One cheap test per fixture folder replaces what a whole scan proved by union: the chunks read each fixture once, each rule id has an annotation, each expected file exists, and each parse gap file exists. With the exact match per chunk, the old claim that every rule fires still holds.
4. Each scan in the two tests passes `--jobs 2`. By default Semgrep starts a worker for each core in each of the 16 test workers. With the cap the same scans used a third of the CPU (user seconds 103 to 169 against 324 to 441) and ended sooner in 6 of 6 pairs. The cap sits in the test calls, because one production scan that runs alone gains from every core.
5. Chunk counts: 6 and 12, 3 and 6, and 4 and 8 were each timed twice, with and without the cap. Their wall times overlapped within the noise of the machine, so no count is shown to win. The middle pair, 4 and 8, is taken.
6. The workflow judge test was split into 16 cases and measured: 100 CPU seconds against 14 for the old test on a quiet machine. It is restored to its old form and is not part of this change.
7. xdist hands each worker a run of neighbouring tests, so the 12 cases first sat on one worker (the full runs gw8 and gw14 held all 12). A hook in `tests/conftest.py` moves the cases marked `scan` apart, so each starts in the first batch of a different worker. The hook reads the worker count from `PYTEST_XDIST_WORKER_COUNT` and the batch size from the xdist rule (tests per worker, divided by 4), so a 4-worker CI shard gets 3 scans per worker and no two annotated scans share one. The next full run put the 12 cases on 12 workers. A second option, `--dist worksteal`, left 10 of 12 on one worker and is not used. Changing the gate command was avoided.

## Acceptance + steps

- [x] Each rule still fires exactly on its annotated lines and nowhere else, over every fixture → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines` (4 cases) and `tests/test_hot_paths.py::test_the_annotated_chunks_cover_every_fixture_and_every_rule`
- [x] The reported inputs keep every expected finding and the exact parse gap list → `tests/test_hot_paths.py::test_exact_reported_inputs_keep_all_expected_findings` (8 cases) and `tests/test_hot_paths.py::test_the_reported_input_chunks_cover_every_input_and_every_expectation`
- [x] Each worker's first batch holds its share of the scan cases, and no two annotated scans share a worker, at 4 and 14 workers → `tests/test_hot_paths.py::test_each_worker_starts_with_its_share_of_the_scan_cases` (3 cases; the 4- and 14-worker cases failed on the old hook, which gave one worker 4 scans and another none; the 5-test case failed on the first fix, which used batches in a run small enough for xdist to send one test to each worker in turn) and `tests/test_hot_paths.py::test_a_filtered_run_spreads_the_scans_that_remain` (a real `-k annotated` collection; it failed while the hook ran before the `-k` filter). A real `-n 4 -k annotated` run put the 4 scans on 4 workers. A real `-n 4` run of the file ran 3 scans on each worker, all in the first 18% of the run.
- [x] The two tests no longer end the run: the longest case is under 125 s in the full run, against 198 to 540 s for the old test → N/A — time on a shared machine has no repeatable test; the timings are in Verification

## Baseline + execution

Result: Passed
Evidence: base `a7909cdb`; a full run without coverage at load 100 passed 7061 tests in 1318 s. The two hot path tests took 441.6 s and 217.5 s.
Execution: one builder; the split, the timing runs, the static gates and the full gate once.

## Risks + recovery

- More Semgrep starts raise total CPU for the split; the cap more than pays that back.
- Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes; the change is test code.

## Verification

Result: Passed
Evidence: focused old and new forms of the two tests at 16 workers: new 58 s and 24 s, old 132 s and 51 s. Full suite as the gate runs it, with coverage: new 612 s and 1037 s, old 997 s and 814 s; the other load on the machine moved the totals by hundreds of seconds, so the totals do not separate the forms. Before the hook, all 12 cases ran on one worker in each full run; after it, on 12 workers (full run 554 s at load 21, 7,221 tests passed). The longest hot path case in the full runs: 52 s and 124 s new, against 371 s and 198 s old (and 539 s and 214 s in an earlier pair). The cheap gates (format, lint, complexity, annotations, pyrefly, vulture) passed.
E2E: N/A — no user journey changes.
Real service: N/A — no outside service is called.
Retro: (1) The fault escaped to the base branch: no check tied the hot path tests to the gate time limit → None — the gate limit already failed the push, and this change shortens the tests. (2) The first split looked right but the measure showed no gain on the whole suite; the extra Semgrep starts raised the CPU use on a saturated machine → None — the cap in Decision 4 fixed it, found by the advisor review of the timings. (3) The agent check test split cost seven times the CPU, so it was restored → None. (4) The independent review found that xdist had put all 12 cases on one worker in my own full runs, which I had not read → None — the hook in Decision 7 fixed it and a full run showed 12 workers. (5) The Ready run found a type fault in the new code (an untyped empty list) → None — fixed before the commit. (6) The independent review found that a 4-worker CI shard still put all four annotated scans on one worker, because the hook used a fixed stride and the test checked list places, not workers → `tests/test_hot_paths.py::test_each_worker_starts_with_its_share_of_the_scan_cases`. (7) The next review found that a focused `-k` run still put two scans on one worker, because the hook ran before pytest dropped the filtered tests → `tests/test_hot_paths.py::test_a_filtered_run_spreads_the_scans_that_remain`.

Delivery target: Merge
Delivery: Pending — required remote proof.
