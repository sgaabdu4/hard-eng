# Merge only current branches, state the undo, learn from escaped bugs

Status: Complete

## Outcome + scope

`ship` refuses a PR that is behind its base, `ship` refuses a PR body without an `Undo:` line, and HE Learn treats the first bug found on the base branch after a merge as a trigger. Non-goals: a merge queue service, GitHub branch-rule changes, review-round limits, human approval paths, an eval set or metrics.

## Repository context

Owners:
- `_ready_state` in `.hooks/shipping.py:873` verifies the open PR for `ship --stage ready` and `--stage merge`. It accepts `mergeable_state == "clean"`. GitHub reports `behind` only when the branch rule requires an up-to-date branch (`shipping.py:806` reads that rule only on the admin-bypass path). Without that rule, a PR behind the base merges, and the combined code is checked only after the merge.
- The PR body is already loaded into `_PullRequest.body` (`shipping.py:357`) and checked for UI evidence (`ship_evidence.py`) and attribution (`shipping.py:936`). `update_pr.py` writes the "Update Hard Eng" PR body.
- `he-ship/SKILL.md` "PR =" line lists the PR body parts; it has no undo part. Hard Eng merges by rebase only (`ship_actions.py:477`), so a PR with several commits has no one-commit revert.
- `he-learn/SKILL.md` "Recurrence" line starts Learn on a repeat, or at once only for a false pass or a protected boundary. A bug that reaches the base branch for the first time does not start it, and nothing asks which gate should have caught it.
- Agent behavior proof: `tests/agent_checks.py` (on demand, not in CI), with the `repeat_failure` case as the model for a new case.
Same cause: Gap 1 is one cause: the ready check trusts GitHub's `clean`, which ignores a behind branch when no strict rule exists. The admin-bypass path (`shipping.py:806`) refuses a strict rule because an admin merge would skip it; no path checks whether the PR head is behind. `update_pr.py` does not use `ship`: it rebuilds the update branch when it is not current on the fetched base (`branch_current`), so neither new check applies to it. Gaps 3 and 4 have no earlier fix.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Approved by the user on 2026-11-01 ("yes it is correct, you do it"): gaps 1, 3 and 4 from the Claude Code review article, the three recommendations below, build, commit and push to the task branch. Round limits and human-approval paths were rejected. Opening the PR needs the user's request. Accepted recommendations:
1. Behind check uses GitHub's compare API (`behind_by` must be 0) for the PR head against the base, so it needs no local fetch. Unknown or invalid data refuses the PR.
2. `Undo:` is enforced by the ship ready check (Hard Eng enforces with checks, not only skill text). The check needs a non-empty `Undo:` line; it cannot judge whether the steps are right.
3. HE Learn change is skill text plus one agent check case, because a changed trigger needs real agent proof (`he-learn/SKILL.md`, "Behavioral proof").

## Acceptance + steps

- [x] A PR whose head is behind the base is refused at `ready` and `merge` with a message that says to rebase and rerun checks; a current PR passes; unknown compare data refuses → `tests/test_review_bypass.py::test_ready_refuses_a_pr_behind_its_base`.
- [x] A PR body without a non-empty `Undo:` line is refused at `ready`; a body with one passes → `tests/test_review_bypass.py::test_ready_requires_an_undo_line`.
- [x] `he-ship` PR line asks for `Undo:` steps that fit a rebase merge (revert each commit, plus non-Git steps such as migrations or flags); README Ship section says the same → N/A — skill text; proven by the two ship tests above and the skill-link tests.
- [x] A first bug found on the base branch after a merge starts HE Learn; the agent names the gate that should have caught it and adds a test that fails on the merged code before the fix → `tests/test_agent_checks.py::test_escaped_bug_needs_a_test_that_fails_on_the_merged_code` for the judge, then one real run: `tests/agent_checks.py --client claude --case escaped-bug`. Non-trigger cases stay valid: `review-only` and `failed-baseline` agent cases in the same run.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on 7624c88. First run failed: the two skill submodules were not checked out in this cloud clone, so `secrets-files` and 300 tests failed on `Unresolved skill link`. After `git submodule update --init --recursive`, the rerun passed (exit 0): it reused the branch point's passed CI and ran the secret scan, which passed.
Execution: One builder (Sonnet) in order: gap 1 test then code, gap 4 tests then code and text, gap 3 text then agent case. One fresh Opus reviewer on the final diff. Codex is not installed here, so `challenge` is not available; record that.

## Risks + recovery

- GitHub native auto-merge merges without `ship`, so the behind check does not cover it. Recovery: the user turns on "require branches to be up to date" in the branch rule; this plan does not change branch rules.
- Every existing project PR now needs an `Undo:` line, so an open PR made before the update fails `ready` until the body is edited. The refusal message names the missing line.
- One more GitHub API call per ready check.

## ux_reference

N/A — shipping checks and skill text; no visual surface.

## Verification

Result: Passed
Evidence:
- Ship tests: `tests/test_review_bypass.py` (36 passed) failed first on the old code (9 cases), then passed. With the other ship tests: 212 passed.
- Full gate `python3 .hooks/hard-eng.py check` on the final code: every gate passed except `tests`, which had 6 failures (2120 passed). These are the same 6 as on the starting commit: they need `dart` and `swiftc`, which this container does not have. CI runs them.
- Reader check (Writing Great Skills) on all changed text: two rounds, all findings fixed. Fresh Opus review: 3 findings (judge did not prove HE Learn loaded, wrong test file in the plan, `Undo:` steps had to be on the same line), all fixed in their own commits.
- Agent runs, Claude, `tests/agent_checks.py`: run 1 had no sandbox (`bubblewrap` missing), so no shell command could run; not counted. After installing `bubblewrap` and `socat`: escaped-bug run 2 PASS (read HE Learn, new test failed with `1 != 1.5`, then fixed, named the `tests` gate). After the shorter `AGENTS.md` text: run 3 FAIL, because the agent put a correct fix in a linked worktree and the judge reads only the main folder; run 4 FAIL only on "never loaded he-learn": the agent read HE Learn with the Read tool, which the judge did not count. After the judge fix, run 4's recorded events show `he-build` and `he-learn` loaded, so run 4 meets every check. Nearby case `failed-baseline` PASS.
- Limits: the agent moved to a worktree because `check` counts the sandbox's empty placeholder files (`.bashrc`, `.mcp.json`) as new files. That is a separate bug, queued as its own task. Independent review not done: Codex is not installed in this container.
E2E: N/A — the ship tests drive the real `verify` with a fake GitHub API, as in `features/review-threads-block-ship`; a live merge is not repeatable in tests. The agent journey is proven by the `escaped-bug` agent check above.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green; open only on the user's request.
