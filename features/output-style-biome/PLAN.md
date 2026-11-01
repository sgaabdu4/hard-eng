# Keep project Biome formatting off the shipped output style

Status: Complete

## Outcome + scope

Setup ships `.claude/output-styles/biome.json`, a nested Biome config that turns the formatter off for the Markdown files in that folder. A project that formats Markdown with Biome no longer rewrites the shipped output style, so the next update can replace it. Non-goals: project-owned Markdown, the project's own Biome settings, other formatters.

## Repository context

Owners: `.hooks/update.py` `scaffold_files` lists the files setup copies; `setup.py` `scaffold_changes` refuses to replace a shipped file that differs from both the new and the previous release. `.agents/biome.json` already turns the formatter off for shipped `SKILL.md` files for the same reason. Test: `tests/test_adoption.py::test_setup_json_stays_in_the_project_biome_layout`.
Cause: Biome 2.6.4 (latest) formats Markdown without front matter support. It adds a blank line after the opening `---` of `.claude/output-styles/plain-ste.md`. A project that ran its Biome formatter then held a changed copy, and setup refused the update with "already differs; ask before replacing it".
Same cause: `.agents/biome.json` turned the formatter off for `SKILL.md` front matter; the output style was not covered because it lives under `.claude/`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The owner asked on 2026-10-31 for Hard Eng to enforce the CI speed work through updates, with full authority to merge; this blocks one project's update.

## Acceptance + steps

- [x] Setup ships the nested config, and it turns the formatter off for the folder's Markdown → `tests/test_adoption.py::test_setup_json_stays_in_the_project_biome_layout` passes (both cases); it failed with `KeyError: '.claude/output-styles/biome.json'` before the `update.py` change.

## Baseline + execution

Result: Passed
Evidence: develop ccf2c7f. In a project with Biome 2.6.4 and Markdown formatting on, `biome format .claude/output-styles/plain-ste.md` on the shipped file reports one change (a blank line after `---`); with the shipped style restored and this nested config added, `biome ci .` passes on that project (139 files, no errors).
Execution: One builder, this session.

## Risks + recovery

A project that wants its formatter on the output style can delete the nested config; setup restores it on the next update. Recovery: revert this change.

## ux_reference

N/A — formatter config only; no visible UI.

## Verification

Result: Passed
Evidence: focused `tests/test_adoption.py`, `tests/test_hook_setup.py`, `tests/test_setup.py`, `tests/test_updates.py` pass.
E2E: N/A — the Canary new-project jobs run setup on real runners.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
