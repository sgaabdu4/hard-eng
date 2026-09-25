# Keep gates usable while agent worktrees exist and a build spans several turns

Status: Draft

## Outcome + scope

Fix [#169](https://github.com/sgaabdu4/hard-eng/issues/169) and the Hard Eng half of [#168](https://github.com/sgaabdu4/hard-eng/issues/168). Stop accepts a Ready plan whose Verification is Pending (a build in progress) by running the checks at Ready, unless the agent's last message claims `Ready for ship`; pre-push and CI still require Complete. Setup ignores `.claude/worktrees/`, so current-file scans skip agent worktrees. Non-goals: other agents' worktree paths (Codex keeps its worktrees outside the repository), and a Hard Eng workaround for dart-decimate package discovery, which is fixed at its owner in [sgaabdu4/dart-decimate#115](https://github.com/sgaabdu4/dart-decimate/issues/115).

## Repository context

Owners: `.hooks/agent_hooks.py` (`completion` runs `check --base` at Stop), `.hooks/plans.py` (`validate_plans` requires Complete for non-Markdown changes when no stage is given), `setup.py` (`configure_ignores`), `.hooks/gitleaks_scan.py` (`scan_paths` uses `git ls-files --others --exclude-standard` and rejects untracked directories that are not gitlinks). HE Build keeps plans Ready with Verification Pending until the final Complete gate. Claude Code and Codex both send `last_assistant_message` in Stop input ([hooks reference](https://code.claude.com/docs/en/hooks.md)).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix every open issue, file and fix the dart-decimate part through a subagent, run `/codex:adversarial-review` after all fixes, and merge.

## Acceptance + steps

- [ ] Stop with a Ready + Verification Pending plan and a code change passes at Ready with a "build in progress" notice; the same turn claiming `Ready for ship` still requires Complete → `tests/test_plans.py::test_stop_accepts_a_ready_plan_mid_build_until_ship_is_claimed`.
- [ ] Pre-push and CI behaviour is unchanged: ordinary `check` still requires Complete → existing `tests/test_plans.py` stage tests.
- [ ] An installed project with a worktree at `.claude/worktrees/<name>` has no worktree paths in the current-file scan inventory → `tests/test_updates.py::test_installed_project_scans_skip_agent_worktrees`.
- [ ] dart-decimate stops discovering nested checkouts and ignored packages → upstream PR for #115.
- [ ] Full gate passes; `/codex:adversarial-review` findings resolved.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `bc92b48` → exit 0; 17/17 gates PASS, 817 tests passed; 1m39s wall.
Execution: One builder in Hard Eng; one subagent fixes dart-decimate in an isolated worktree of that repository.

## Risks + recovery

A turn that finishes without the exact `Ready for ship` phrase is checked at Ready; the HE Build handoff still requires the Complete gate before that phrase, and pre-push/CI still require Complete. Recovery: tighten the claim detection. Hosts without `last_assistant_message` are treated as mid-build.

## ux_reference

N/A — hook, gate and installer behaviour with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — native Stop hook through `hard-eng.py stop` on a fixture repository; real `git worktree add .claude/worktrees/<name>` in an installed project.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
