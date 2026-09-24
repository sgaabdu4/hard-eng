# Check skill links in CI and agent behaviour on demand

Status: Ready

## Outcome + scope

A pytest check fails on broken relative file links, section anchors and Mermaid routes in distributed skills, including symlinked submodule skills. A source-only, on-demand script runs four real-agent cases in disposable fixtures and saves per-case pass/fail/blocked evidence. Non-goals: runtime hooks, workflow rules, a general eval framework, CI agent runs and skill edits.

## Repository context

Owners: `tests/` holds source-only checks; `setup.py` installs `.hooks`, `.agents`, `.github` and never `tests/`. `changed_packages` in `.hooks/gate_config.py` already selects every gate for any `.agents/` path, including a submodule pointer; `test_changed_package_includes_transitive_dependents_and_shared` proves the skill-path case. `test_setup.py` shows consumers receive symlinked skills as copies at `.agents/skills/<name>`, so links resolve lexically from that path. Reused cases: planning-only, review-only and valid-baseline resume in `features/he-build/PLAN.md`; approved-plan continuation and blocked feature work after a failed baseline in `features/skill-package-review/PLAN.md` and `DECISION.md`. Their `/tmp` fixtures no longer exist. `coverage/` is already ignored and not installed.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for both improvements, source-only, with applicable checks run and actual agent execution.

## Acceptance + steps

- [ ] Current distributed skills pass; a missing file, broken anchor, broken Mermaid click, broken Mermaid path label, wrong-case path and uninitialized submodule skill fail while valid equivalents, external URLs and fenced examples pass → `tests/test_skill_links.py`.
- [ ] Deliberately breaking a real skill click, anchor and submodule link fails the real-repository test.
- [ ] `python3 tests/agent_checks.py` runs planning-only, continue-approved, review-only and failed-baseline cases through `codex exec` in disposable installed fixtures; judges read only fixture files, Git state and command results; results record commit, client version, actual model/settings, timestamp, per-case status and evidence under ignored `coverage/agent-checks/`.
- [ ] Unavailable Codex (not on PATH, logged out, failed or unfinished turn) is reported as blocked.
- [ ] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `34b0703` → exit 0; 17/17 gates PASS, 803 tests passed.
Execution: One builder; link check first, then the agent script.

## Risks + recovery

Agent outcomes vary between runs and models; the script records the actual model and evidence per run rather than claiming stability. Recovery: rerun or narrow a case.

## ux_reference

N/A — test and developer-script change with no visual surface.

## Verification

Result: Pending
Evidence: Pending implementation.
E2E: Required — a real `codex exec` run of all four cases with saved results.
