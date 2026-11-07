# Staging from develop, production from main

Status: Draft

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
Uncertainty: a Cloudflare Workers PR preview needs `wrangler versions upload --preview-alias pr-<N>` and a preview URL the journeys can reach. Cheapest check: one preview upload from a real project's PR workflow, reached by its journeys. If it fails, PRs run checks only and the journeys first run on staging after merge; ask before switching.

## Acceptance + steps

- [ ] A real project's PR gets a preview on the staging backend and its journeys pass there, without changing the shared staging site → that project's deploy run on that PR (first slice; proves the main uncertainty).
- [ ] The hosting rule keeps today's flow without the coordinator, and for a coordinator project names PR → preview + journeys, `develop` → staging + journeys, `main` → production + read-only check → N/A — rule wording; checked against a real project in the switch step.
- [ ] Ship and update-pr target `develop` when `shipping.base` is `develop`, and the release PR from `develop` to `main` uses a merge commit → tests to name in build.
- [ ] The coordinator releases once every card on staging is approved, and reverts or fixes a failed card first → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [ ] Testing = live on staging with images; Done = release live on production → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [ ] A real project moves over: `develop` branch and default branch, deploy workflow, `shipping.base`, release-source check; staging shows `develop`, production shows `main` → that project's deploy runs on both pushes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` passed on 2026-11-07 at develop 0a7582e8, which passed required CI.
Execution: first slice on a real project: prove the PR preview in its deploy workflow. Then Hard Eng rules and checks (one PR into develop, then release). Then that project's switch in its own PR, with its staging journeys as proof. One builder, sequential; a fresh reviewer before each merge.

## Risks + recovery

Two merges per change and a release step add delay. A missed revert of a failed card blocks the release. Recovery: revert the Hard Eng PR; on a project, set `shipping.base` back to `main` and restore its deploy workflow.

## ux_reference

N/A — no app screens change; card text keeps everyday words ("test site", "real site").

## Verification

Result: Pending
Evidence: Pending.
E2E: Delivery — the project's staging journeys on a `develop` push, and its production check on a `main` push.
Delivery target: Deploy
Delivery: Pending — Hard Eng PR into develop, release, then the project's switch.
