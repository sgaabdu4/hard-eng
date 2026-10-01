# Check every package only when the check itself changes

Status: Complete

## Outcome + scope

CI checks every package only when a change can alter how every package's checks run: an unverified edit under `.hooks/` or `.agents/skills/he/`, `hard-eng.gates.json`, or a `.github/` file that runs `hard-eng.py`. Other `.github/` files run the workflow lint and secret scan only; other `.agents/` files and the agent instruction files run the secret scan only, unless a package names them in `impact_inputs`. A full-scope run prints the file that caused it. A package outside a `depends_on` cycle may not depend on a cycle member (issue 230). Non-goals: cycles themselves stay allowed, because Fallow coverage reuse requires a mutual edge; check order, timeouts and verified-update narrowing are unchanged.

## Repository context

Owners: `.hooks/gate_config.py` `packages_for`, `changed_packages` and `affected_groups` (selection); `.hooks/dependency_graph.py` `dependency_review_guidance` (mapping review, raised by `parse_config`, which update's `validate_gates` also runs) and `secrets_only`; `.hooks/fallow_report.py` `_dependency_coverage_commands` (requires the mutual edge); `hard-eng.py impact` (CI's light path); `.agents/skills/he/references/gates.md` (Affected selection row); this repository's `hard-eng.gates.json`, whose tests read `.agents/` and `AGENTS.md`. Evidence: in a consumer, six of the last 25 runs edited non-check workflows, checked all 15 packages and hit or neared a 45-minute timeout; app changes also checked an unrelated package through a root cycle.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix and enforce this, then update every consumer that uses Hard Eng; they approved a hard error over a justification field. The cycle ban became an error for packages outside a cycle that depend on it, because a full ban breaks Fallow coverage reuse; the user was told. Consumer mapping fixes ship before this release reaches them, one PR per repository; this repository's content stays free of consumer details.

## Acceptance + steps

- [x] A non-check workflow edit selects no package and runs the workflow and secret checks → selection test asserts the shared roles; `impact` prints `docs_only=true`.
- [x] Edits to a workflow that runs `hard-eng.py`, including a deleted one, `.hooks/`, `.agents/skills/he/` or `hard-eng.gates.json` still check every package and print the triggering file → selection tests.
- [x] Other `.agents/` files, `AGENTS.md`, `CLAUDE.md` and `AGENTS.override.md` run the secret scan only, and a package that names them in `impact_inputs` still runs → selection tests.
- [x] A package depending on a member of a cycle it is not part of fails `parse_config` with the edge named; a two-package cycle alone still passes, keeping Fallow coverage reuse → mapping tests plus the existing Fallow owner test.
- [x] The issue 230 fragment fails validation; replacing the outside edge with `impact_inputs` makes an app-only change select the app and root only → regression test.
- [x] A verified Hard Eng update still narrows to the other changes → existing update tests pass.
- [x] Full check passes with `--base origin/main`.

## Baseline + execution

Result: Passed
Evidence: main at 57c14ed passed push CI run 36819601946; `hard-eng.py check --plan-stage Draft --base HEAD` on this branch with only the plan added exited 0 with all 18 checks passing.
Execution: Single session on `fix/narrow-full-scope-ci`: selection change first, then the cycle rule, gates doc and this repository's `impact_inputs`.

## Risks + recovery

A workflow that runs the checks indirectly without naming `hard-eng.py`, such as a local composite action, would no longer check every package; the PR's own CI still runs that workflow. Projects with an outside edge into a cycle fail check and update until their mapping is fixed, which is why their fixes ship first. Recovery is reverting this change.

## ux_reference

N/A — gate selection and configuration validation only; no product appearance.

## Verification

Result: Passed
Evidence: `test_only_workflows_that_run_the_checks_select_every_package` covers edited and deleted workflows with and without `hard-eng.py`, the printed reason and `impact`; `test_package_outside_a_cycle_reads_the_root_files_it_needs` covers the issue 230 fragment; the instruction, `.agents/` and `.agents/skills/he/` cases extend the existing selection test; the existing Fallow owner and verified-update tests pass. The selection tests moved unchanged into `tests/test_affected_selection.py`, because `tests/test_agent_hooks.py` passed the 1000-line limit. Full suite: 1174 passed. This repository's package now names `.agents/` and `AGENTS.md` in `impact_inputs`, because its tests read them.
E2E: Passed — in a scratch clone of a multi-package consumer with these hooks, `impact` first failed with the cycle error naming the outside edge. After replacing that edge with `impact_inputs`: a deploy-workflow edit printed `docs_only=true` and `check --base HEAD` ran only secrets-history, actionlint, zizmor and secrets-files, passing in 12 seconds; an edit to the workflow that runs `hard-eng.py` printed the file and checked every package; an app edit selected the app and root only; `AGENTS.md` and a non-`he` skill edit ran the secret scan only.

Delivery target: Merge
Delivery: Pending — PR CI, merge and merged-main CI.
