# zizmor private runners and Bun function calls

Status: Complete

## Outcome + scope

1. The `ci-security` gate turns off zizmor's `self-hosted-runner` audit only in private repositories (issue sgaabdu4/hard-eng#303). Public repositories keep it.
2. The Bun LCOV to Istanbul converter counts a function's calls from its entry line, and as zero when Bun reports no called function in the file (issue sgaabdu4/hard-eng#302).
Non-goals: no zizmor version pin; no other audit changes; no Fallow command change.

## Repository context

Owners: [gitleaks_scan.py](../../.hooks/gitleaks_scan.py) `zizmor_config` (already turns off `self-repository`); [fallow_report.py](../../.hooks/fallow_report.py) `write_istanbul`.
Evidence: zizmor 1.31.0 with Hard Eng's `--persona=auditor` reported low-confidence `self-hosted-runner` findings in four private projects whose jobs reach their own runner only for the owner's same-repository pushes and PRs; 1.30.1 passed the same files. Bun 1.4.3 LCOV for a file with a never-called and a called function: `DA:1,0` and `DA:6,12` on their entry lines, but `DA:4,1` inside the never-called body, so the old maximum-over-span count marked it called.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix the new Hard Eng issues and merge, and to run the release canary afterwards. Codex adversarial review loop (gpt-6-astra) before the PR; merge when green.
Decisions: A private repository's runners cannot be reached by outside fork PRs, which is the risk the audit guards; the visibility comes from `gh repo view`, and any lookup failure keeps the audit on. A project's own `self-hosted-runner` rule wins. The private-repository fork-PR workflow setting is not checked: reading it needs administration access the CI token lacks, so local and CI gates would disagree; GitHub keeps it off by default. A pin would only delay the same audit. For Bun calls the entry line is the closest signal Bun gives; Bun's per-file FNH:0 rules out calls where a module-level arrow function's first line ran at load.

## Acceptance + steps

- [x] Private repository → `self-hosted-runner` off; public → on; a project's own rules, including its own `self-hosted-runner` rule, kept → `test_ci_security_gate_turns_off_only_audits_that_cannot_apply`, red before.
- [x] A never-called function whose body line Bun counted gets 0 calls; a called one gets its entry-line count; FNH:0 gives 0 → `test_bun_lcov_marks_a_function_with_a_hit_body_line_but_no_call_uncalled`, red before.
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red tests, fixes, real zizmor 1.31.0 rerun, full check, Codex loop, PR, merge; the release canary runs after the merge at the user's request.

## Risks + recovery

A private repository that allows workflows from fork PRs keeps a smaller risk the audit no longer reports. Recovery is reverting this branch.

## ux_reference

N/A — gate configuration and coverage conversion only; no product appearance.

## Verification

Result: Passed
Evidence: Each new test failed before its fix and passed after. Real zizmor 1.31.0 with the new config passed three private projects that failed before.
E2E: Passed — real zizmor 1.31.0 runs on private projects; real Bun 1.4.3 LCOV for the function fixture.

Delivery target: Merge
Delivery: Pending — PR CI, merge, then the release canary.
