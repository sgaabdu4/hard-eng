# Route Research and Security Review from the Hard Eng workflow

Status: Draft

## Outcome + scope

Agents load Research for stack, vendor or version choices and "look online" asks, and load Security Review for changes to sign-in, permissions, API keys, payments, uploads or personal data. Non-goals: the SessionStart text, the session hook import crash (not reproduced), new skills.

## Repository context

Owners: `.agents/skills/he-plan/SKILL.md` (Context line), `.agents/skills/he-build/SKILL.md` (Behavior line), the `research` and `security-review` descriptions. Evals: `tests/agent_checks.py`, fixtures in `tests/agent_fixtures.py`.
Same cause: a skill-use audit of Hard Eng projects found zero Research loads, although users asked for research and "look online" many times. Security Review ran only when a subagent brief named it; it did not run on a sign-in and per-team API key change in a personal-data app. he-plan loaded Research "only when needed", no workflow skill linked Security Review, and both descriptions lacked the words users type. No earlier fix of this cause.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-28: "Yes. Fix the routing so security-review and research get used, in PR 431." PR 431 had merged, so this ships as its own PR to develop. No commit or push without approval (AGENTS.override.md); the request covers this PR.
Decision: routing lives in he-plan, he-build and the two descriptions; the SessionStart line stays as it is (least always-loaded tokens). The two descriptions keep their total word count (72 words before and after).

## Acceptance + steps

- [x] A "look online" prompt ranks Research first, and an API key and personal-data prompt ranks Security Review first → `tests/test_skill_routing.py::test_every_request_picks_its_own_skill`.
- [x] No two descriptions grow too alike → `tests/test_skill_routing.py::test_no_two_descriptions_are_too_alike`.
- [x] he-plan stays under the Codex skill size limit → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.
- [ ] A model asked to look online loads Research → `tests/agent_checks.py::routes-to-research`.
- [ ] A model asked to check a commit that stores API keys loads Security Review → `tests/agent_checks.py::routes-to-security`.
- [x] Each client's skill loads are read from its own records → `tests/test_agent_checks.py::test_skill_routing_is_judged_from_the_skills_each_client_loaded`.

## Baseline + execution

Result: Passed
Evidence: Branch point develop 7d4d05d1; its PR #431 passed all 16 CI checks.
Execution: One builder, this session; Codex adversarial review before the evals.

## Risks + recovery

N/A — skill text and tests only; a wrong route costs one extra skill load.

## ux_reference

N/A — skill text only; no visible UI.

## Verification

Result: Pending
Evidence: The two new routing prompts fail on the old descriptions and pass now.
E2E: N/A — the model evals load the installed skills in a fixture project.
Delivery target: Merge
Delivery: Pending — the PR merges into develop after its checks pass.
