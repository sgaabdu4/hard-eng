# Install Claude-only rules into projects

Status: Complete

## Outcome + scope

Setup copies Hard Eng's `.claude/rules/*.md` into each project and updates refresh or retire them, so Claude-only guidance (subagent models, long-running subagent briefs) loads without spending `AGENTS.md` budget that Codex shares. Project-owned files in `.claude/rules/` stay untouched; a same-named project file is refused like any other scaffold conflict. Ships `model-roles.md` and `subagents.md`. Non-goals: adding these rules to `AGENTS.md`, Codex equivalents, per-project rule selection.

## Repository context

Owners: `.hooks/update.py` (`scaffold_files` defines what setup copies and what updates retire; `maybe_installed` marks paths a verified scaffold-only update may change), `setup.py` (`scaffold_changes` copies scaffold files at the same relative path), `tests/conftest.py` (`release_template`), tests in `tests/test_updates.py`. Source lives at `.claude/rules/` — the same relative path it installs to, as `.agents/skills` and `.hooks` already do, so no path mapping is needed. The path is not ignored (`git check-ignore` exit 1).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User requested this change delivered as one PR; that request approves the branch commits and PR under `AGENTS.override.md`. Merge follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] Fresh install → both rules copied byte-equal to source; a project's own `.claude/rules/team.md` unchanged; rerun changes nothing → `test_install_adds_claude_rules_and_keeps_project_rules[team.md]`.
- [x] Project file already at a Hard Eng rule path → install refused, nothing written → same test, `model-roles.md` case.
- [x] Update adds a new source rule and refreshes a changed one in the update commit; the project rule is preserved → `test_update_refreshes_claude_rules_and_keeps_project_rules`.
- [x] Rule removed from the source → update deletes the unedited copy; an edited copy is refused with `Local scaffold edit`, edit and revision kept → same test, `edited` case.
- [x] An update that changes rules still passes the scaffold-only check → `maybe_installed` covers `.claude/rules/`; `check_scaffold_update` asserted in the same test.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `fbd7c672` + this plan → exit 0, 17/17 PASS, 1199 tests passed (after `git submodule update --init` in the fresh worktree).
Execution: One builder; first slice is `scaffold_files` + rule files with the install test.

## Risks + recovery

A project that already keeps a same-named rule file blocks setup until the user resolves it — the existing conflict path, preserving their file. Recovery: rename either file.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: The four new test cases pass. Reverting the `scaffold_files` rules glob fails all four new test cases; reverting the `maybe_installed` prefix fails the unedited update case at `check_scaffold_update`. `setup.sh` and `fetch_sources` use full clones, so released rules reach installs and updates.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0, 17/17 PASS, 1203 tests passed.
E2E: N/A — installer/updater file transformation; proof is fixture install and update tests plus the gate.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
