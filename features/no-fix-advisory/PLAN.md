# The vulnerabilities gate passes a vulnerability that no release fixes

Status: Complete

## Outcome + scope

The vulnerabilities gate passes a reported vulnerability when public data proves that no fixed release exists, and prints a line on each run that says it will fail once a fix exists. Non-goals: a project-side entry, date, reason or setting; a new config key; a change for the image scan, the Stop hook or the Bash hook.

## Sources + coverage

Sources: N/A — the request is the only source.
Deliverables: None

## Repository context

Owners: `.hooks/osv_report.py` (the OSV report checks, moved from `.hooks/reports.py`), `.hooks/osv_unfixed.py` (the proof), `.hooks/freshness.py` (registry readers), `.hooks/gate_runner.py::run_limited_gate` (the exit code decides the gate).
Same cause: the cause is a rule that fails on each reported vulnerability, with no case where no project change can clear it. Seen on the advisory for picomatch, whose range ends at `last_affected` 4.0.7 while the newest npm release is 4.0.7. Searched for other readers of the report: `.hooks/debt.py::osv_findings` is read for a gate that failed, and `judge` reads no finding for a gate that passed, so a gate that now passes records no new debt. A project whose debt file lists the picomatch finding is told once that the listed finding is fixed, as for any fixed finding, and removes the line. The image scan (`validate_osv_image`) never gets the new mode.
Single source: registry readers live in `.hooks/freshness.py` only; the new npm and PyPI readers sit beside `pub_versions`, and `pypi_eligible` now calls the same `pypi_releases` reader. The advisory record comes from the OSV report itself (checked on a real report: each record holds `affected[].ranges[].events`), so no second reader of api.osv.dev exists. The OSV validators moved from `reports.py` to `osv_report.py` because `reports.py` and `gate_runner.py` stand at the 1000 line limit (HE-FILE-LENGTH); `reports.py` imports them again, so each caller keeps its name.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner decided the design and said not to widen it; the rule that Hard Eng changes only when no project change can pass applies, because no release fixes this advisory.
Decisions:

1. A vulnerability passes only when both hold. (a) In the report's record, no `affected` entry for the package and ecosystem has a `fixed` event in any range, and every event is `introduced` or `last_affected`. (b) The registry lists no release above the lowest `last_affected` of the package. A range with no end passes only when it starts at 0, and then the registry is read as well: a release above the installed version fails, because real records of this shape often have a fix that the record does not list (grapesjs 0.19.4 and ldapauth 2.2.3 carry it only in `last_known_affected_version_range`, and an old vyper only in an alias). An installed pre-release is ordered by its own suffix: a release other than the installed one fails unless it is a known pre-release of an installed release. An advisory with an open range and a closed range keeps both: the registry is read against the installed version and the installed version must not pass the closed end. A suffix that is not a known pre-release form fails whatever its number, so a PyPI epoch release fails. Any other case fails as before, with the proof that failed named in the message.
2. The scanner must exit 1 (vulnerabilities found), the report must validate in full, each vulnerability of each package must pass, and at least one must exist. Any other exit code fails.
3. The version order only passes when it is certain. A release with a higher number than `last_affected` fails, also a pre-release such as 4.1.0-beta.1. A suffix passes only in a known pre-release form of its ecosystem (npm: `-rc.1` and `+build`; Pub: `-rc.1`; PyPI: `rc1`, `a1`, `.dev1`); each other suffix, such as `.post1`, `-1`, an epoch or a Pub `+1`, may sort above the release and fails. A version that cannot be read, a `last_affected` that is not a release, a `limit` event, an installed version above the bound, a group id with no record and a record for another package all fail.
4. Ecosystems: npm, PyPI and Pub have a reader. Any other ecosystem fails as before.
5. A registry that cannot be read fails with the reason; no retry.
6. The registry is read only after check (a) passes, and only in the vulnerabilities gate. A report with no vulnerability reads nothing. `osv_unfixed` and `freshness` load inside the failing-scan branch; `osv_report` also loads lazily: `reports.py` holds thin functions that import it when the vulnerabilities gate runs, and a check showed that importing `reports` loads none of `osv_report`, `osv_unfixed` or `freshness`.

7. A record that is a malicious package record (id `MAL-`, or CWE-506 on a reviewed advisory; the real report holds the origins key of the malicious-packages feed only together with the `MAL-` id, so that key is no check of its own) never passes, and neither does a record with a `withdrawn` field. `reports.py` loads `osv_report` only inside the vulnerabilities gate; `tests/test_osv_unfixed.py::test_loading_the_hook_and_gate_modules_loads_no_osv_module` holds that. Measured on the real `check --quick` run with `-X importtime`: 184 modules before and after, the same set, none of `reports`, `osv_report`, `osv_unfixed`, `freshness`.
Limit: an advisory that never gets a fix passes with no end date. It is printed on every run and fails the day a fixed release appears. A malicious package record never passes: the real report of a malicious npm package (flatmap-stream 0.1.1, hand-made lockfile, not installed) holds the id `MAL-2025-20690`, the key `malicious-packages-origins` and, in its reviewed advisory, CWE-506; each mark fails the gate. A record with a `withdrawn` field fails too; no real report with one was found, so that row uses a made record. Fail closed: a registry error, a timeout, bad JSON, a package missing from the registry and an ecosystem with no reader each fail the gate (all held before; tests added).

## Acceptance + steps

- [x] An advisory with a `last_affected` and no fixed event passes when the registry has nothing above it, and is printed with package, version and id → `tests/test_osv_unfixed.py::test_an_advisory_with_no_fix_and_no_newer_release_passes_and_is_printed`
- [x] The same advisory with a `fixed` event fails and reads no registry → `tests/test_osv_unfixed.py::test_an_advisory_with_a_fixed_event_fails_without_a_registry_read`
- [x] A release above the range, or one that cannot be read, fails; one inside or below it does not → `tests/test_osv_unfixed.py::test_a_release_above_the_affected_range_or_an_unreadable_one_fails`, `tests/test_osv_unfixed.py::test_a_release_inside_or_below_the_affected_range_does_not_fail`
- [x] A python advisory passes, and a newer release or a suffix that may sort above it fails; a Pub build suffix fails; a range with no end that starts after 0 fails; a report with no results is not accepted; an ecosystem with no reader fails → `tests/test_osv_unfixed.py::test_a_python_release_that_may_sort_above_the_bound_fails`, `tests/test_osv_unfixed.py::test_a_pub_build_suffix_sorts_above_its_release_and_a_pre_release_below`, `tests/test_osv_unfixed.py::test_a_range_with_no_end_that_starts_after_zero_fails`, `tests/test_osv_unfixed.py::test_a_report_the_scanner_wrote_with_no_results_is_not_accepted`, `tests/test_osv_unfixed.py::test_a_python_advisory_with_no_fix_passes_and_a_newer_release_fails`, `tests/test_osv_unfixed.py::test_an_ecosystem_with_no_registry_reader_fails`
- [x] A registry that cannot be read fails and says so; a clean report reads no registry → `tests/test_osv_unfixed.py::test_a_registry_that_cannot_be_read_fails_and_says_so`, `tests/test_osv_unfixed.py::test_a_clean_report_reads_no_registry`
- [x] The runner passes exit 1 with only unfixed advisories, and fails on a fixable one, on any other exit code and on exit 1 with no finding → `tests/test_osv_unfixed.py::test_the_gate_passes_when_the_scanner_found_only_advisories_with_no_fix`, `tests/test_osv_unfixed.py::test_the_gate_fails_when_one_advisory_has_a_fix`, `tests/test_osv_unfixed.py::test_the_gate_fails_on_any_scanner_exit_other_than_found_vulnerabilities`, `tests/test_osv_unfixed.py::test_the_gate_fails_when_the_scanner_exits_1_and_the_report_holds_no_finding`
- [x] A range open from 0 fails when the registry has a newer release than the installed one, and passes when the installed one is the newest → `tests/test_osv_unfixed.py::test_a_range_open_from_zero_fails_when_the_registry_has_a_newer_release`, `tests/test_osv_unfixed.py::test_a_range_open_from_zero_passes_when_the_installed_release_is_the_newest`
- [x] An installed pre-release fails when a later release exists, and an advisory that has an open and a closed range counts as open → `tests/test_osv_unfixed.py::test_an_installed_pre_release_fails_when_a_later_release_exists`, `tests/test_osv_unfixed.py::test_an_installed_pre_release_passes_when_it_is_the_newest`, `tests/test_osv_unfixed.py::test_an_open_range_still_counts_when_the_same_advisory_has_a_closed_range`, `tests/test_osv_unfixed.py::test_the_closed_range_of_a_mixed_advisory_still_bounds_the_installed_release`, `tests/test_osv_unfixed.py::test_a_python_epoch_release_is_above_the_installed_one_for_an_open_range`
- [x] The lowest `last_affected` of several advisories sets the bound, and a retracted Pub release is not a fix → `tests/test_osv_unfixed.py::test_the_lowest_last_affected_of_several_advisories_sets_the_bound`, `tests/test_osv_unfixed.py::test_a_pub_release_that_was_retracted_is_not_a_fix`
- [x] A malicious package record and a withdrawn record fail → `tests/test_osv_unfixed.py::test_a_malicious_package_record_never_passes_as_having_no_fix`, `tests/test_osv_unfixed.py::test_a_record_that_is_withdrawn_but_still_reported_fails`
- [x] A registry error, a timeout, bad JSON and a package missing from the registry fail → `tests/test_osv_unfixed.py::test_a_registry_that_fails_or_lacks_the_package_fails_the_gate`
- [x] No hook or gate module loads the OSV modules → `tests/test_osv_unfixed.py::test_loading_the_hook_and_gate_modules_loads_no_osv_module`
- [x] The real gate passes on a lockfile with picomatch 4.0.7 and fails on one with lodash 4.17.20 → N/A — a one-time real run against the scanner and the registry, recorded under Verification

## Baseline + execution

Result: Passed
Evidence: the starting code is `origin/develop` at 1f2a45c6, which passed its 10 checks on GitHub (hard-eng, hard-eng-checks, 6 test shards, canary, canary targets); the branch was first cut from `origin/main` at c5068084 and moved onto `develop`.
Execution: one builder; tests first and shown red, then the change, the focused tests, the static gates, the real lockfile run and the Complete gate.

## Risks + recovery

- A fix may ship while a project still passes on stale data: the registry is read on each run, so the gate fails on the next run after the release.
- A registry outage fails the gate for a project that holds such an advisory; a rerun is the repair.
- Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes; the change is one gate result and one printed line.

## Verification

Result: Passed
Evidence: the new tests failed first (27 of 33 failed, the 6 others being cases that already failed as before); the rows added after review failed on the earlier code too, as did the malware rows and the import test (3 and 1). The open-range repros (4) failed on the earlier code; flipping the bound to the highest `last_affected` fails the bound test. The challenge repros (6) failed on the earlier code. All 66 pass. The full suite run directly passed 5351 of 5353 tests; 2 timed out under machine load and passed alone. The first local Complete run passed each gate outside the tests; its tests gate timed out at 1800 s under load, so that run did not pass, and the direct full-suite run above stands in for it. The push runs the Complete check again, and its result is the push itself. Hosted CI on the pull request is the remote proof; its result is in the Delivery line.
E2E: N/A — no user journey changes; the gate runs inside checks.
Real service: Passed — npm registry, OSV scanner: the real gate command ran through `run_limited_gate` on a Bun lockfile with picomatch 4.0.7. The scanner exited 1, the registry listed 35 releases with 4.0.7 the newest, the gate printed `OSV: picomatch@4.0.7 GHSA-fc5q-39xc-vjpf: no fixed release exists yet, so this passes; it will fail as soon as a fixed release exists` and ended `PASS vulnerabilities (exit 1)`. The same command on a lockfile with lodash 4.17.20 failed with `not proven unfixable: GHSA-29mw-wpgm-hmr9: it has a fixed event`. The real report holds `affected[].package`, `ranges[].events` and `groups[].ids`, which are the fields the code reads and the tests build; the tests lack the other fields of the real record. The readers ran once for npm (picomatch and the scoped package @babel/core), PyPI (requests) and Pub (http); each returned a list of versions. Compared: 7 real reports (picomatch, lodash, flatmap-stream, grapesjs, ldapauth, vyper, ecdsa), 7 read the same way by the code and by the test shapes; the grapesjs, ldapauth and vyper reports are fixtures and each repro failed before the open-range fix. The real gate on them: grapesjs 0.19.4, ldapauth 2.2.3, vyper 0.3.7 and flatmap-stream fail; picomatch 4.0.7 and ecdsa 0.19.2 pass. The version order was compared with the real tools on real release lists: 224207 PyPI pairs against `packaging.version` and 54499 npm pairs against Bun's semver, 0 pairs where the tool says higher and the code says not above. Not caused: a registry refusal, because a public read has none to handle.
Retro: (1) The fault escaped to the base branch: no test gave the gate an advisory with no fix → `tests/test_osv_unfixed.py::test_the_gate_passes_when_the_scanner_found_only_advisories_with_no_fix`, which failed first. (2) The first design put the check in the report validator, but the runner fails on the scanner's exit code, so the report check alone would still fail the gate → the same test, which runs the runner. (3) `reports.py` and `gate_runner.py` stood at the 1000 line limit, so the OSV validators moved to their own module → HE-FILE-LENGTH. (4) A test helper copied the fake registry of the freshness tests, and the duplicates gate refused it → the helper now imports that fake.

Review declined: an open range can pass when an earlier release than the installed one already fixed it (grapesjs, 0.19.6 installed, fix 0.19.5 in a side field) :: the pass then only happens for an installed release that is above the real fix, so it is not affected; for any affected installed release the fix is a later release, which the registry read finds and fails on.
Delivery target: Merge
Delivery: Pending — hosted CI on pull request 645 at the final head, then merge into `develop`; the earlier head 28ca5e08 passed 24 checks before the open-range fix.
