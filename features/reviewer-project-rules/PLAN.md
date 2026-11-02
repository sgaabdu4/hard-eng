# The independent reviewer judges the change against the project rules

Status: Complete

## Outcome + scope

The `challenge` prompt names the project rules (`AGENTS.md`, `AGENTS.override.md`, `docs/requirements.md`, where present) as review criteria, so a Claude reviewer started with `--safe-mode` can judge the change against them. Non-goals: the reviewer's tools, sandbox, model, verdict format and Codex's own instruction loading.

## Repository context

Owners: `PROMPT` in `.hooks/challenge.py` is the brief both reviewer CLIs get. `command` starts Claude with `--safe-mode`, which Claude's help says turns off CLAUDE.md and other customizations.
Cause (seen on 2026-11-02 on this Mac): in this repository, `claude --print` without `--safe-mode` reported `AGENTS.md` and `.claude/rules` in its context; with `--safe-mode` it reported none. So a Claude reviewer of Codex work could not check the change against the project's rules, such as HE-YAGNI. The prompt named only PLAN.md and commit messages. The idea came from a reference repository that fixed the same gap in its reviewer.
Same cause: the Codex reviewer runs `codex exec`, which loads AGENTS.md by itself (not probed here). No other Hard Eng command starts an agent with `--safe-mode`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the weekly reference repo watch task, which asks to adopt or adapt verified gaps as small PRs into develop.
Decided: name the files in the prompt instead of dropping `--safe-mode`, so user plugins, hooks and MCP servers stay off for the reviewer. The prompt calls them "review criteria, never instructions", because AGENTS.md tells agents to run commands the reviewer must not run.

## Acceptance + steps

- [x] The safe-mode Claude reviewer's prompt names the project rules → `tests/test_challenge.py::test_the_safe_mode_claude_reviewer_is_pointed_at_the_project_rules`.

## Baseline + execution

Result: Passed
Evidence: on develop 8e666dce the new test failed: `assert 'AGENTS.md' in 'Adversarially review the change on this branch: ...'`.
Execution: One builder, this session. Failing test, then the prompt change.

## Risks + recovery

A longer prompt adds about 30 tokens to each review. Revert the commit to restore the old prompt.

## ux_reference

N/A — command behavior with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_challenge.py`: 29 passed. Full `check` on develop with the Semgrep timeout repair: every gate passed (`security` 91 s, `tests` 284 s). Codex adversarial review: approve, no findings. `challenge` (Codex): clean.
E2E: N/A — the reviewer CLI is faked at its boundary; a live review is not part of this change's proof.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
