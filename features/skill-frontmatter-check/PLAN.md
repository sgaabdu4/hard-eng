# Check that every distributed skill's frontmatter loads

Status: Complete

## Outcome + scope

A pytest check fails when a distributed skill's frontmatter would not load in a host: no `---` on line 1 or no closing marker, YAML that does not parse, a `name` that differs from its directory, or a `description` that is missing, empty or over 1024 characters. Symlinked submodule skills are covered. Non-goals: a schema library, rules for unknown or optional fields, and runtime hooks. Source: a review of public agent-skill tooling changes; its sandboxing and ADR-expiry proposals were reviewed and held.

## Repository context

Owner: `tests/test_skill_links.py` already walks `.agents/skills`, follows submodule symlinks and uses tmp_path negative fixtures; PyYAML and its type stubs are already project dependencies. Host rules: Claude Code reads frontmatter only when `---` is the first line, and malformed YAML loads the skill with no description, so it stops triggering without an error ([skills docs](https://code.claude.com/docs/en/skills#skill-not-triggering)). Codex requires `name` and `description` ([Codex skills](https://developers.openai.com/codex/skills)). The [Agent Skills specification](https://agentskills.io/specification#frontmatter) requires a non-empty `description` of at most 1024 characters and a [`name` matching the parent directory](https://agentskills.io/specification#name-field).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: After that review, the user asked to rebase on origin/main, implement the frontmatter check, open a PR and merge it.

## Acceptance + steps

- [x] Every current distributed skill passes → `test_distributed_skill_frontmatter_loads`.
- [x] A late opener, a missing closer, an unquoted colon, a wrong name, a missing description and a 1025-character description each fail, while a quoted colon passes → `test_unreadable_frontmatter_fails_and_valid_equivalent_passes`.
- [x] Breaking a real local skill and a real submodule skill fails the repository test.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `f0c5825` → exit 0; 17/17 gates PASS, 815 tests passed.
Execution: One builder; one test change.

## Risks + recovery

Host rules may change; the check covers only rules the linked host docs state. Recovery: update the check to the host's current rule.

## ux_reference

N/A — test-only change with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_skill_links.py` → 4 passed; all 14 distributed skills pass. The first full run failed the types gate on an undeclared `YAMLError.problem` and an unannotated empty dict, both fixed. `python3 .hooks/hard-eng.py check --plan-stage Ready` → exit 0; 17/17 gates PASS, 817 tests passed. An unquoted colon in `he`'s description and a changed `name` in the Appwrite submodule skill each failed the repository test, then were reverted.
E2E: N/A — test-only change; no runtime journey changes.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
