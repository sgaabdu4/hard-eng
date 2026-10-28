# Install the Appwrite skill for a planned backend

Status: Complete

## Outcome + scope

Setup installs the `appwrite-backend` skill when Appwrite is planned or configured, not only when code imports its SDK, and no installed skill page links to a stack skill that setup left out. Non-goals: installing stack skills into every project, changing MCP server settings, changing the stack skills themselves.

## Repository context

Owners: `.hooks/agent_hooks.py::integrated_services` decides the stack skills (`setup.py::unused_skills`) and the MCP servers (`.hooks/mcp_setup.py::detected_servers`). Links into stack skills: `.agents/skills/he/references/integrations.md`, `.agents/skills/he-plan/SKILL.md`, `.agents/skills/e2e/`.
Same cause: a new React and Appwrite project got no Appwrite skill. Hard Eng was installed before any backend code, and the server code called Appwrite over plain HTTP, so no SDK import ever matched. Its `appwrite.config.json` and `APPWRITE_ENDPOINT` were not signals. The agent used old collection APIs and never used MCP. The same link gap exists for Flutter: he-plan and e2e link to `building-flutter-apps`, which a project without Dart does not get. No earlier fix of this cause. Hard Eng updates read the base branch, so the file must land there first; a setup rerun with no newer release added the skill but dropped its commit, and skipped new checks in `hard-eng.gates.json` (#430): `build_update` looked only for the update commit message, and `update_pr.publish` saw nothing to publish at the same revision.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-28: "Fix the Hard Eng gap so the Appwrite skill installs for a planned backend, and the integrations link never points at a missing file." Then: fix all open GitHub issues in this PR (#430). No commit or push without approval (AGENTS.override.md).
Decision: Appwrite counts as planned when the repository has an Appwrite project file (`appwrite.json` or `appwrite.config.json`, already Appwrite files in `.hooks/change_size.py`). A planned backend without code commits that file with `projectId` + `endpoint` to the base branch, then reruns setup; its update PR adds the skill. `APPWRITE_ENDPOINT` alone stays no signal: `tests/test_mcp_setup.py::test_installer_registers_only_detected_service_mcps` keeps a shell value from adding Appwrite to every project. Links into stack skills become plain skill names, so they cannot point at a missing file.

## Acceptance + steps

- [x] An Appwrite project file marks Appwrite as integrated without SDK imports → `tests/test_agent_hooks.py::test_planned_appwrite_counts_without_sdk_imports`.
- [x] Setup in a new project with `appwrite.config.json` installs the Appwrite skill, and the pending MCP message names a file that exists → `tests/test_mcp_setup.py::test_planned_appwrite_setup_installs_the_skill`.
- [x] A new project without Appwrite or Dart has no skill link to a missing file → `tests/test_skill_links.py::test_installed_skill_links_resolve_without_stack_skills`.
- [x] After the file lands on the base branch, the next update branch holds the skill and its link; the same holds for `pubspec.yaml` and the Flutter skill → `tests/test_update_pr.py::test_next_update_adds_the_stack_skill_the_base_branch_now_needs`.
- [x] A setup rerun with no newer release keeps its repair on the update branch and `update-pr` opens one repair PR, then none after it merges → `tests/test_update_pr.py::test_setup_rerun_without_a_newer_release_publishes_its_repair`.
- [x] That repair also writes the workflow checks `hard-eng.gates.json` needs → `tests/test_update_pr.py::test_setup_rerun_repair_adds_the_workflow_checks_with_the_workflow`.
- [x] The repair branch counts as files the verified update wrote, so pre-push needs no plan for it → same repair test, `change_size.size_verdict`.
- [x] A repair with a follow-up fix still publishes after the base moves; a merged repair is never published again, even after the base later removes a file it added → same repair test.
- [x] A merged update plus fix publishes nothing when no newer release exists, after rebase or squash merge → `tests/test_update_pr.py::test_update_pr_publishes_nothing_after_a_merged_fix_without_a_newer_release`.
- [x] Source skill links still resolve → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.
- [x] The shipped Appwrite skill is the merged 2.6.2 update (appwrite-backend PR #27, master CI passed), so new installs ask for TablesDB scopes → `tests/test_skill_links.py::test_distributed_skill_links_resolve` and the full check on the moved submodule.

## Baseline + execution

Result: Passed
Evidence: Branch point develop ef19d969; its release PR #429 passed `hard-eng`, `canary` and every new-project job in CI.
Execution: One builder, this session.

## Risks + recovery

N/A — a repository file is the only new signal; projects without one install the same files as before.

## ux_reference

N/A — setup and skill text only; no visible UI.

## Verification

Result: Passed
Evidence: The new Appwrite cases fail with the old `.hooks/agent_hooks.py` and pass now; the Flutter update case passes on both, as before. `tests/test_agent_hooks.py`, `tests/test_mcp_setup.py` and `tests/test_skill_links.py` pass (141). `integrated_services` on the React and Appwrite project from the report now returns `["Appwrite"]`; it returned `[]` before. Codex adversarial review (gpt-6-astra): round 2 no material findings; round 3 found that a setup rerun reads the base branch, fixed in the text and the update test above; round 4 no material findings. The two #430 repair tests fail with the old update code and pass now. Codex adversarial review of #430, 6 rounds: rounds 1 to 5 found the squash-merge replay, the pre-push plan need and a follow-up fix after the base moves, all fixed; round 6 found that a base change before the first repair publish skips it, not changed because rerunning setup recovers it. The Appwrite skill submodule is at the merged appwrite-backend PR #27, whose master CI passed. `python3 .hooks/hard-eng.py check` on the final tree passed every gate (1992 tests).
E2E: N/A — the tests run the real setup against fixture repositories.
Delivery target: Merge
Delivery: Pending — the PR merges into develop after its checks pass.
