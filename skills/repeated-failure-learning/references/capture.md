# Repeated Failure Learning Capture

## Trigger

- The same class of problem failed at least twice and the recurring failure mode plus evidence are clear
- A non-obvious process was discovered through trial and error and should be reused next time
- The user says the same issue happened again, asks to avoid it next time, or points out repeated trial without learning capture
- A direct fix is complete but the durable lesson has not been recorded yet

If failures differ or the useful process is still unclear, keep diagnosing and state what is unknown.

## Owner

- Reusable workflow, pitfall, commands, tests, E2E pattern, or domain rule: create or update `skills/<topic>/SKILL.md`, add `references/*.md` or a script for the workflow, and route it from the nearest project `AGENTS.md`
- Narrow routing-only rule with no reusable workflow: append the rule to the nearest project `AGENTS.md`
- Project-specific behavior does not belong in the global `AGENTS.md`

## Required Capture

1. Name the recurring failure mode or reusable process and cite the evidence.
2. Check existing docs, skills, and project `AGENTS.md` files to avoid duplicates and find the canonical owner.
3. Add or update the learning artifact before final.
4. Run the smallest relevant validation, including skill validation or the project contract test when available.
5. Mention the learning artifact in the final response.
