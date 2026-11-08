# Staging from develop, production from main

Status: Complete

## Outcome + scope

A hosted project with staging and production now deploys staging from each same-repository PR and production from each push to the base branch. Staging shows whichever PR deployed last, and a change reaches real users before a tester has tried it. Now a project with both environments and the Trello coordinator (`trello.json`) works like this: feature PRs target `develop`; a push to `develop` deploys staging and runs the E2E journeys there; testers test staging; a release PR from `develop` to `main` (merge commit) deploys production. The Trello coordinator moves a card to Testing once it is live on staging, and to Done once its release is live on production. Projects without the coordinator, or with one environment, keep today's flow (PR → staging, base push → production; or one base branch), because nobody tests their staging before release. Non-goals: hosts other than the ones a project already uses.

## Repository context

Owners:
- `.agents/skills/he/references/integrations.md` (Hosting: which push deploys where).
- `.agents/skills/trello-coordinator/SKILL.md` + `references/run.md` (Testing, Release, Done).
- `.agents/skills/he-ship/SKILL.md` + `references/checks.md` (base branch, release PR, delivery proof).
- `.github/workflows/release-source.yml` (Hard Eng's own "main takes only develop" check; the pattern to reuse).
- `.hooks/shipping.py` (`shipping.base`, already read by ship and update-pr through `update_base`).
Same cause: the hosting rule tied staging to PR events, so nothing gave staging one stable source or gave testers a step before production.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07: "yes pls" to planning staging from `develop` and production from `main`; on 2026-11-07 limited it to projects that use the coordinator and have staging.
Decision: `shipping.base` = `develop` for a project with both environments and `trello.json`; update PRs follow it, so Hard Eng updates reach production through the next release.
Decision: `main` takes only the `develop` release PR, merged with a merge commit; a project copy of the release-source check enforces it.
Decision: a card that fails testing is fixed or reverted on `develop` before the next release, so it never holds approved cards back.
Decision (Abid, 2026-11-07): each same-repository PR deploys its own preview on the staging backend and runs the E2E journeys there before merge; the shared staging site changes only on a `develop` push.
Decision (Abid, 2026-11-07): the coordinator starts the release as soon as every card on staging is approved by its tester; no owner step.
Decision (Abid, 2026-11-07): "yes pl" to a UI card's Testing proof using the mockup rule: before and after, red boxes around each change; written rule, since a script cannot see the boxes.
Uncertainty: a Cloudflare Workers PR preview needs `wrangler versions upload --preview-alias pr-<N>` and a preview URL the journeys can reach. Cheapest check: one preview upload from a real project's PR workflow, reached by its journeys. If it fails, PRs run checks only and the journeys first run on staging after merge; ask before switching.

## Acceptance + steps

- [x] A real project's PR gets a preview on the staging backend and its journeys pass there, without changing the shared staging site → N/A — proven outside this repository: that project's deploy run on its preview PR passed 12 journeys on the preview address, and the staging site served the same build before and after.
- [x] The hosting rule keeps today's flow without the coordinator, and for a coordinator project names `shipping.base` = `develop`, PR → own preview + journeys, `develop` → staging, `main` → production, and `main` taking only the `develop` release PR → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] Ship refuses a PR whose base is not `shipping.base`, so feature PRs go to `develop` and the release PR is merged by hand; no code change → `tests/test_shipping.py::test_ready_rejects_pr_identity_and_mergeability`.
- [x] The coordinator releases once every testing card is approved, merges the release PR with `gh pr merge --merge`, and fixes or reverts a failed card first → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] Done = release live on production → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] A UI card's Testing proof shows before and after of the same screen, state and width, with red boxes around each change → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] N/A — not in this plan: the real project's switch (`develop` branch, default branch, deploy workflow, `shipping.base`, release-source check). It ships in that project's own PR with its own plan, after this release.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` passed on 2026-11-07 at develop 0a7582e8; the branch was rebased on develop 921d8ce8 on 2026-11-08, which passed required CI.
Execution: first slice on a real project (done): the PR preview in its deploy workflow. Then Hard Eng rules (this plan: one PR into develop, then release). Then that project's switch in its own PR. One builder, sequential; a fresh reviewer before each merge.

## Risks + recovery

Two merges per change and a release step add delay. A missed revert of a failed card blocks the release. Recovery: revert the Hard Eng PR; on a project, set `shipping.base` back to `main` and restore its deploy workflow.

## ux_reference

N/A — no app screens change; card text keeps everyday words ("test site", "real site").

## Verification

Result: Passed
Evidence: On 2026-11-08 `uv run pytest -q tests/test_trello_coordinator.py`: 37 passed; the new assertions failed before the rule text changed.
E2E: N/A — rule text only; the real project's switch proves it with its staging journeys on a `develop` push and its production check on a `main` push.
Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
