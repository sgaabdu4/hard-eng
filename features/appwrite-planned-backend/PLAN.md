# Install the Appwrite skill for a planned backend

Status: Complete

## Outcome + scope

Setup installs the `appwrite-backend` skill when Appwrite is planned or configured, not only when code imports its SDK, and no installed skill page links to a stack skill that setup left out. Non-goals: installing stack skills into every project, changing MCP server settings, changing the stack skills themselves.

## Repository context

Owners: `.hooks/agent_hooks.py::integrated_services` decides the stack skills (`setup.py::unused_skills`) and the MCP servers (`.hooks/mcp_setup.py::detected_servers`). Links into stack skills: `.agents/skills/he/references/integrations.md`, `.agents/skills/he-plan/SKILL.md`, `.agents/skills/e2e/`.
Same cause: a new React and Appwrite project got no Appwrite skill. Hard Eng was installed before any backend code, and the server code called Appwrite over plain HTTP, so no SDK import ever matched. Its `appwrite.config.json` and `APPWRITE_ENDPOINT` were not signals. The agent used old collection APIs and never used MCP. The same link gap exists for Flutter: he-plan and e2e link to `building-flutter-apps`, which a project without Dart does not get. No earlier fix of this cause. Hard Eng updates read the base branch, so the file must land there first; a setup rerun with no newer release would add the skill but drops its commit (open issue #430), so the next release's update PR is the working path.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-10-28: "Fix the Hard Eng gap so the Appwrite skill installs for a planned backend, and the integrations link never points at a missing file." No commit or push without approval (AGENTS.override.md).
Decision: Appwrite counts as planned when the repository has an Appwrite project file (`appwrite.json` or `appwrite.config.json`, already Appwrite files in `.hooks/change_size.py`). A planned backend without code commits that file with `projectId` + `endpoint` to the base branch; the next Hard Eng update PR adds the skill. `APPWRITE_ENDPOINT` alone stays no signal: `tests/test_mcp_setup.py::test_installer_registers_only_detected_service_mcps` keeps a shell value from adding Appwrite to every project. Links into stack skills become plain skill names, so they cannot point at a missing file.

## Acceptance + steps

- [x] An Appwrite project file marks Appwrite as integrated without SDK imports → `tests/test_agent_hooks.py::test_planned_appwrite_counts_without_sdk_imports`.
- [x] Setup in a new project with `appwrite.config.json` installs the Appwrite skill, and the pending MCP message names a file that exists → `tests/test_mcp_setup.py::test_planned_appwrite_setup_installs_the_skill`.
- [x] A new project without Appwrite or Dart has no skill link to a missing file → `tests/test_skill_links.py::test_installed_skill_links_resolve_without_stack_skills`.
- [x] After the file lands on the base branch, the next update branch holds the skill and its link; the same holds for `pubspec.yaml` and the Flutter skill → `tests/test_update_pr.py::test_next_update_adds_the_stack_skill_the_base_branch_now_needs`.
- [x] Source skill links still resolve → `tests/test_skill_links.py::test_distributed_skill_links_resolve`.

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
Evidence: The new Appwrite cases fail with the old `.hooks/agent_hooks.py` and pass now; the Flutter update case passes on both, as before. `tests/test_agent_hooks.py`, `tests/test_mcp_setup.py` and `tests/test_skill_links.py` pass (141). `integrated_services` on the React and Appwrite project from the report now returns `["Appwrite"]`; it returned `[]` before. Codex adversarial review (gpt-6-astra): round 2 no material findings; round 3 found that a setup rerun reads the base branch, fixed in the text and the update test above; round 4 no material findings. `python3 .hooks/hard-eng.py check` passed every gate (1988 tests). Remaining: #430 blocks the setup-rerun path.
E2E: N/A — the tests run the real setup against fixture repositories.
Delivery target: Merge
Delivery: Pending — the PR merges into develop after its checks pass.
