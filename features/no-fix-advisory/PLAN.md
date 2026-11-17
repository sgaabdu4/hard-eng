# The vulnerabilities gate passes a vulnerability that no release fixes

Status: Draft

## Outcome + scope

The vulnerabilities gate passes a reported vulnerability when public data proves that no fixed release exists, and prints a line on each run that says it will fail once a fix exists. Non-goals: a project-side entry, date, reason or setting; a new config key; a change for the image scan, the Stop hook or the Bash hook.

## Sources + coverage

Sources: N/A — the request is the only source.
Deliverables: None

## Repository context

Owners: `.hooks/osv_report.py` (the OSV report checks, moved from `.hooks/reports.py`), `.hooks/osv_unfixed.py` (the proof), `.hooks/freshness.py` (registry readers), `.hooks/gate_runner.py::run_limited_gate` (the exit code decides the gate).
Same cause: the cause is a rule that fails on each reported vulnerability, with no case where no project change can clear it. Seen on the advisory for picomatch, whose range ends at `last_affected` 4.0.7 while the newest npm release is 4.0.7. Searched for other readers of the report: `.hooks/debt.py::osv_findings` reads it only after a failed gate, so it needs no change. The image scan (`validate_osv_image`) never gets the new mode.
Single source: registry readers live in `.hooks/freshness.py` only; the new npm and PyPI readers sit beside `pub_versions`, and `pypi_eligible` now calls the same `pypi_releases` reader. The advisory record comes from the OSV report itself (checked on a real report: each record holds `affected[].ranges[].events`), so no second reader of api.osv.dev exists. The OSV validators moved from `reports.py` to `osv_report.py` because `reports.py` and `gate_runner.py` stand at the 1000 line limit (HE-FILE-LENGTH); `reports.py` imports them again, so each caller keeps its name.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner decided the design and said not to widen it; the rule that Hard Eng changes only when no project change can pass applies, because no release fixes this advisory.
Decisions:

1. A vulnerability passes only when both hold. (a) In the report's record, no `affected` entry for the package and ecosystem has a `fixed` event in any range, and every event is `introduced` or `last_affected`. (b) The registry lists no release above the lowest `last_affected` of the package, and, for a range with no end, nothing is above. Any other case fails as before, with the proof that failed named in the message.
2. The scanner must exit 1 (vulnerabilities found), the report must validate in full, each vulnerability of each package must pass, and at least one must exist. Any other exit code fails.
3. The version order only passes when it is certain. A release with a higher number than `last_affected` fails, also a pre-release such as 4.1.0-beta.1 and a `.postN` release. A pre-release of the same number (4.0.7-rc.1) is below it and passes. A version that cannot be read, a `last_affected` that is not a release, a `limit` event, an installed version above the bound, a group id with no record and a record for another package all fail.
4. Ecosystems: npm, PyPI and Pub have a reader. Any other ecosystem fails as before.
5. A registry that cannot be read fails with the reason; no retry.
6. The registry is read only after check (a) passes, and only in the vulnerabilities gate. A report with no vulnerability reads nothing. The new modules load inside the failing-scan branch, so the Stop and Bash hooks load nothing new.

Limit: an advisory that never gets a fix passes with no end date. It is printed on every run and fails the day a fixed release appears. A package with several ranges uses the lowest `last_affected`, so it fails sooner, never later.

## Acceptance + steps

- [ ] An advisory with a `last_affected` and no fixed event passes when the registry has nothing above it, and is printed with package, version and id → `tests/test_osv_unfixed.py::test_an_advisory_with_no_fix_and_no_newer_release_passes_and_is_printed`
- [ ] The same advisory with a `fixed` event fails and reads no registry → `tests/test_osv_unfixed.py::test_an_advisory_with_a_fixed_event_fails_without_a_registry_read`
- [ ] A release above the range, or one that cannot be read, fails; one inside or below it does not → `tests/test_osv_unfixed.py::test_a_release_above_the_affected_range_or_an_unreadable_one_fails`, `tests/test_osv_unfixed.py::test_a_release_inside_or_below_the_affected_range_does_not_fail`
- [ ] A python advisory passes, and a newer release fails; an ecosystem with no reader fails → `tests/test_osv_unfixed.py::test_a_python_advisory_with_no_fix_passes_and_a_newer_release_fails`, `tests/test_osv_unfixed.py::test_an_ecosystem_with_no_registry_reader_fails`
- [ ] A registry that cannot be read fails and says so; a clean report reads no registry → `tests/test_osv_unfixed.py::test_a_registry_that_cannot_be_read_fails_and_says_so`, `tests/test_osv_unfixed.py::test_a_clean_report_reads_no_registry`
- [ ] The runner passes exit 1 with only unfixed advisories, and fails on a fixable one, on any other exit code and on exit 1 with no finding → `tests/test_osv_unfixed.py::test_the_gate_passes_when_the_scanner_found_only_advisories_with_no_fix`, `tests/test_osv_unfixed.py::test_the_gate_fails_when_one_advisory_has_a_fix`, `tests/test_osv_unfixed.py::test_the_gate_fails_on_any_scanner_exit_other_than_found_vulnerabilities`, `tests/test_osv_unfixed.py::test_the_gate_fails_when_the_scanner_exits_1_and_the_report_holds_no_finding`
- [ ] The real gate passes on a lockfile with picomatch 4.0.7 and fails on one with lodash 4.17.20 → real run, recorded under Verification

## Baseline + execution

Result: Passed
Evidence: the starting code is `origin/main` at c5068084, which passed each of its 8 checks on GitHub; the reports and freshness tests passed before the change.
Execution: one builder; tests first and shown red, then the change, the focused tests, the static gates, the real lockfile run and the Complete gate.

## Risks + recovery

- A fix may ship while a project still passes on stale data: the registry is read on each run, so the gate fails on the next run after the release.
- A registry outage fails the gate for a project that holds such an advisory; a rerun is the repair.
- Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes; the change is one gate result and one printed line.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — no user journey changes; the gate runs inside checks.
Real service: Required — npm registry and OSV scanner: the changed gate runs one time on a lockfile with picomatch 4.0.7 and one time on a lockfile with lodash 4.17.20.
Retro: Pending

Delivery target: PR
Delivery: Pending — the pull request and its checks.
