# Hot-path rules fail old code

Status: Draft

## Outcome + scope

Every Semgrep `security` gate in every project that uses Hard Eng runs the HE-HOT-PATH rules on the whole repository, and every rule fails the gate: constant regexes in functions, boolean arrays, whole-row and whole-entity reads, in-process caches, awaits in loops, independent awaits in sequence, URL parsing in loops and JSON columns. Each rule skips the shapes where the slow form is needed. Hard Eng's own `.hooks/` code passes the rules. Non-goals: blobless CI clones, a CI step split and test sharding.

## Repository context

Owners: `prepare_command` in `.hooks/hard-eng.py` already adds `.agents/skills/he/semgrep/python.yaml` to Python security gates at run time, so a change there reaches installed projects without new gate files. `debt.py` records Semgrep report findings, so `adopt` covers old findings at install. `hot_paths.py` held the added-lines scan and the `hot-paths` listing.
Same cause: `features/hot-path-checks` made the judgment rules notes and kept old code passing, because HE-DEBT-SHRINK-ONLY gives updates no debt path. The maintainer accepted that installed projects must fix old findings when they update.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer asked to enforce every rule on old projects too, make the judgment rules fail, close the known gaps, review adversarially with an Opus subagent, merge into `develop` and release to `main`.
Decided: no suppression path exists (HE-NO-SWITCH-OFF), so each blocking rule skips a loop that stops early (`break` or `return`), updates a value its condition reads, or sleeps on purpose; a URL parse of the loop item or of a value the loop builds; `INSERT INTO ... SELECT *`; SQL and JSON words in comments. `.agents/` and test files stay out of scope.

## Acceptance + steps

- [ ] Each rule fires on its annotated fixture line and nowhere else, including the passing loop, URL, SQL, JSON and comment shapes → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [ ] A Semgrep security gate fails on slow code that is already committed, and other gates do not get the rules → `tests/test_hot_paths.py::test_every_security_gate_fails_old_slow_code`.
- [ ] `hot-paths` lists every finding and fails while any remain → `tests/test_hot_paths.py::test_a_repository_scan_lists_every_finding_and_fails`.
- [ ] Python and other security gates get the rule file and the 60 s rule limit → `tests/test_tool_execution.py::test_security_scan_gives_each_rule_time_to_finish_under_load` and `tests/test_tool_execution.py::test_python_security_gate_replaces_only_the_registry_sha1_rule`.
- [ ] Hard Eng's own code has no finding → `python3 .hooks/hard-eng.py hot-paths` prints `HE-HOT-PATH: 0 findings`.

## Baseline + execution

Result: Passed
Evidence: `develop` 209f27b `hard-eng` CI passed. With `.hooks/` in scope, `hot-paths` found 115 cases in Hard Eng's own code: 113 constant regexes in functions, one URL parse of a value the loop builds (now skipped by the rule) and one `functools.cache`.
Execution: One builder in this session; one Sonnet subagent moves Hard Eng's own regexes to module level; an Opus subagent reviews the diff adversarially until no verified finding remains.

## Risks + recovery

Installed projects with old findings fail `check` and CI after they update, and must fix each one; a project installing Hard Eng can record them once with `adopt`. A loop that must run in order but does not stop early, update its condition or sleep has no passing shape and must be rewritten. Recovery: revert the merge.

## ux_reference

N/A — command-line checks and skill text; no visual surface.

## Verification

Result: Pending
Evidence: Pending.
E2E: Pending — the security gate command runs on a real repository in `tests/test_hot_paths.py`, and `hot-paths` runs on this repository.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green, then the `develop` → `main` release PR.
