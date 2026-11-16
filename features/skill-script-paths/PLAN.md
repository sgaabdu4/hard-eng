# Call skill scripts by path from any folder

Status: Ready

## Outcome + scope

The walkthrough video skill names each script by its path from the skill folder, and a test refuses a script call that only works inside the skill folder. Non-goals: the Setup block, the scripts themselves, the skills that come from submodules.

## Sources + coverage

Sources: N/A — the request is the weekly reference repository watch; its only source is the idea "a bundled script the shell executes must be anchored" from one reference repository, read in the diff.

## Repository context

Owners: `.agents/skills/product-walkthrough-video/README.md` (six `bun scripts/<name>.mjs` calls) and `SKILL.md` (the sentence "commands run from this skill's directory"); `tests/test_skill_links.py` owns the checks on shipped skill text.
Same cause: N/A — no earlier fix of this cause. Searched every Markdown file under `.agents/skills`, linked skills included, for `bun|node|python3|bash|sh` followed by `scripts/` or `./scripts/`: only the six README lines. `marketing-video/SKILL.md` already uses `bun <skill>/scripts/<name>.mjs`.
Single source: N/A — the call form `bun <skill>/scripts/<name>.mjs` has one owner in each skill; no shared constant, type or config changes.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the scheduled reference repository watch asks for each adapt item as its own small PR into develop.

## Acceptance + steps

- [x] A script call relative to the skill folder in shipped skill text fails, and the path forms pass → `tests/test_skill_links.py::test_a_script_call_relative_to_the_skill_folder_fails` passes.
- [x] No shipped skill holds such a call → `tests/test_skill_links.py::test_distributed_skills_call_scripts_by_path_from_any_folder` failed on the six README lines before the edit and passes after it.
- [x] The scripts run by path from another folder → N/A — no test starts Bun; `scripts/scaffold.mjs` and `scripts/review-video.mjs`, started by absolute path from another folder, reached their own argument checks.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16, develop b9824ebc: the `Hard Eng` and `Canary` workflows passed on the push. One real Codex session ran `cd sub` and then `pwd` as two shell calls; the second call started in the first folder again, so a folder change does not carry over.
Execution: One builder, this session.

## Risks + recovery

N/A — text of one optional skill and one test; a revert restores both.

## ux_reference

N/A — skill text and a test; no visible UI.

## Verification

Result: Pending
Evidence: Pending — the Complete check.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: Pending
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
