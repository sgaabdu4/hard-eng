# Setup reports workflow cache settings that cannot work on a self-hosted runner

Status: Complete

## Outcome + scope

Setup and update print a specific message, with the fix, for two workflow faults they cannot rewrite: (a) a tool directory (`MISE_DATA_DIR`, `MISE_CACHE_DIR`, `MISE_STATE_DIR`, `BUN_INSTALL_CACHE_DIR`) set from the runner temp folder without keeping the runner's own value, in a form the migration does not move (an env mapping, `${RUNNER_TEMP}`); (c) an `actions/cache` step on a Playwright browser folder, in a workflow whose jobs can run on a self-hosted runner and that never sets `PLAYWRIGHT_BROWSERS_PATH`. Non-goals: (b) below, a general "path the job never creates" rule, a failing gate.

## Repository context

Owners: `report_cache_problems` and its two message functions in the new `.hooks/ci_cache.py` (`ci_setup.py` is at the file-length limit); `configure_ci` in `.hooks/ci_setup.py` runs them after the migrations, on the migrated text.
Same cause: (a) projects whose generated or copied steps kept the unconditional form made every run on a self-hosted runner with a persistent tool directory download its tools again (about 70 s); the earlier changes rewrite the forms setup can recognise and this reports the rest. (c) On a self-hosted runner image that exports `PLAYWRIGHT_BROWSERS_PATH`, the default folder `~/.cache/ms-playwright` is never created, so the cache post step prints "Path Validation Error: Path(s) specified in the action for caching do(es) not exist, hence no cache is being saved", the cache always misses, and the job reinstalls the browser each run; two workflows of one monorepo show it in their logs. Searched the other repositories' workflows: no other cache path of this kind.
(b) Not added. The hosted-only guards found (`runner.environment == 'github-hosted'` on the tool and bun caches) sit on paths the self-hosted image already provides, so they are right. Whether a given tool is provided is a fact of the runner image; Hard Eng cannot read it, and any rule that guessed would flag correct workflows. The runner owner records the provided tools.
Why not a failing gate: the update's own gate validation (`validate_gates` in `.hooks/update.py`) loads the project's files as they are before the update, so a gate that fails on the old form would refuse the update that rewrites it.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved this stream on 2026-10-31 (edit, push, open pull requests into `develop`, no release). Decided: the browser rule fires only when a job's `runs-on` mentions `vars.` or `self-hosted` and the workflow text has no `PLAYWRIGHT_BROWSERS_PATH`; messages go to stderr like the existing "CI adaptation pending" ones.

## Acceptance + steps

- [x] An env mapping or `${RUNNER_TEMP}` tool directory is reported with the variable, file, line and the fix → `tests/test_ci_cache.py::test_a_tool_directory_the_move_cannot_rewrite_is_reported`.
- [x] A line the setup moves is not reported → `tests/test_ci_cache.py::test_a_moved_tool_directory_is_not_reported`.
- [x] A Playwright cache on a self-hostable job is reported with the fix → `tests/test_ci_cache.py::test_a_playwright_cache_on_a_self_hostable_job_is_reported`.
- [x] A hosted-only job, or a workflow that sets `PLAYWRIGHT_BROWSERS_PATH`, is not reported → `tests/test_ci_cache.py::test_a_playwright_cache_that_can_exist_is_not_reported`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` 16a49a1: `tests/test_ci_setup.py` and `tests/test_tool_environment.py` passed. The new tests failed first: three of six had no message. Run on the live workflows of the installed projects (read only, nothing changed), the rules named the two Playwright cache workflows and the one project with a leftover env mapping, and nothing else.
Execution: One builder; tests first, then the two message functions and the wrapper.

## Risks + recovery

A self-hosted runner without `PLAYWRIGHT_BROWSERS_PATH` gets a message that its cache already works; the suggested step keeps the default folder, so following it is harmless. Recovery: revert the commit.

## ux_reference

N/A — setup messages with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Complete --base origin/develop` on the branch: all 20 gates passed and 2100 tests passed. Earlier runs failed the file-length limit on `ci_setup.py` (1026 lines), so the new code moved to `ci_cache.py`.
E2E: N/A — the tests run the real setup on written workflow files; a cache post step on a self-hosted runner is not reproducible here.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
