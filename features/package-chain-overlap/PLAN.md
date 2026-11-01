# Run the gate chains of separate packages at the same time

Status: Complete

## Outcome + scope

`check` runs the serial gates of one package beside the serial gates of another package, and parallel gates beside the serial gates of their own package, so the iOS tests of a Flutter app run while its Dart tests and analyzer run. Each limit that made gates wait stays, but applies only to the gates it affects: dependency setup still runs first and alone, a performance suite still runs alone, a gate that may write files still finishes before the gates of related packages that read them, and JavaScript tests, which clear `coverage/`, still never run beside another gate in the same folder. At most `max(2, CPUs / 4)` serial gates run at once, because a test runner uses every core. Every gate still runs and every failure is still reported. Non-goals: the CI job layout, the gate commands, the roles, the per-gate time limit.

## Repository context

Owners: the order and the waiting rules move from `.hooks/reports.py` (`gate_order`, `scan_blockers`, the role sets) to the new `.hooks/gate_schedule.py`, which also runs the gates; `run_gates` in `.hooks/hard-eng.py` passes it `run_gate`. Both old files were at 990 of the 1000 lines that HE-FILE-LENGTH allows. `.hooks/process_group.py` keeps the set of running process groups, so an interrupt still stops a gate that now runs in a worker thread, and after an interrupt it starts no new command until the run ends.
Evidence: today `run_gates` runs each serial gate alone and makes every later gate wait for it. `gate_order` places scans after the last gate in the whole list that may write files, so in a project whose last package has a generator, every gate of every earlier package runs first, one at a time. In CI logs of Flutter apps with an iOS package, the Dart tests, the analyzer and the iOS tests run one after another in one macOS job, and the summed gate time is about equal to the job time.
Same cause: earlier speed work started scans beside serial suites (`tests/test_gate_speed.py::test_scans_start_beside_a_serial_suite_listed_before_them`) and moved Swift groups to their own macOS job (`features/swift-checks-on-macos-only/PLAN.md`); both helped, and neither lets two packages' serial gates overlap. A search for `parallel`, `gate_order`, `scan_blockers` and `early_scan` found no other scheduler of gates.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner approved the CI and pre-push speed work on 2026-10-31 and asked for a decision without questions: a PR into `develop`, merged when its checks pass.
Design compared:
- (a) Overlap package chains in one job under a CPU limit. It helps pre-push, which runs on one machine; it helps every CI job that checks more than one package, on Linux and macOS; and it needs no workflow change. On a 4-core runner the gain is limited by CPU contention, so the saving there is less than the length of the shorter chain.
- (b) Split heavy packages into separate CI jobs. This already exists for generated workflows: `migrate_swift_runner` in `.hooks/ci_jobs.py` runs Swift groups in a macOS job and the rest on Linux. It is the larger lever for macOS waits, because it moves the Dart chain off the macOS runner. Projects with a customised workflow keep one macOS job, and the migration leaves them alone with a note; adopting it there is a change in each project's workflow, not in Hard Eng. It does nothing for pre-push.
Decision: build (a) here. The two are complementary: (a) speeds up the projects as they run today and every pre-push; (b) stays the route to fewer macOS minutes.
Rules, as built:
- Order: setup first. A writer (a gate whose role is not read-only) moves ahead of the readers of other packages, but stays after earlier writers, its own package's gates and the readers of packages inside its folder, whose results it may read. A performance suite moves ahead of readers and stays after earlier writers and suites. Scans follow the last writer or suite; the other readers follow the scans.
- Waiting: a gate waits for an earlier gate when either is dependency setup or a performance suite; when both are serial gates of one package; when either is a writer, they are not two parallel gates other than scans, and their packages are related (one folder inside the other, or a `depends_on` path from the whole configuration in either direction); when one is JavaScript tests and the other any gate in the same folder; or when the later is a Fallow gate and the earlier is the tests gate of a package it depends on, whose coverage it may reuse.
- CPU: up to one gate per CPU, of which at most `max(2, CPUs / 4)` are serial.

## Acceptance + steps

- [x] Serial gates of two packages run at the same time → `tests/test_gate_speed.py::test_serial_gates_of_two_packages_run_at_the_same_time` (each gate waits until it sees the other running; failed on the old runner by its 10 s limit).
- [x] When one package fails at once, its next gate still runs beside the other package's gate, and all three failures are reported with exit 1 → `tests/test_gate_speed.py::test_every_failure_is_reported_when_one_package_fails_first` (failed on the old runner).
- [x] A performance suite still runs alone beside another package's serial and parallel gates → `tests/test_gate_speed.py::test_performance_suites_run_alone_beside_other_packages`.
- [x] A generator in a child package is ordered before the readers of its parent, and a generator in the parent stays after the readers inside its folder → `tests/test_gate_speed.py::test_writers_move_ahead_only_of_readers_they_cannot_consume`.
- [x] A scan waits for a writer in its own, a parent or a `depends_on` package and not for one in an unrelated package; JavaScript tests never overlap a scan or any other gate in the same folder, in either order and across groups; a Fallow gate waits for the tests of a package it depends on and not of an unrelated one (found by the independent review); a performance suite waits for scans anywhere; serial gates in one package keep their order and a parallel gate does not wait for a serial reader of its package; serial gates of two packages do not wait for each other → `tests/test_gate_speed.py::test_a_gate_waits_only_for_gates_that_can_disturb_it` (replaces the `scan_blockers` test).
- [x] A parallel gate runs beside a serial gate of its own package → `tests/test_gate_speed.py::test_parallel_gates_run_beside_the_serial_gates_of_their_package` (failed on the first version of this change, which kept parallel gates behind their package's serial ones, by its 10 s limit).
- [x] The existing order and early-scan proofs still pass → `tests/test_gate_speed.py`, `tests/test_swift.py::test_flutter_dependency_setup_runs_before_the_pods_gate`, `tests/test_quick_check.py`.
- [x] An interrupt stops a gate's whole process group although the gate runs in a worker thread, and the gate starts no further command → `tests/test_gate_speed.py::test_an_interrupt_stops_gates_running_in_worker_threads` (the second command started before the stop flag, found by the independent review).
- [x] Stopping kills every running group even while others finish and leave the set → `tests/test_process_group.py::test_stop_groups_kills_every_group_while_others_finish` (raised `Set changed size during iteration` before the snapshot, found by the independent review).
- [x] The gates reference describes the new limits → N/A — documentation text, read in the diff.

## Baseline + execution

Result: Passed
Evidence: `develop` `bb1e34f` before the change: `tests/test_gate_speed.py`, `tests/test_swift.py`, `tests/test_quick_check.py` and `tests/test_process_group.py` passed (98 tests).
Execution: One builder; the module and its tests first, then the interrupt guard, then the documents; a timed full check of a private Flutter app with an iOS package before and after, kept out of this repository.

## Risks + recovery

A gate whose role says it only reads but whose command writes files outside its folder (for example an iOS tests command that regenerates the parent app's code) can now overlap the parent's readers; Hard Eng cannot see such writes, so the project should move that step into a generator gate. Overlapped gates run slower than alone; the per-gate limit of three times the last passing time, at least 600 s, leaves room for two runners sharing the CPUs. On a 4-CPU, 12 GiB runner up to four gates now run at once (two serial, two parallel), so memory, not CPU, is the likely failure mode; the per-gate limit (three times the last pass, at least 600 s) still stops a gate that runs far slower. Recovery: revert this change.

## ux_reference

N/A — gate scheduling with no visible interface.

## Verification

Result: Passed
Evidence: `check --plan-stage Complete --base origin/develop` on the branch rebased onto `develop` `40fe004`: all 20 gates passed, 2110 tests passed, line coverage 91.48%. An earlier full run failed `declarations` (the new module was not listed as first-party for deptry) and `tests/test_runner.py::test_parallel_checks_overlap_up_to_the_cpu_count` (two role-less parallel gates waited for each other as writers); both are fixed in this change. Against the old runner, the two-package overlap test and the failure-report test failed by their 10 s limit. Ruff format, ruff lint, complexity, annotations, pyrefly and vulture report nothing on the changed files.
E2E: N/A — the tests run real `check` processes on real gate commands in temporary repositories; the timed run of a real project is the end-to-end proof, and it stays private.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` check green, merged.
