# Failing checks are rules to follow

Status: Draft

## Outcome + scope

Agents in installed projects met a strict Hard Eng finding, called it a Hard Eng fault and asked the user whether to weaken the rule. The shared rules invited that: they told agents to report a "fault" with no line between a broken tool and a strict check. Now the shared rules say a failing check means fix the project and never offer to weaken the check; only broken Hard Eng hooks, skills or setup get reported. Non-goals: changing any check, the cache rule or the update flow.

## Repository context

Owner: `AGENTS.md` (shared rules installed into every project), capped by `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`.
Same cause: the report-a-fault line was the only rule about Hard Eng problems, and it did not say that a strict finding is not a fault.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07: "yes pls" to adding the rule to Hard Eng's shared instructions, shipping it and installing it.
Decision: the change rewrites the report-a-fault line in place, so the file stays within its size cap.

## Acceptance + steps

- [ ] The shared rules stay within the installed size cap → `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`.
- [ ] The shared rules say a failing check means fix the project and never offer to weaken it → N/A — rule wording; a text match would only mirror the line.

## Baseline + execution

Result: Passed
Evidence: develop at the branch point (0c6860d7) passed required CI; `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` passed on 2026-11-07.
Execution: one session; edit, check, PR into develop, release, install on one project.

## Risks + recovery

An agent could read "broken" too narrowly and never report a real Hard Eng crash. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey; the change is agent instruction text.
Delivery target: PR
Delivery: Pending — PR into develop.
