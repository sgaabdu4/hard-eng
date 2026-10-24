# Update past a rewritten release, and set the mise package in every CI job

Status: Complete

## Outcome + scope

1. A project whose recorded Hard Eng release left upstream history (after the history rewrite) can update again. The updater fetches the old release by its ID, which GitHub still serves, and checks that it is older than the new release by commit time. If the old release cannot be fetched, the update stops with a message that names the stale record in `.hooks/hard-eng-source.json`. Before, the update and the scaffold-only check stopped with a bare `git merge-base --is-ancestor` error (issue #400). Projects that could not update also kept old bugs that main had already fixed, such as the check-attr hang (issue #375).
2. Setup adds the `MISE_PACKAGE` line to every CI job that launches mise. Before, it added the line only to the first job, so a second job on another runner used an empty package name and failed (issue #399). A job with no place for the line is named in the setup output.

Non-goals: no change to which releases count as verified; no change to the generated template.

## Repository context

Owners: [.hooks/release_history.py](../../.hooks/release_history.py) (new; `fetch_sources` in [.hooks/update.py](../../.hooks/update.py) calls it), `migrate_launcher` in [.hooks/ci_setup.py](../../.hooks/ci_setup.py); tests in [tests/test_rewritten_release.py](../../tests/test_rewritten_release.py) and [tests/test_ci_launcher.py](../../tests/test_ci_launcher.py).
Evidence: issues #399 and #400, and the #375 recurrence, all come from a project still on a release from before the history rewrite. That release is not in main's history, but `git fetch origin <id>` from GitHub still returns it.
Same cause: [rewritten-release-update](../rewritten-release-update/PLAN.md) made the scaffold-only check fall back to full checks for the same missing release. The update itself still failed, so affected projects could not move to a fixed release.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid filed the issues and asked for every open issue to be fixed. Standing approval to push, open PRs, decide and merge green PRs.
Decisions: Order by commit time when ancestry is gone. latest_verified already picks only main's newest verified release, so the time check only blocks a downgrade. The new module keeps `update.py` under the 1,000-line limit. Each workflow job gets its own package line because GITHUB_ENV does not cross jobs.

## Acceptance + steps

- [x] An update from a release that left upstream history fetches it by ID and installs the new release → `tests/test_rewritten_release.py::test_update_fetches_a_release_that_left_upstream_history`.
- [x] A recorded release that cannot be fetched stops the update with a message naming the record → `tests/test_rewritten_release.py::test_an_unfetchable_recorded_release_names_the_stale_record`.
- [x] Every job that launches mise gets the package line, once → `tests/test_ci_launcher.py::test_each_job_that_launches_mise_gets_the_package_line`.
- [x] A job with no place for the line is named → `tests/test_ci_launcher.py::test_a_job_without_the_anchor_is_named`.
- [x] The template stays as it is → `tests/test_ci_launcher.py::test_template_is_unchanged`.

## Baseline + execution

Result: Passed
Evidence: Both rewritten-release tests failed on develop 35c1e98 with `CalledProcessError` from `merge-base --is-ancestor` (exit 128).
Execution: One builder.

## Risks + recovery

A clock skew between releases could make a real newer release look older; the update then stops with a clear message, never installs an older one. Revert this PR to restore the strict ancestry rule.

## ux_reference

N/A — installer and CI setup with no visual surface.

## Verification

Result: Passed
Evidence: Local `hard-eng.py check`: every gate passed except 6 Dart and Swift tests that also fail on develop in this container (no Dart or Xcode tools); the `hard-eng` CI check is their proof.
E2E: N/A — the affected project's next installer run is the full proof.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` green.
