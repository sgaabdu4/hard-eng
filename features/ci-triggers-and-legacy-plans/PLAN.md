# CI triggers, new-branch bases, workflow_call and legacy plans

Status: Complete

## Outcome + scope

Run the Hard Eng CI template once per change, migrate installed copies of the generated triggers on update, compare a new branch against its merge base with the default branch, let project workflows call and depend on Hard Eng, and stop new plan rules from failing unchanged Complete plans. No new runner, receipt store or plan-dating scheme.

## Repository context

Owners: `.github/workflows/hard-eng.yml` (template), `.hooks/ci_setup.py` `configure_ci` (project copy), `.hooks/gate_config.py` `changed_files` (comparison base), `.hooks/plans.py` `validate_plans` (plan scope), `.agents/skills/he/references/gates.md` (documented zero-base behavior). The updater already preserves an existing project workflow apart from pin/tool migrations, so the reported overwrite did not reproduce; the observed old-plan CI failures came from the zero-base push run diffing against the empty tree.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous; the user authorized all five changes including `workflow_call` and delegated the remaining decisions.

## Acceptance + steps

- [x] Template triggers are `pull_request` plus `push` to the default branch only; `configure_ci` writes the project's shipping base → `test_workflow_runs_once_per_change` asserts the template and generated copy.
- [x] `changed_files` with an all-zero base returns only files changed since the merge base with the shipping base branch; the default branch itself, a missing policy or a missing remote ref keep the empty-tree fallback → `test_new_branch_zero_base_compares_with_default_branch`.
- [x] Template exposes `workflow_call` with a `base_sha` input that feeds `BASE_SHA` → `test_workflow_call_base_input_feeds_check`; actionlint and zizmor pass on the workflow.
- [x] A Complete plan outside the diff without `E2E:` passes `validate_plans`; the same plan inside the diff still fails → `test_unchanged_complete_plan_predates_e2e_rule`.
- [x] An installed workflow that still carries the generated `push`/`pull_request` block migrates to the new triggers, `workflow_call` and `BASE_SHA` for the project's shipping base; customized triggers or a missing policy leave it untouched → `test_generated_triggers_migrate_with_customizations` and the existing updater pin-migration test extended with old triggers.
- [x] Each new test fails on the unmodified code for the stated reason and passes after the change.

## Baseline + execution

Result: Passed
Evidence: Starting revision ea6ea7c in a clean detached worktree: `uv run --no-project --with pyyaml python .hooks/hard-eng.py check` exit 0, 739 tests passed, all 17 native checks passed. An earlier in-tree Draft run was contaminated by concurrent edits and discarded.
Execution: Single implementer; tests first, then owners in the order above.

## Risks + recovery

Push-only-to-main removes CI for branches without a PR; PR delivery is the shipping default. A wrong merge base would hide changed packages; the fallback to the empty tree remains the widest scope. Tolerating a missing `E2E:` only on unchanged Complete plans keeps every other rule active; recovery is reverting the single owner change. Callers of the reusable workflow see the check as `<caller job> / hard-eng`, which their `shipping.checks` must name.

## ux_reference

N/A — CI workflow and hook changes have no visual interface.

## Verification

Result: Passed
Evidence: Red on unmodified code: `test_workflow_runs_once_per_change` (`branches-ignore` instead of `branches: [main]`), `test_workflow_call_base_input_feeds_check` (`KeyError: 'workflow_call'`), `test_new_branch_zero_base_compares_with_default_branch` (`shared.py` and `hard-eng.gates.json` counted as changed), `test_unchanged_complete_plan_predates_e2e_rule` (`plan needs one filled 'E2E:' field`). Green after the change: affected modules test_ci_setup, test_agent_hooks, test_plans, test_planning_handoffs, test_ship_actions, test_shipping, test_updates and test_setup, 340 passed. `gate_config.py` stays at the 700-line limit after compacting the helper. An empty `--base` (a `workflow_dispatch` or `schedule` caller without `base_sha`) already runs full scope; the existing native CLI test now asserts it. Red for the migration with `ci_setup.py` stashed at ea6ea7c: `test_generated_triggers_migrate_with_customizations` raised `KeyError` because no workflow change was planned, and the updater test's migrated workflow still carried `branches-ignore`. The updater fixture needed a shipping policy and a branch named after it, which is the real installed layout. Review found the trigger slice ended after the blank line, so a real installed copy gained an extra blank line; the slice now ends at the single newline, the setup test asserts the installed `pull_request:` blank-line shape, and both migration tests compare the migrated copy with the template. Git history shows only one generated trigger block and one `BASE_SHA` line ever shipped, so the exact-match migration covers every installed copy. The first PR run of `hard-eng` failed only `test_unchanged_complete_plan_predates_e2e_rule` with `Author identity unknown`: the runner has no git identity, while the local machine derives one from the OS account. The commit now carries the inline fixture identity used elsewhere in the same file; the failure reproduces locally with a blank global config plus `user.useConfigOnly`, and the fixed test passes under the same conditions. Full `hard-eng.py check` on the task tree before the identity fix passed: exit 0, 744 tests including the migration tests, and all native checks including actionlint and zizmor on the new workflow triggers. On the final tree every native check passed except tests, whose run hit the check's 600-second timeout under external machine load (load average near 190); the fixed test passes in isolation, and the PR's `hard-eng` run is the full-tree proof.
E2E: N/A — CI workflow wiring is proven by actionlint/zizmor and YAML assertions; GitHub-hosted runs are remote delivery proof outside local tests.

Delivery target: PR
Delivery: Pending — PR with green required `hard-eng` check.
