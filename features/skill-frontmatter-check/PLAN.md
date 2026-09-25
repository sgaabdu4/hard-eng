# Check that every distributed skill's frontmatter loads, and let hosts pick Writing Great Skills

Status: Complete

## Outcome + scope

A pytest check fails when a distributed skill's frontmatter would not load in a host: no `---` on line 1 or no closing marker, YAML that does not parse, a `name` that differs from its directory, or a `description` that is missing, empty or over 1024 characters. Symlinked submodule skills are covered. Writing Great Skills is no longer explicit-only: Claude Code and Codex may select it from its description for skill authoring or review, and explicit `/` and `$` invocation still work. Non-goals: a schema library, rules for unknown or optional fields, runtime hooks, and invocation changes to other skills. Source: a review of public agent-skill tooling changes; its sandboxing and ADR-expiry proposals were reviewed and held.

## Repository context

Owner: `tests/test_skill_links.py` already walks `.agents/skills`, follows submodule symlinks and uses tmp_path negative fixtures; PyYAML and its type stubs are already project dependencies. Host rules: Claude Code reads frontmatter only when `---` is the first line, and malformed YAML loads the skill with no description, so it stops triggering without an error ([skills docs](https://code.claude.com/docs/en/skills#skill-not-triggering)). Codex requires `name` and `description` ([Codex skills](https://developers.openai.com/codex/skills)). The [Agent Skills specification](https://agentskills.io/specification#frontmatter) requires a non-empty `description` of at most 1024 characters and a [`name` matching the parent directory](https://agentskills.io/specification#name-field). Invocation: Writing Great Skills was made explicit-only on 2026-09-09 through `disable-model-invocation: true` in its frontmatter (Claude Code) and `policy.allow_implicit_invocation: false` in `agents/openai.yaml` (Codex). HE Learn and `decisions.md` reach it by file link, which neither flag affects; no test, hook or setup code reads either flag. Its `references/package.md` keeps an existing invocation policy unless the user authorizes a change.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: After that review, the user asked to rebase on origin/main, implement the frontmatter check, open a PR and merge it, then chose to include the Writing Great Skills invocation change in the same PR.

## Acceptance + steps

- [x] Every current distributed skill passes → `test_distributed_skill_frontmatter_loads`.
- [x] A late opener, a missing closer, an unquoted colon, a wrong name, a missing description and a 1025-character description each fail, while a quoted colon passes → `test_unreadable_frontmatter_fails_and_valid_equivalent_passes`.
- [x] Breaking a real local skill and a real submodule skill fails the repository test.
- [x] Writing Great Skills has neither explicit-only flag; its interface metadata is unchanged.
- [x] A skill-authoring prompt selects Writing Great Skills in Claude Code and Codex after the change, and did not before.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `f0c5825` → exit 0; 17/17 gates PASS, 815 tests passed.
Execution: One builder; one test change, then the invocation change.

## Risks + recovery

Host rules may change; the check covers only rules the linked host docs state. Recovery: update the check to the host's current rule. Writing Great Skills may now be selected for loosely related prompts in installed projects, and its description is listed in every session. Recovery: narrow its description, or restore both flags.

## ux_reference

N/A — test and skill-metadata change with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_skill_links.py` → 4 passed; all 14 distributed skills pass. The first full run failed the types gate on an undeclared `YAMLError.problem` and an unannotated empty dict, both fixed. `python3 .hooks/hard-eng.py check --plan-stage Ready` → exit 0; 17/17 gates PASS, 817 tests passed. An unquoted colon in `he`'s description and a changed `name` in the Appwrite submodule skill each failed the repository test, then were reverted. After the invocation change, `check --plan-stage Ready` → exit 0; 17/17 gates PASS, 817 tests passed.
E2E: Passed — disposable fixtures holding only this skill, before and after the flag removal, one run each, prompt "Draft a SKILL.md for a skill that formats changelogs". Claude Code 2.1.282 on claude-haiku-4-5, project settings only, no MCP: before, the skill was absent from its self-invocable list and the prompt made no tool calls; after, it listed the skill with its description and the prompt called `Skill` with `writing-great-skills`. Codex CLI 0.154.0 on gpt-6-astra, read-only sandbox: before, it read its built-in `skill-creator`; after, it read `writing-great-skills/SKILL.md`. Selection varies by model and run; these are single-run observations.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
