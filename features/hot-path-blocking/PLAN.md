# Hot-path rules fail old code

Status: Complete

## Outcome + scope

Every Semgrep `security` gate in every project that uses Hard Eng runs the HE-HOT-PATH rules on the whole repository, and every rule fails the gate: constant regexes in functions, boolean arrays, whole-row and whole-entity reads, in-process caches, awaits in loops, independent awaits in sequence, URL parsing in loops and JSON columns. Each rule skips the shapes where the slow form is needed. Hard Eng's own `.hooks/` code passes the rules. Non-goals: blobless CI clones, a CI step split and test sharding.

## Repository context

Owners: `prepare_command` in `.hooks/hard-eng.py` already adds `.agents/skills/he/semgrep/python.yaml` to Python security gates at run time, so a change there reaches installed projects without new gate files. `debt.py` records Semgrep report findings, so `adopt` covers old findings at install. `hot_paths.py` held the added-lines scan and the `hot-paths` listing.
Same cause: `features/hot-path-checks` made the judgment rules notes and kept old code passing, because HE-DEBT-SHRINK-ONLY gives updates no debt path. The maintainer accepted that installed projects must fix old findings when they update.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer asked to enforce every rule on old projects too, make the judgment rules fail, close the known gaps, review adversarially with an Opus subagent, merge into `develop` and release to `main`.
Decided: no suppression path exists (HE-NO-SWITCH-OFF), so each blocking rule skips the shapes that need the slow form: loops that stop early, update a value their condition reads, sleep, read an async stream or run as workers; awaits on one session, connection, transaction, cursor, socket, page or dialog; URL parses of the loop item or of a value the loop builds; `INSERT INTO ... SELECT *`, `CREATE TABLE ... AS`, table functions; JSON and SQL text in comments or quotes; form JSON fields. Generated and vendored files leave the security scan, as whole folders when they hold nothing else. `.agents/` and test files stay out of scope. Semgrep parses the stock Next.js page only in part (a bare `&` in a link), so security gates drop `--strict`: the report check prints each partly parsed line and fails every other scan error. Rule paths are relative to the gate folder, so adopted debt matches on every machine.

## Acceptance + steps

- [x] Each rule fires on its annotated fixture line and nowhere else, including the passing loop, URL, SQL, JSON and comment shapes → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] A Semgrep security gate fails on slow code that is already committed, and other gates do not get the rules → `tests/test_hot_paths.py::test_every_security_gate_fails_old_slow_code`.
- [x] A security gate passes a page Semgrep parses only in part and still fails on slow code in its parsed part → `tests/test_hot_paths.py::test_a_partly_parsed_page_passes_the_gate_but_its_findings_fail_it`.
- [x] `hot-paths` lists every finding and fails while any remain → `tests/test_hot_paths.py::test_a_repository_scan_lists_every_finding_and_fails`.
- [x] Python and other security gates get the rule file and the 60 s rule limit → `tests/test_tool_execution.py::test_security_scan_gives_each_rule_time_to_finish_under_load` and `tests/test_tool_execution.py::test_python_security_gate_replaces_only_the_registry_sha1_rule`.
- [x] Hard Eng's own code has no finding → `python3 .hooks/hard-eng.py hot-paths` prints `HE-HOT-PATH: 0 findings`.

## Baseline + execution

Result: Passed
Evidence: `develop` 209f27b `hard-eng` CI passed. With `.hooks/` in scope, `hot-paths` found 115 cases in Hard Eng's own code: 113 constant regexes in functions, one URL parse of a value the loop builds (now skipped by the rule) and one `functools.cache`.
Execution: One builder in this session; one Sonnet subagent moves Hard Eng's own regexes to module level; an Opus subagent reviews the diff adversarially until no verified finding remains.

## Risks + recovery

Installed projects with old findings fail `check` and CI after they update, and must fix each one; a project installing Hard Eng can record them once with `adopt`. A loop that must run in order but does not stop early, update its condition or sleep has no passing shape and must be rewritten. Recovery: revert the merge.

## ux_reference

N/A — command-line checks and skill text; no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_hot_paths.py` (6 tests) passes: the fixture test counts findings per line across Python, TS, Dart, Swift, SQL and Prisma, including a file with a PEP 695 `type` statement; the gate test runs the real `security` command in an `ios` group, fails on committed slow code, skips a generated file and shows `ios`-relative `app.py:5 Compile this constant regex` in the gate error. `python3 .hooks/hard-eng.py hot-paths` on this repository: `HE-HOT-PATH: 0 findings` after 115 old findings in `.hooks/` were fixed. Full `check --plan-stage Ready` on 8818162: every gate passed, including `security` with the rules; `tests` failed only on the 6 tests that need the Dart and Swift SDKs this machine lacks (2166 passed); they fail on `develop` here too and pass in CI. The first PR run failed the Next.js and OpenNext canaries with `security` exit 3 and 0 findings: the new rules made Semgrep parse the stock `app/page.tsx`, which it parses only in part, and `--strict` failed that. With the fix, the real gate command on a fresh `create-next-app@16.4.0` project exits 0 and prints the four skipped lines. Opus adversarial review, 4 rounds: 11, then 5, then 3, then 1 verified findings, all fixed with fixtures. Known misses, safe direction: loops nested inside a stream or worker loop, JS destructured loop items (Semgrep binds no names in JS destructuring), a `{` alone on the line after a stream-loop header, two independent awaits that destructure their results, Drizzle `json()`. Accepted: an ordered loop that does not stop early, update its condition or sleep must be rewritten.
E2E: Passed — the real Semgrep security gate command ran on a Git repository in `tests/test_hot_paths.py`, and `hot-paths` and `check` ran on this repository.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green, then the `develop` → `main` release PR.
