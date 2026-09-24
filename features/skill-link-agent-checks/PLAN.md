# Check skill links in CI and agent behaviour on demand

Status: Complete

## Outcome + scope

A pytest check fails on broken relative file links, section anchors and Mermaid routes in distributed skills, including symlinked submodule skills. A source-only, on-demand script runs four real-agent cases through Codex or Claude Code in disposable fixtures, isolated from the user's own agent setup, and saves per-case pass/fail/blocked evidence. Follow-up fixes the user approved: HE Plan now says plan-only requests end with a saved PLAN.md, and this repository's types gate checks explicit paths. Non-goals: runtime hooks, new workflow rules, a general eval framework, CI agent runs and the consumer types-gate template.

## Repository context

Owners: `tests/` holds source-only checks; `setup.py` installs `.hooks`, `.agents`, `.github` and never `tests/`. `changed_packages` in `.hooks/gate_config.py` already selects every gate for any `.agents/` path, including a submodule pointer; `test_changed_package_includes_transitive_dependents_and_shared` proves the skill-path case. `test_setup.py` shows consumers receive symlinked skills as copies at `.agents/skills/<name>`, so links resolve lexically from that path. Reused cases: planning-only, review-only and valid-baseline resume in `features/he-build/PLAN.md`; approved-plan continuation and blocked feature work after a failed baseline in `features/skill-package-review/PLAN.md` and `DECISION.md`. Their `/tmp` fixtures no longer exist. `coverage/` is already ignored and not installed. Claude Code's shared `.git/info/exclude` pattern `**/.claude/worktrees/` made project-mode pyrefly match no files inside such a worktree while exiting 0.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for both improvements, source-only, with applicable checks run and actual agent execution, then asked to fix every reported limitation. The consumer types-gate template needs a migration design and is a separate suggested task.

## Acceptance + steps

- [x] Current distributed skills pass; a missing file, broken anchor, broken same-page anchor, broken Mermaid click, broken Mermaid path label, wrong-case path and uninitialized submodule skill fail while valid equivalents, external URLs and fenced examples pass → `tests/test_skill_links.py`.
- [x] Deliberately breaking a real skill click, anchor and submodule link fails the real-repository test.
- [x] `tests/agent_checks.py` runs planning-only, continue-approved, review-only and failed-baseline cases in disposable installed fixtures; judges read fixture files, Git state and command results, plus the final report for the review finding; results record commit, client version, actual model/settings, MCP calls, timestamp, per-case status and evidence under ignored `coverage/agent-checks/`.
- [x] Codex runs use a fresh `CODEX_HOME` sharing only the login; Claude runs use project settings only, user plugins off and no MCP.
- [x] Not on PATH, logged out, failed turn and timeout are reported as blocked.
- [x] Plan-only requests leave a saved PLAN.md → planning-only case across repeated runs.
- [x] The types gate fails a planted type error inside a `.claude/worktrees` checkout.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `34b0703` → exit 0; 17/17 gates PASS, 803 tests passed.
Execution: One builder; link check, agent script, then the reported follow-up fixes as separate commits.

## Risks + recovery

Agent outcomes vary between runs and models; the script records the actual model and evidence per run rather than claiming stability. Recovery: rerun or narrow a case.

## ux_reference

N/A — test, developer-script and skill-wording change with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_skill_links.py` → 2 passed; the real skills resolve 543 prose links, 47 Mermaid clicks and 89 anchors, including same-page anchors. Breaking the `he` testing click, the `he-build` plan-checks anchor, an Appwrite submodule link and a Flutter same-page anchor each failed. Blocked paths: `codex` off PATH, Codex with an empty `CODEX_HOME`, Claude logged out, a 5-second timeout and an unsupported model each reported BLOCKED. Types: project-mode pyrefly printed "No Python files matched" here; with `setup.py .hooks tests` it reports 0 diagnostics and fails a planted `bad-return`. Semgrep flagged an argv-derived subprocess argument, fixed in `64870ac`. `python3 .hooks/hard-eng.py check` on `3ea4ecf` → exit 0, 17/17 gates, 805 tests.
E2E: Passed — on final `3ea4ecf` (codex-cli 0.154.0, effort high, isolated home, workspace-write plus writable `.git`) all four cases PASS on gpt-6-astra (`coverage/agent-checks/20260924T192543Z-codex-gpt-6-astra/`) and gpt-5.6-terra (`20260924T192545Z-codex-gpt-5.6-terra/`), with no MCP calls. Planning-only: 1 of 3 isolated runs passed on the old skill; 8 of 8 after `1a7d74f`. Earlier failures were harness faults, now fixed: stripped Git status (`06504bd`), read-only `.git` stopping branch creation (`47a4953`) and a judge that rejected the separately committed repair AGENTS.md requires (`3ea4ecf`). Claude Code 2.1.281 is logged out here, so every Claude case is BLOCKED; no Claude pass is claimed.
