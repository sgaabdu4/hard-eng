# Shorten and narrow Writing Great Skills' description

Status: Complete

## Outcome + scope

Writing Great Skills' description names only its trigger: writing, revising or reviewing an agent skill (SKILL.md package). It drops the list of sub-topics, going from 114 to 57 characters, which lowers the cost of listing it in every session now that hosts may select it. Skill-authoring prompts still select it; nearby non-skill prompts still do not. Non-goals: changes to its body, references, `agents/openai.yaml` or invocation policy.

## Repository context

Owner: the `description` field in `.agents/skills/writing-great-skills/SKILL.md`. PR #164 made the skill model-invocable in Claude Code and Codex, so its description is listed in every session. Its `references/package.md` asks for a concise description with the purpose and distinct trigger first, and representative matching and nearby non-matching prompts for a trigger change. `tests/test_skill_links.py` checks the description is 1-1024 characters. The `agents/openai.yaml` `short_description` ("Write terse, routed agent skills") stays consistent.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to narrow the description and make it shorter.

## Acceptance + steps

- [x] The description is shorter and names only the skill-authoring trigger.
- [x] Two skill-authoring prompts select the skill and two nearby non-skill prompts do not, in Claude Code and Codex, matching the old description.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `0e06feb` → exit 0; 17/17 gates PASS, 817 tests passed.
Execution: One builder; one metadata change.

## Risks + recovery

A shorter description may miss prompts that name a sub-topic, such as consolidating skills, without saying "skill"; explicit invocation still works. Recovery: add the missed trigger term.

## ux_reference

N/A — skill-metadata change with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Ready` → exit 0; 17/17 gates PASS, 817 tests passed, including the frontmatter check on the new description.
E2E: Passed — disposable fixtures holding only this skill, old and new description, one run each per prompt. Claude Code 2.1.282 on claude-haiku-4-5 (project settings only, no MCP) and Codex CLI 0.154.0 on gpt-6-astra (read-only sandbox). "Draft a SKILL.md for a skill that formats changelogs" and "Create an agent skill that formats changelogs" selected the skill on both hosts with both descriptions; "Draft a README.md for a CLI that formats changelogs" and "List five skills a senior backend engineer needs" selected it on neither. All 16 runs completed. Selection varies by model and run; these are single-run observations.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
