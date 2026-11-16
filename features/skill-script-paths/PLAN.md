# Call skill scripts by path from any folder

Status: Complete

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
- [x] The scripts run by path from another folder → N/A — no test starts Bun; each of the four scripts that the README calls (`scaffold`, `run-walkthrough`, `review-video`, `convert-mp4`), started by absolute path from another folder, loaded its imports and reached its own argument check. No full recording ran.

## Baseline + execution

Result: Passed
Evidence: 2026-11-16, develop b9824ebc: the `Hard Eng` and `Canary` workflows passed on the push. One real Codex session ran `cd sub` and then `pwd` as two shell calls; the second call started in the first folder again, so a folder change does not carry over.
Execution: One builder, this session.

## Risks + recovery

N/A — text of one optional skill and one test; a revert restores both.

## ux_reference

N/A — skill text and a test; no visible UI.

## Verification

Result: Passed
Evidence: `tests/test_skill_links.py` and `tests/test_skill_routing.py`: 17 passed. The four scripts started by path from another folder, as the third acceptance line says. The Complete check passed on this branch.
Reader: a reader that did not write the text compared the old and new skill text. It quoted the README sentence on `<skill>` (unclear "it") and the SKILL.md sentence (no meaning for `<skill>`); both were reworded.
Review: the Codex adversarial review approved cacc191a. The independent review at cacc191a had two findings: no Reader record, and only two of four scripts started by path. Both are repaired above.
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: (1) The independent review found no Reader check on changed skill text → `.agents/skills/code-review/references/review.md` "Skill text" rule caught it; None — the existing review rule worked. (2) The same review found the third acceptance line checked with two of four scripts run → None — a judgement the existing review found; the line now names all four.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
