# Two faults that the update of real projects showed

Status: Complete

## Outcome + scope

1. `update-pr` said "checks failing" for an update pull request whose checks all passed. GitHub had cancelled an older run of one check and started it again, and the newer run passed. The list of checks holds both runs, and the command read the cancelled one as a failure. Now a cancelled run of a workflow check gives no verdict when the same check has another run on that head commit. The other run decides: passed, failed or still running.
2. After an update, a Python project could not load its gates: "the dead-code check must run `vulture`". Its dead-code check ran `skylos`, a real dead-code scanner. Vulture cannot see a route or a model field that a framework calls, so such a project cannot pass vulture without an ignore list. Now the Python `dead-code` role accepts `uvx skylos` with `--strict` as a second tool. `uvx` installs the scanner by itself, and `--strict` makes it fail on a finding.

Non-goals: the combined state that GitHub gives, the ship command, checks with no workflow name, other roles, other tools.

## Repository context

Owners: `.hooks/update_pr.py` (`check_state` judges the checks of the update pull request; `judged_runs` sets a cancelled run aside when the same workflow check ran again). `.hooks/tool_setup.py` (`require_role_tool` reads the accepted tools of a role; `OTHER_ROLE_TOOLS` holds the second tool).
Same cause: (1) the check list of a pull request holds each run of a check, and `check_state` read each entry as current. Earlier fix: none; searched `statusCheckRollup` and `startedAt` in `.hooks/`. Other places: `review_bypass.py` reads the combined `state` that GitHub computes from the newest runs, so it has no such fault. (2) commit c504a33d made each role name one tool, to refuse a swapped command such as `true`; it left no way for a second real tool. Other places: searched `ROLE_TOOLS`; `require_role_tool` is the one reader for packages and for the shared list. The update installed a release under which the gates file could not load, because the check that an update runs on the gates file does not call the role rule; that gap is filed as an issue and is not in this change.
Single source: N/A — one function owns each judgement; no second copy exists.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-11 and 2026-11-12 the maintainer told the builder to make the decisions and to fix a fault that the update of a real project shows. Merge after green checks, then release.
Decision: only a cancelled run is set aside, because it gives no verdict on the commit; a failed run always counts. A skipped run gives no verdict too, so it does not replace a cancelled run. The rule uses no start time, because GitHub does not start runs in the order it creates them. A check with no workflow name keeps each entry, because two apps can publish a check of the same name.
Decision: the second tool is named for one role of one language, not as a free choice, so a swapped command still fails to load.

## Acceptance + steps

- [x] A check with a cancelled run and a passed run, in each order, counts as passed, the state on which the command asks for the merge → `tests/test_update_pr_checks.py::test_update_pr_takes_no_verdict_from_a_cancelled_run_of_a_check_that_ran_again`.
- [x] A cancelled run beside a queued run gives pending; a cancelled run beside a failed run, a failed run beside a passed run, two cancelled runs, a cancelled run beside a skipped run, a cancelled run of another workflow and a cancelled check with no workflow name each give failing → `tests/test_update_pr_checks.py::test_update_pr_takes_no_verdict_from_a_cancelled_run_of_a_check_that_ran_again`.
- [x] A Python dead-code check that runs `uvx skylos` with `--strict` through `bash -c` loads → `tests/test_gate_tools.py::test_wrapped_tool_commands_load`.
- [x] `true` under the dead-code role, `skylos` with no `uvx`, `uvx skylos` with no `--strict`, a tool with a near name and `uvx skylos` under the lint role still fail to load → `tests/test_gate_tools.py::test_required_check_must_name_its_tool`.

## Baseline + execution

Result: Passed
Evidence: `develop` passed required CI at the branch point; the first row of each new test failed before its change and passes after it.
Execution: one session; the failing rows first, each fix in one function, the focused tests, the independent review, the full check, PR, release.

## Risks + recovery

A person can cancel a second run of a check that passed before; the command then reads the earlier pass, which is a verdict on the same commit. Two workflow files with the same workflow name and the same job name count as one check, because the check list gives no file name. A project can swap vulture for skylos with weak settings; the role still needs a real scanner. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: the focused runs of `tests/test_update_pr_checks.py`, `tests/test_gate_tools.py`, `tests/test_update_pr.py` and `tests/test_update_pr_refusal.py` passed. The result of `python3 .hooks/hard-eng.py check --plan-stage Complete --base origin/develop` is recorded in the pull request.
E2E: N/A — no user journey; the tests give the state function check lists in the shape that real pull requests returned, and load a real gates template.
Retro: (1) Hard Eng fault that the update of real projects showed: the command called a green pull request failing → `tests/test_update_pr_checks.py::test_update_pr_takes_no_verdict_from_a_cancelled_run_of_a_check_that_ran_again`. (2) Three review corrections: a start time gives no safe order of runs, a check with no workflow name could hide a failure, and a skipped run could replace a cancelled run → the rule now uses no order, and the rows `failed beside passed`, `cancelled beside skipped` and `no workflow name` of the same test hold it. (3) Hard Eng fault that the update of a real project showed: the role rule refused a real dead-code scanner → `tests/test_gate_tools.py::test_wrapped_tool_commands_load`.
Delivery target: Merge
Delivery: Pending — the PR checks pass, `ship` passes its ready stage, the rebase merge into `develop` and the release merge into `main` are done, and the `main` run passes.
