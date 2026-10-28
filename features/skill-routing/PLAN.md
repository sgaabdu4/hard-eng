# Route Research and Security Review from the Hard Eng workflow

Status: Complete

## Outcome + scope

Agents load Research for stack, vendor or version choices and "look online" asks, and load Security Review for changes to sign-in, permissions, API keys, payments, uploads or personal data. Non-goals: the SessionStart text, the session hook import crash (not reproduced), new skills.

## Repository context

Owners: `.agents/skills/he-plan/SKILL.md` (Context line), `.agents/skills/he-build/SKILL.md` (Behavior line), `.agents/skills/code-review/SKILL.md` (routes), the `research` and `security-review` descriptions. Evals: `tests/agent_checks.py`, fixtures in `tests/agent_fixtures.py`.
Same cause: a skill-use audit of Hard Eng projects found zero Research loads, although users asked for research and "look online" many times. Security Review ran only when a subagent brief named it; it did not run on a sign-in and per-team API key change in a personal-data app. he-plan loaded Research "only when needed", no workflow skill linked Security Review, and both descriptions lacked the words users type. Code Review, which a commit review loads, had no route to Security Review. CI then showed that an adoption whose lint fixes touch commented files fails its first full check: the comment check counted the old blocks, and adoption recorded the gates' own fix reports as debt. The eval judge counted only the first SKILL.md a command read, so a Codex run that read three skills in one command was judged as loading one. No earlier fix of this cause.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-28: "Yes. Fix the routing so security-review and research get used, in PR 431." PR 431 had merged, so this ships as its own PR to develop. No commit or push without approval (AGENTS.override.md); the request covers this PR.
Decision: routing lives in he-plan, he-build, Code Review and the two descriptions. The SessionStart line stays as it is: naming both skills there gave Opus no gain (4/4 with and without) and Haiku 1/4 against 0/4, which does not pay for words in every session. The two descriptions keep their total word count (72 words before and after).

## Acceptance + steps

- [x] A "look online" prompt ranks Research first, and an API key and personal-data prompt ranks Security Review first → `tests/test_skill_routing.py::test_every_request_picks_its_own_skill`.
- [x] No two descriptions grow too alike → `tests/test_skill_routing.py::test_no_two_descriptions_are_too_alike`.
- [x] he-plan stays under the Codex skill size limit → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.
- [x] A model asked to look online for a vendor choice loads Research → N/A — not a pytest test; the on-demand model eval `routes-to-research` in `tests/agent_checks.py` proves it, results under Verification.
- [x] A model asked to check a commit that stores API keys loads Security Review → N/A — not a pytest test; the on-demand model eval `routes-to-security` in `tests/agent_checks.py` proves it, results under Verification.
- [x] A command that reads several SKILL.md files counts each skill → `tests/test_agent_checks.py::test_skill_routing_is_judged_from_the_skills_each_client_loaded`.
- [x] CI repair: the brownfield sample drops the ended Python 3.10 before its lock upgrade, so fixed filelock releases resolve → `tests/test_release_canary.py::test_the_brownfield_upgrade_drops_the_ended_python`.
- [x] In the change that installs Hard Eng, a comment block a file already held stays old code when the install's tools touch that file; new or changed blocks still fail, and later changes answer for every block → `tests/test_comments.py::test_the_install_change_keeps_older_blocks_in_files_its_tools_fixed` and `tests/test_comments.py::test_the_install_change_compares_each_older_block_whole`.
- [x] When adoption's gates fix files, adoption records what the fixed code still fails with → `tests/test_debt.py::test_adoption_records_what_the_fixed_code_still_fails_with`; the local brownfield canary passes with these fixes alone.
- [x] CI repair: the measured CI budget rises from 300 to 420 seconds; full runs took 253 to 306 seconds → `tests/test_ci_setup.py::test_generated_ci_timeout` and the PR's `hard-eng` job.
- [x] Each client's skill loads are read from its own records → `tests/test_agent_checks.py::test_skill_routing_is_judged_from_the_skills_each_client_loaded`.

## Baseline + execution

Result: Passed
Evidence: Branch point develop 7d4d05d1; its PR #431 passed all 16 CI checks.
Execution: One builder, this session; Codex adversarial review before the final evals.

## Risks + recovery

N/A — skill text and tests only; a wrong route costs one extra skill load.

## ux_reference

N/A — skill text only; no visible UI.

## Verification

Result: Passed
Evidence: The two new routing prompts fail on the old descriptions and pass now; the two-skill judge test fails with the old matcher and passes now. Model evals, 2 runs per case: Opus 5.5 on the final commit, research 2/2 and security 2/2; an earlier commit without the Code Review route and with a trivia prompt, 1/4. Codex GPT 6 Astra on the old text, research 0/2 and security 2/2; on the routing commit, 4/4; on the final commit, 4/4. Haiku 5.5, 0/4 on the old text with the trivia prompt and 0/4 on the final commit: it answers or reviews without loading any skill, the same gap earlier Haiku evals recorded. Codex adversarial review (gpt-6-astra): routing, 2 rounds, no material findings; adoption fixes, 2 rounds: round 1 found that the old-block match stopped short of blocks with a blank comment line, fixed; round 2 no material findings. Local brownfield canary: PASS. `python3 .hooks/hard-eng.py check` passed every gate (1992 tests).
E2E: N/A — the model evals load the installed skills in a fixture project.
Delivery target: Merge
Delivery: Pending — the PR merges into develop after its checks pass.
