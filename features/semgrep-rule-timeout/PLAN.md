# The security gate gives each Semgrep rule 60 s

Status: Complete

## Outcome + scope

`prepare_command` adds `--timeout 60` after `semgrep scan` in a security gate that sets no `--timeout`, so a busy machine does not fail the gate on a rule timeout. Non-goals: `--strict`, `--timeout-threshold`, the gate's total time budget, other scanners and a project's own security script.

## Repository context

Owners: `prepare_command` in `.hooks/hard-eng.py` already adds Hard Eng's Python rules to the security gate at run time. Every Semgrep command passes through it: this repository's `hard-eng.gates.json`, the four `.agents/skills/he/templates/hard-eng.*.json` files, `.hooks/basic_mode.py` and the copies installed projects keep.
Cause (seen on 2026-11-02 on this Mac): two local `check` runs on develop 8e666dce failed `security` with exit 2 and 0 findings. Each `coverage/semgrep.json` held 3 `Timeout` errors on different rule and file pairs. Semgrep's default per-rule limit is 5 s, and `--strict` turns a timeout into a failure. The same scan alone passed with no errors; its slowest rule on a file took 0.5 s. Under load the mean rule time rose about 8 times.
Same cause: PR 149 raised the Dart declaration parser's timeout for the same kind of load (helped). Searched every `semgrep` command in `.hooks`, the templates and `hard-eng.gates.json`; all reach `prepare_command`, so this one change covers them.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the weekly reference repo watch task, which says to fix every finding properly and never switch off a check. Hard Eng's baseline repair route sends a failing baseline check to its own PR first.
Decided: 60 s, bounded, not 0 (no limit), so a hung rule still fails the gate. A gate that already sets `--timeout` keeps its value. Only a direct `semgrep scan` (or `semgrep@<version>`) call gets the flag; a project script such as `make scan` does not.

## Acceptance + steps

- [x] A direct Semgrep scan gets `--timeout 60` after `scan` → `tests/test_tool_execution.py::test_security_scan_gives_each_rule_time_to_finish_under_load[scan0-expected0]`.
- [x] A gate with its own `--timeout` keeps it → `tests/test_tool_execution.py::test_security_scan_gives_each_rule_time_to_finish_under_load[scan1-expected1]`.
- [x] A project's own security script gets no extra argument → `tests/test_tool_execution.py::test_security_scan_gives_each_rule_time_to_finish_under_load[scan2-expected2]`.

## Baseline + execution

Result: Passed
Evidence: on develop 8e666dce, `check` failed `security` twice with 3 Semgrep rule timeouts each. The new test failed before the fix: `assert ['--config', 'p/default', '.'] == ['--timeout', '60', ...]`, and after the first version `assert ['--timeout', '60'] == []` for `make scan`.
Execution: One builder, this session. Failing test, then the change in `prepare_command`, then the `make scan` case from the challenge finding.

## Risks + recovery

A rule that needs more than 60 s still fails the gate, as before. Revert both commits to restore Semgrep's 5 s default.

## ux_reference

N/A — command behavior with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_tool_execution.py`: 55 passed. Two full local `check` runs on this branch failed: every gate but `tests` passed, `security` included (163 s and 129 s under load). In both, `tests` hit the 600 s `pre_push_seconds` budget at about 93% because other sessions kept this Mac's load average near 240; the suite took 399 s on develop earlier today. A third full `check`, at a load average near 100, passed every gate: `security` 115 s, `tests` 287 s. Codex adversarial review: approve, no findings, two rounds. `challenge`: one finding (the `make scan` case), fixed.
E2E: N/A — no user journey; the gate's command line is the behavior and the tests run it through `prepare_command`.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
