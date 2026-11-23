# Stop Contrived Syntax-Fuzzing Loops in Independent Challenge

Status: Complete

## Outcome + scope

Tighten the independent challenge prompt and review guidance so cross-model reviews focus on realistic failures and stated security boundaries instead of chaining contrived syntax puzzles across re-review rounds:
1. Update `PROMPT` and `HISTORY` in `.hooks/challenge.py` to require concrete failures under realistic inputs or a bypass of a stated security boundary, and to skip contrived syntax puzzles, style nits, and edge cases outside a documented boundary—especially on narrow fixes or heuristics from earlier rounds.
2. Remind the host when `challenge` returns `findings` to record `Review declined:` for findings disproved or outside a heuristic's documented scope rather than chasing heuristic rewrites.
3. Align `.agents/skills/code-review/references/challenge.md` (`Assignment`, `Re-review`, and `Declined finding`) with the exact same terminology while keeping the source-verification guard on `Review declined:` entries.

Non-goals: weakening real defect or security-boundary checks, skipping independent challenge on big changes, or letting hosts decline findings without source verification or owner decision.

## Sources + coverage

Sources: User's direct instruction in chat on 2026-11-22 (`yes fix challenge then`), read in full.
Reviewer: N/A — small direct prompt and reference update requested by the user.
Deliverables: None

- User instruction, fix challenge synthetic loops: In scope — skip contrived edge cases

## Repository context

Owners:
- `.hooks/challenge.py` owns `PROMPT`, `HISTORY`, and the `challenge()` CLI output.
- `.agents/skills/code-review/references/challenge.md` owns the independent challenge `Assignment`, `Re-review`, and `Declined finding` rules.
- `tests/test_challenge.py` owns contract tests for `PROMPT`, `HISTORY`, and `challenge()` output.

Same cause: `challenge.py` `HISTORY` narrowed re-reviews to `git diff {last} {revision}` without telling reviewers to skip contrived syntax puzzles on previously narrowed heuristics or telling hosts to decline out-of-scope heuristic fuzzing instead of rewriting heuristics endlessly.
Single source: `.hooks/challenge.py` owns the reviewer prompts and CLI guidance; `.agents/skills/code-review/references/challenge.md` owns the independent review rules.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: User directly instructed fixing `challenge` in chat on 2026-11-22.

## Acceptance + steps

- [x] `challenge.py` `PROMPT` instructs reviewers to report concrete failures under realistic inputs or stated security-boundary bypasses and skip contrived edge cases → `tests/test_challenge.py::test_the_prompt_pins_the_reviewed_revision_and_treats_repo_text_as_data`.
- [x] `challenge.py` `HISTORY` guards re-reviews against contrived edge cases while keeping open earlier findings and security-boundary bypasses, and `findings` output reminds hosts to use `Review declined:` for disproved or out-of-scope findings → `tests/test_challenge.py::test_re_review_and_host_output_guard_against_synthetic_chaining`.
- [x] Updated `.agents/skills/code-review/references/challenge.md` passes Writing Great Skills Reader check and skill link/size tests → `tests/test_skill_links.py::test_distributed_skill_links_resolve` and `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.

## Baseline + execution

Result: Passed
Evidence: Branched a clean worktree from `origin/develop` (`60096580`), updated `.hooks/challenge.py`, `.agents/skills/code-review/references/challenge.md`, and `tests/test_challenge.py`, and refined the `challenge.md` sentences after independent Writing Great Skills Reader passes.
Execution: Verified `tests/test_challenge.py`, `tests/test_skill_links.py`, `ruff`, `pyrefly`, full Hard Eng check, and live Codex `challenge` runs.

## Risks + recovery

Overly broad anti-nit wording could make reviewers skip genuine boundary bugs or still-open earlier findings; mitigated by explicitly preserving still-open earlier findings, concrete failures under realistic inputs, bypasses of stated security boundaries, and source verification for every `Review declined:` entry. Recovery: revert the commits on `develop`.

## ux_reference

N/A — Hard Eng CLI and skill reference change with no visual application UI.

## Verification

Result: Passed
Evidence: Independent Writing Great Skills Reader passes checked every edited `challenge.md` sentence (three passes; every quoted phrase reworded). Verified `uv run pytest tests/test_challenge.py tests/test_skill_links.py`, `ruff`, `pyrefly`, and `hard-eng.py check --quick --base origin/develop --plan-stage Complete`; full check and round-2 challenge run before shipping.
E2E: N/A — prompt and reference update covered by unit contract tests and skill link checks.
Real service: Passed — Codex CLI: ran live `challenge.challenge(..., host="agy")` on two synthetic repositories using the revised prompt; Case A (removed path-containment check in `read_doc`) returned `VERDICT: findings` reporting the path-traversal bypass, and Case B (narrow case-insensitive regex fix on re-review with a documented `Review declined:` scope boundary) returned `VERDICT: clean` with no contrived edge cases.
Retro: Repeated multi-round synthetic Markdown fuzzing in `challenge` exposed missing anti-puzzle materiality rules in `challenge.py` and `challenge.md` → `tests/test_challenge.py::test_the_prompt_pins_the_reviewed_revision_and_treats_repo_text_as_data` and `tests/test_challenge.py::test_re_review_and_host_output_guard_against_synthetic_chaining`.

Delivery target: Merge
Delivery: Pending — rebase onto `develop` after `#693`, run full check + challenge, PR, CI, and merge.
