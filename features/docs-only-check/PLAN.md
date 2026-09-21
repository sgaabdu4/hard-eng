# Run only the secret scan for docs-only changes

Status: Complete

## Outcome + scope

When every changed path is a plan or top-level Markdown file other than `AGENTS.md`, `check --base` selects only the shared secret-scan gates, prints one line saying so, and provisions only their tools (issue 131). The `hard-eng` job still runs and concludes, so a required check keeps reporting. No new file other than this plan, and no workflow or configuration change.

## Repository context

Owner: `.hooks/gate_config.py` `changed_packages` and `affected_groups`; the documentation rule sits beside `is_plan_path` in `.hooks/plans.py` and the secret-scan subset beside the other impact helpers in `.hooks/dependency_graph.py`. Plans were already excluded from package selection, but a root `README.md` either matched the root package or, in a multi-package repository, matched no package and forced every check. `provision_tools` installs only what the selected gates' commands name, so narrowing the groups also narrows tool installation. `.hooks/`, `.agents/`, `.github/`, `hard-eng.gates.json` and `AGENTS.md` still mean unknown impact.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open Hard Eng issues and open a PR to main; 131 was the only one open. The secret scan stays because `gitleaks dir .` reads Markdown and `validate_required_checks` requires it; dropping it would weaken a required check. Only top-level Markdown counts as documentation, because Markdown inside a package can be a build or test input. The issue's configurable path list is left out: the fixed rule meets the reported case, and the list can be added when a project needs to widen or narrow it. Plan-only diffs now run only the secret scan instead of every shared gate. The user then asked to raise the handwritten-file limit from 700 to 1000 lines in the same PR; `validate_file_sizes` in `.hooks/gate_config.py`, its boundary test and the README change together, and it applies to installed projects too.

## Acceptance + steps

- [x] A diff of only plans or top-level Markdown, in a root-package or multi-package layout, selects only the secret-scan gates → `test_docs_only_change_runs_only_the_secret_scan`; all six cases fail on main.
- [x] `AGENTS.md`, skill Markdown and package-level Markdown keep package checks, and a root `README.md` no longer selects every package → new cases in `test_changed_package_includes_transitive_dependents_and_shared`.
- [x] The file-size gate accepts 1000 lines and rejects 1001 → `test_file_size_boundary_and_narrow_exceptions` updated.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at b50c3c8, the merged revision of PR 130, whose hard-eng CI passed.
Execution: Single session on `feature/hard-eng-issues-5060cb`.

## Risks + recovery

A top-level Markdown file that a package's tests read would no longer run those tests when it alone changes; `DESIGN.md` and `PRODUCT.md` are still validated in-process on every check. Recovery is reverting this branch.

## ux_reference

N/A — command-line gate selection only; no product appearance.

## Verification

Result: Passed
E2E: Passed — in a scratch worktree of this branch with only `README.md` and this plan edited, `hard-eng.py check --base HEAD` printed the secret-scan-only line, ran only `secrets-files`, and exited 0 in 6 seconds; the same repository runs all 17 checks, about four minutes, for a code change.
Evidence: `tests/test_agent_hooks.py` selection tests pass. The full check result is recorded in the delivery line below.

Delivery target: PR
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks passed, 783 tests and 4 performance checks. A first run failed the then 700-line limit on `gate_config.py` and the test file; the helpers moved to their existing owners before the passing run. After the limit rose to 1000, the full check passed again: 17 checks, 783 tests. PR CI remains unverified.
