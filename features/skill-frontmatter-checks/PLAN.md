# Skill frontmatter checks

Status: Complete

## Outcome + scope

The skill frontmatter test now fails two silent faults. An unquoted description with ` #` loses its end, because YAML reads the rest as a comment. A skill whose Claude `disable-model-invocation` and Codex `allow_implicit_invocation` disagree triggers on one host and not the other. Non-goals: other frontmatter fields.

## Repository context

Owner: `frontmatter_failures` in `tests/test_skill_links.py`, which already fails unreadable metadata. `writing-great-skills/references/package.md` names both client policy fields; no check compared them.
Same cause: N/A — two separate metadata faults with one owner.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop` and to back skill rules with deterministic checks, with every decision made by the agent.

## Acceptance + steps

- [x] An unquoted ` #` and disagreeing manual-only flags fail; a quoted ` #` passes → `tests/test_skill_links.py::test_unreadable_frontmatter_fails_and_valid_equivalent_passes`.
- [x] Every distributed skill passes → `tests/test_skill_links.py::test_distributed_skill_frontmatter_loads`.

## Baseline + execution

Result: Passed
Evidence: `develop` ec270c5: the new rows failed there; all distributed skills already agree.
Execution: One builder; failing rows, then the checks.

## Risks + recovery

None; a future skill that fails gets a message that names the fix.

## ux_reference

N/A — test change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1818 passed, the same 8 environment failures as `develop`; `tests/test_skill_links.py` 6 passed. Ruff, Pyrefly (0 errors) and jscpd (0 clones) pass.
E2E: N/A — the test reads the real distributed skills.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
