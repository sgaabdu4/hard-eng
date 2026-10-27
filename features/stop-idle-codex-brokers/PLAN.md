# Open issue sweep: idle Codex brokers, Stop without a session record, own launchers, Xcode 27.1 coverage

Status: Draft

## Outcome + scope

One PR closes every open issue: session start stops idle Codex plugin brokers (#417); a session without a SessionStart record checks once, then skips unchanged turns (#415); Hard Eng's own hook launchers need no shellcheck entry (#414); Swift coverage reads the exported report when `xccov view` cannot load the bundle (#413); #416 needs no change. Non-goals: changing the Codex plugin, a new Stop time budget, Windows process cleanup.

## Repository context

Owners: `.hooks/process_group.py`, `.hooks/agent_hooks.py` (`session_context`, `completion`), `.hooks/project_setup.py::unlisted_shell_scripts`, `.agents/skills/he/templates/hard-eng.swift.json`.
Same cause: #417 — Hard Eng's own Codex review runs through `run_in_group`, which already stops every child; the plugin starts `app-server-broker.mjs serve --endpoint E --cwd F --pid-file P` detached and stops it only on `SessionEnd`; its clients are `codex-companion.mjs` processes. #415 — the unchanged-turn skip needed the SessionStart record, and `test_missing_session_baseline_cannot_skip_verification` keeps the first check; no other Stop path depends on the record. #414 — `is_own` already names every launcher setup writes. #413 — the two vendored `skill-sources` copies are submodules owned upstream. #416 — Stop already runs `check --quick` (format, lint, types, annotations only, `reports.QUICK_ROLES`); tests, coverage and scans run in pre-push and CI; the long waits came from #415 and a test queue held back by machine load.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-27: stop idle brokers in Hard Eng, address every open issue in one PR, run the Codex adversarial review loop with gpt-6-astra before the PR and fix only genuine, substantial findings.

## Acceptance + steps

- [ ] A broker whose folder no longer exists is stopped with its child process → `tests/test_process_group.py::test_stops_broker_whose_folder_is_gone`: both processes end.
- [ ] A broker with no job for its folder is stopped with its child process → `tests/test_process_group.py::test_stops_broker_without_a_job`: both processes end.
- [ ] A broker with a running job stays, for a task worker and for a job in the folder → `tests/test_process_group.py::test_keeps_broker_with_a_running_job`: the broker stays alive.
- [ ] Session start reports the stopped brokers → `tests/test_agent_hooks.py::test_session_reports_stopped_codex_brokers`: the context names the count.
- [ ] A session without a record checks once, then skips an unchanged turn → `tests/test_agent_hooks.py::test_session_without_a_record_checks_once`: one check, then "no code checks run".
- [ ] Hard Eng's own launcher in a tracked hooks folder needs no shellcheck entry; a project hook still does → `tests/test_runner.py::test_own_hook_launcher_needs_no_shellcheck_entry`.
- [ ] Swift coverage falls back to the exported report → `tests/test_swift.py::test_tests_script_reads_exported_coverage_when_xccov_cannot_load_the_bundle`: the report holds the exported coverage. The fallback commands were run against a real Xcode 27.1 result bundle: `xccov view` of the exported report gave the same per-file counts as `xccov view` of the bundle.
- [ ] #416 → N/A — no code change; the PR states the evidence and closes it.

## Baseline + execution

Result: Pending
Evidence: Pending — `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop`.
Execution: One builder, this session; Codex adversarial review loop before the PR.

## Risks + recovery

A broker can be stopped between two jobs of one session. The plugin starts a new broker when the next job finds the old one gone, so the cost is one broker start.

## ux_reference

N/A — hook and template code only; no visible UI.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — the tests start real processes and real hook scripts with fake tools; no user interface.
Delivery target: Merge
Delivery: Pending — `hard-eng` passes on the PR and the PR merges into develop.
