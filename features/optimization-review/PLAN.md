# Optimisation review follow-ups

Status: Complete

## Outcome + scope

Settle the ten review points one at a time with the user, then build the agreed ones. Non-goals: points the user rejects; reopening settled decisions (three languages, pnpm only, shipped Claude rules and video skill, retired MCP tools).

## Repository context

Owners: `.hooks/plans.py` (`validate_plans`, `is_documentation`), `.hooks/gate_config.py` (`changed_files`), `.hooks/agent_hooks.py` (`completion`), `.hooks/update.py` (`require_current`), `.hooks/update_runner.py` (`commit_update`).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User approved building points 1-8 and 10 on 2026-10-07, with commits and a push to this branch, everything in one PR. Before opening the PR: loop Codex adversarial review on gpt-6-astra, fixing only genuine, realistic, substantial issues. Test in different project types.

### Point 1: small changes skip the plan (decided 2026-10-07)

- A script decides the size from the branch's full diff against its merge base with main. The agent never decides and cannot mark a change small; the user can always ask for a plan.
- Small when every changed file is documentation under the existing `is_documentation` rule, or when all of these hold:
  - 20 changed lines or fewer (added plus removed) across 3 files or fewer.
  - No added, deleted or renamed files; no binary files.
  - No change to dependency manifests or lockfiles, CI workflows, `.hooks/`, `.agents/`, `hard-eng.gates.json`, `AGENTS.md` or database files.
  - No removed lines in test files.
- Anything else is big and needs a plan as today.
- Small skips only the plan requirement. Every check still runs.
- The script prints the verdict and the first reason, for example "Size: big, because it adds a new file".

### Point 2: update checks never block a reply (decided 2026-10-07)

- End of reply makes no GitHub requests. It reuses the result of the session-start update; offline, a GitHub error or a newer version gives a note, never a block.
- Shipping (`ship_actions.py`, PR or merge) keeps the live check and still blocks when Hard Eng is out of date or freshness cannot be confirmed.

### Point 3: updates arrive as their own auto-merged PR (decided 2026-10-07)

- Background updates never commit onto a feature branch. They prepare the update on its own branch only.
- An agent pushes that branch, opens a "Update Hard Eng" PR and turns on auto-merge. No human approval; it merges only once its checks pass. Use the repo's allowed merge method.
- Before shipping, the agent looks for an open update PR. None open and Hard Eng is out of date: it opens one. Update PR failing: it fixes that PR first, in its own worktree on the update branch, waits for the merge, rebases the feature branch on main, then continues.
- Hard Eng update PRs are allowed alongside the main PR (user's one-PR rule exception, recorded in the user's global git rule). Hard Eng's shipped instructions state the same exception.
- This replaces the settled rule "the installer/updater never pushes" for update PRs only.
- Accepted side effect: in repos that deploy on every change to main, each update merge also triggers a deploy.
- Release pace unchanged: every CI-verified Hard Eng commit is a version. At most one update PR is open per project; a newer version moves the open PR forward instead of opening another.

### Point 4: quick checks after each reply, full checks before push (decided 2026-10-07)

- The Stop hook runs a fixed quick set, chosen by gate name, never by the agent: format, lint, types, tests for the changed packages, and the current-files secret scan (Python `format`, `lint`, `imports`, `types`, `annotations`, `tests`, `secrets-files`; JavaScript `format-lint`, `types`, `typing-style`, `focused-tests`, `secrets-files`; Dart `format`, `types-lint`, `tests`, `secrets-files`). Exact per-language list to confirm at build time.
- Pre-push and CI keep running every gate, as today, so nothing reaches GitHub without the full set.
- Failure output shows the list of failed gates, then the first failing gate's output from its start, not the last 16,000 characters of the log.

### Point 5: decision notes are matched to changed files (decided 2026-10-07)

- Each ADR in `docs/adr/` gains an `Applies to:` line listing one or more path prefixes (for example `src/payments/`). The he-learn template and guidance require it.
- After each reply, the Stop hook compares the changed files it already lists against every Accepted ADR's prefixes with a plain prefix match. No model judgment.
- On a match, the hook stops the agent once and shows the ADR's Decision text, asking it to confirm its change follows it. Each ADR is shown at most once per session.
- Cleanup: `check` flags an Accepted ADR whose prefixes match no file in the repository, asking to update or retire it.
- Existing ADRs without the line: to settle at build time (likely flagged once so the line gets added).

### Point 6: skill routing is tested (decided 2026-10-07)

- A free offline pytest scores sample requests against every model-invocable skill description by word overlap; each request's own skill must rank first, and two descriptions that are too alike fail. Runs in this repository's normal tests and CI. No model calls.
- Add a few "picked the right skill" cases to the existing real-agent runner (`tests/agent_checks.py`), run on demand when descriptions change.
- Limit stated in the test: word overlap approximates, but does not prove, how a model selects.
- Hard Eng source only; installed projects receive the better-tested skills, not the test.

### Point 7: review reports on every plan item (decided 2026-10-07)

- One reviewer, as today. The review result must include a "Plan match" list: each acceptance item in the task's PLAN.md marked met or not met, with the test or check result as proof. No item may be skipped; no plan means the review says so.
- Owner: `.agents/skills/code-review/references/review.md`.
- Cross-model challenge (decided 2026-10-07): before shipping any change the point 1 rule rates big, the other agent challenges it. Work done in Claude Code is challenged by Codex; work done in Codex is challenged by Claude Code. Hard Eng picks by the running host, not by agent choice, and calls the other CLI directly (not the user-installed `/codex:adversarial-review` plugin), so it works wherever both CLIs exist. Missing or signed-out CLI: record "independent review not done", never skip silently. The host verifies each finding against source and fixes only reachable defects. Small changes skip it. This replaces the "no fixed provider" line in `code-review/references/challenge.md`.

### Point 8: changes cannot switch off checks (decided 2026-10-07)

- A new gate reads only the added and removed lines of the change (diff against the merge base) and fails on a fixed per-language pattern list: lint or type suppressions (`noqa`, `type: ignore`, `pyrefly: ignore`, `eslint-disable`, `@ts-ignore`, `@ts-expect-error`, `biome-ignore`, Dart `// ignore:` and `ignore_for_file`), skipped or focused tests (`pytest.mark.skip`, `pytest.skip(`, `xfail`, `.skip(`, `.only(`, `xit`, Dart `skip:`), and removed assertion lines in test files (`assert`, `expect(`).
- Runs in the quick set after each reply (point 4) and in pre-push and CI.
- Existing lines in brownfield projects are never flagged; only new changes.
- No exceptions or allow-list, per the user's never-suppress rule.
- Failure names the file, line and pattern and says to fix the cause.

### Point 9: no Hard Eng `verify` skill (dropped 2026-10-07)

- Claude Code's bundled `/verify` records an app-driving recipe at `.claude/skills/verify/SKILL.md` and runs any `verify` skill before commits (v2.1.286+). A Hard Eng `verify` would replace that recipe and could be rewritten by Claude Code, breaking updates. Point 4's quick checks plus pre-push cover the gain. Do not add one.

### Point 10: setup adopts projects instead of refusing them (decided 2026-10-07)

- CLAUDE.md with content: no change. The refusal already tells the agent to move rules into AGENTS.md and rerun; Claude Code reads AGENTS.md only when no CLAUDE.md exists.
- 10a, existing checks (decided): at setup the agent lists the project's existing checks (pre-push and pre-commit scripts, CI check jobs) beside Hard Eng's gates and shows the user a comparison: use Hard Eng's where it does the same or better; keep a project check Hard Eng lacks by adding it as a gate in `hard-eng.gates.json`, so Hard Eng's one pre-push hook runs everything; when unsure, keep both. Nothing project-owned is removed until the user approves the comparison.
- 10a, gap issues (decided): when Hard Eng lacks a check the project has, the agent files an issue on sgaabdu4/hard-eng automatically, without asking, after searching for a duplicate. The issue names only the missing check, never the project, its code, paths or names (publication privacy). This narrows AGENTS.md's "with their approval" rule for these check-gap issues only.
- 10b, other languages (decided): a project with no supported manifest installs in basic mode instead of being refused: AGENTS.md rules, skills, current-files and history secret scans, the shared security scan, and the project's own checks absorbed under 10a. No new language-specific gates (three-language decision stands). Setup files one deduplicated gap issue per language, such as "No built-in checks for Go". An empty repository keeps today's "ask which project type to create" path.

## Acceptance + steps

- [x] Point 1: a small code fix with no plan passes and prints "Size: small"; each disqualifier names its reason and still needs a plan; docs don't count toward size; small changes ship without a plan → `tests/test_plans.py`, `tests/test_shipping_plan.py`.
- [x] Point 2: the Stop hook never blocks on freshness and makes no update-freshness request; quick checks use installed tools offline; shipping still blocks when stale → `tests/test_agent_hooks.py`, `tests/test_planning_handoffs.py`, `tests/test_ship_actions.py`.
- [x] Point 3: updates prepare `hard-eng/update` without touching the current branch; `update-pr` publishes one PR and merges only after every check on the exact head passed, with the repo's allowed method; remote fixes are kept; rebase- or squash-merged fixes don't block later updates; no origin is a plain wait → `tests/test_update_pr.py`, `tests/test_update_runner.py`.
- [x] Point 4: Stop runs only the quick roles and shows `Failed gates:` and the first error first → `tests/test_quick_check.py`, `tests/test_stop_checks.py`.
- [x] Point 5: an Accepted ADR's `Applies to:` prefix blocks once per session with its Decision; new ADRs need the line; deleting the last file under a prefix fails → `tests/test_decisions.py`, `tests/test_stop_checks.py`.
- [x] Point 6: sample requests rank their own skill first and no two descriptions are too alike; three on-demand agent routing cases → `tests/test_skill_routing.py`, `tests/test_agent_checks.py`.
- [x] Point 7: reviews report Plan match per item; big changes need a cross-model challenge record before shipping, `not done` is stated → `tests/test_challenge.py`, `tests/test_ship_actions.py`.
- [x] Point 8: added suppressions, skips (incl. module-level and bare `mark`) and net-removed assertions fail; existing lines don't → `tests/test_comments.py`.
- [x] Point 10: existing pre-push hooks (plain, Husky, lefthook-managed) are kept and run first; a replaced launcher is reported; other languages install in basic mode; gap issues dedupe and refuse project detail; stock Dart pubspec and `uv init --package` entry points work → `tests/test_hook_chain.py`, `tests/test_basic_mode.py`, `tests/test_gap_issue.py`, `tests/test_dart_config.py`.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on b35a2a7e plus this plan: main's CI passed at that commit, secret scan PASS, exit 0.
Execution: Sequential Sonnet builders, one point per commit, in order 2, 4, 1, 8, 5, 3, 7, 6, 10; coordinator reviews each diff.

## Risks + recovery

A one-line behaviour change can skip planning. Recovery: all checks still run, and the user can require a plan.
Accepted limits (judged unrealistic in review): an update fix made by amending the generated update commit can be replaced by a newer update; Stop misses an edit that restores a file already changed at session start. Removed test `test_interrupt_after_installing_reports_the_installed_revision`: updates no longer write the user's checkout, so an interrupt can't leave a half-installed marker.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: Full `check --plan-stage Ready --base origin/main` passed 18/18 gates after rebasing on origin/main (1424 tests). Six Codex adversarial review rounds on gpt-6-astra; every realistic finding fixed with a regression test; the loop stopped when only narrow cases remained (see Risks). End-to-end fixtures (Python, TypeScript/pnpm/vitest, Dart package, Go basic mode with its own pre-push hook, Python with CLAUDE.md, Python with its own pre-push, Python without origin) exercised setup, Size verdicts, quick Stop, offline Stop, suppression guard, ADR matching, hook chaining, gap-issue (fake gh) and a real Codex challenge; findings were fixed. The cross-model challenge (`hard-eng.py challenge`, Codex) then found five more realistic defects (update merge ignoring a failing extra check, wrong package output in multi-package Stop summaries, nested JavaScript Markdown counted as documentation, Scala/F# repos treated as empty, hook not restored before first publication); each fixed with a regression test. PR CI exposed a test clone without a git identity; fixed. Not run: real upstream update publication and an end-to-end `ship` against GitHub.
E2E: Passed — a real `claude -p` session in a fresh `uv init --package` project changed one line with no plan; the Stop hook ran only quick gates and returned a short, first-error-first reason (a real PRODUCT.md prerequisite); `check --quick` then printed `Size: small (1 file, 2 changed lines); no plan needed.` A 4-file or new-file change printing `Size: big` and failing was proven in the fixture runs.

Delivery target: Merge
Delivery: Pending — PR CI on GitHub, then rebase merge.
