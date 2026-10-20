# Keep every Hard Eng skill inside the Codex skill size limit

Status: Complete

## Outcome + scope

A test fails when a Hard Eng SKILL.md passes 8,000 bytes. Codex cuts an invoked skill's body after 8,000 bytes (`MAX_SKILL_PROMPT_BYTES` in `codex-rs/ext/skills/src/render.rs`, openai/codex `e18a20d`). Its skills extension (`extension.rs`) applies the cut to every explicitly invoked skill, disk skills included. Its core fallback (`host_prompt.rs`) cuts only plugin skills, and a skill the agent reads with a shell command is never cut. So the cut depends on the path, but a skill over the limit can lose its end. HE Plan drops from 9,047 to under 8,000 bytes and puts Participation + Readiness + authorization right after Routes, so the authorization rules can never be cut. Non-goals: skills from submodules (`appwrite-backend`, `building-flutter-apps`; their own repositories own their size), new rules, other skills.

## Repository context

Owners: `tests/test_skill_links.py` (skill loadability tests, next to `frontmatter_failures`); `.agents/skills/he-plan/SKILL.md`. Only HE Plan is over the limit; HE Ship is next at 6,727 bytes.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. Abid asked to build the six-repo ideas into Hard Eng, to push and open PRs, and to decide pending items himself; PR targets `develop`.

## Acceptance + steps

- [x] Every SKILL.md this repository owns is at most 8,000 bytes → `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit` passes; it failed on `develop` with he-plan at 9,047 bytes.
- [x] An oversized skill fails, a skill at the limit passes and a symlinked submodule skill is skipped → `tests/test_skill_links.py::test_an_oversized_skill_fails_unless_a_submodule_owns_it`.
- [x] The canary's agent copy leaves out git lock files, so background git maintenance cannot break the copy and a stale lock cannot block git in it → `tests/test_release_canary.py::test_git_locks_in_the_target_never_reach_the_agent_copy`.
- [x] HE Plan keeps its links and routes after the reorder → `tests/test_skill_links.py::test_distributed_skill_links_resolve` and `tests/test_skill_routing.py::test_every_request_picks_its_own_skill`.

## Baseline + execution

Result: Passed
Evidence: `develop` `70d7b0f` in a clean worktree: `uv run --with pytest-xdist pytest -q -n auto tests` → 1756 passed, 1 skipped, 8 failed. All 8 need tools absent here (`dart`, Xcode `xccov`) or signal timing (`test_interrupted_pre_push_removes_its_snapshot`).
Execution: One builder; test first, then the HE Plan rewrite.

## Risks + recovery

Shorter wording could drop a rule. Each bullet keeps its rule; two clauses now point to their single owner instead (the template for test naming, gates.md plan checks for Approval evidence). Revert the HE Plan commit to restore the old text.

## ux_reference

N/A — no visible product change; test and Markdown only.

## Verification

Result: Passed
Evidence: Same command after the change → 1758 passed, 1 skipped, the same 8 environment failures. HE Plan = 7,807 bytes after a Writing Great Skills review restored its pending-proof steering line. Real Claude runs on the final HE Plan: `tests/agent_checks.py --client claude --case planning-only` → PASS; `--case routes-to-plan` → PASS. CI run 39402328881 failed `test_an_agent_run_passes_only_when_hard_eng_recorded_a_passing_check`: copytree hit a maintenance lock that git removed mid-copy. The new lock test failed before the `release_canary.try_agent` fix and passes after; `tests/test_release_canary.py` → 12 passed. ruff format, ruff lint, pyrefly (0 errors) and vulture pass on the test file. gitleaks, osv-scanner, shellcheck and actionlint cannot install in this container (GitHub API 403); CI runs them. Independent review: not done, Codex is not installed here; no Codex agent run.
E2E: N/A — no user journey; the unit tests prove the limit.

Delivery target: PR
Delivery: Pending — hard-eng CI on the PR into develop.
