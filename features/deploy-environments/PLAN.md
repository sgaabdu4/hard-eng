# Plan staging and production for hosted apps

Status: Ready

## Outcome + scope

A plan for a new hosted app sets up staging and production from the first deploy, on Cloudflare Workers unless the user picks another host. A project with a configured production check cannot close work at merge. Non-goals: changes in any consumer project, the Appwrite skill (its own repository), a deploy workflow template, moving existing Pages projects.

## Repository context

Owners: `.agents/skills/he-plan/SKILL.md` (Setup line), `.agents/skills/he/references/integrations.md` (services and hosting), `.agents/skills/he-ship/references/checks.md` (delivery checks), `.hooks/plans.py::_validate_shipping`, `.hooks/shipping.py::verify`, `tests/agent_checks.py` (agent cases).
Same cause: two new projects copied one project's staging and production workflow by hand, because Hard Eng never asks where an app runs. Both set no delivery check, so their plans closed at merge before the live site changed. No earlier fix of this cause. Cloudflare's Pages docs now say "Start new projects with Workers"; Pages is not deprecated.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-05: Workers is the default host unless the user picks another; "create the pr and run autonomously", after a Codex adversarial review loop with gpt-6.1-sol that fixes genuine substantial findings only.

## Acceptance + steps

- [ ] A Ready or Complete plan with `Delivery target: Merge` fails when the project configures delivery checks; `PR` and `Deploy` still pass → `tests/test_shipping_plan.py::test_configured_delivery_checks_need_deploy_target`.
- [ ] Shipping refuses a Merge target when delivery checks are configured, before any GitHub call → `tests/test_shipping.py::test_configured_delivery_checks_refuse_merge_target`.
- [ ] A small change without a plan in such a project ships with the Deploy target, so its delivery checks run → `tests/test_shipping_plan.py::test_ready_without_a_plan_only_for_a_small_change`.
- [ ] Integration setup states the hosting defaults: staging and production, Workers by default, deploys from Actions only, staging journeys, a read-only production check that proves the revision, additive schema pushes, the origin move risk → `tests/test_skill_links.py::test_distributed_skill_links_resolve` (links) and the agent case below.
- [ ] A planning-only request to put the fixture app online yields a plan with staging, production, Cloudflare Workers and `Delivery target: Deploy` → `tests/agent_checks.py::judge_hosted_plan` (case `hosted-greenfield`), run on Claude and Codex.

## Baseline + execution

Result: Passed
Evidence: Branch point develop 4710c249 passed `Hard Eng`, `Canary`, `PR text` and `Release source` in CI. `python3 .hooks/hard-eng.py check --plan-stage Draft` with only this plan changed → exit 0 (secret scan PASS).
Execution: One builder, this session; Codex adversarial review loop before the PR.

## Risks + recovery

A project that configured delivery checks but ships some PRs as Merge now fails its plan check. Recovery: set `Delivery target: Deploy`, or remove the delivery check if the project does not deploy on merge.

## ux_reference

N/A — skill text and plan checks only; no visible UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — the tests run the real plan and shipping checks against fixture repositories; the agent case runs real agent sessions.
Delivery target: Merge
Delivery: Pending — the PR merges into develop after its checks pass.
