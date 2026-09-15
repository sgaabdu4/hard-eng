# Remove acceptance-flow verification repetition

Status: Complete

## Outcome + scope

Keep post-merge receipts in the final report and native remote evidence, without another documentation-only PR. Use the existing Git base option for plan-only edits after a matching passed baseline. Strengthen the updater collision regression by asserting the installed marker bytes are unchanged.

## Repository context

Independent greenfield and brownfield CLI acceptance runs delivered their requested behavior, then each created an unnecessary follow-up PR to replace pending delivery prose. A fresh human-mode run repeated full checks after correcting plan wording. The existing shipping guidance and affected-check option already own these behaviors; no new runner, state record or test framework is necessary. The existing updater transaction test checks HEAD but also needs a direct marker assertion to catch unstaged mutation.

## Decisions + authorization

Blockers: None
The user authorized full workflow enforcement and efficiency repairs while preserving YAGNI/KISS. Update the two existing workflow owners and the existing regression; this plan is the required task record. Keep baseline, pre-push, CI and real delivery proof mandatory.

## Baseline + execution

Result: Passed
Evidence: Source b707b67 passed PR CI and integrated Complete/pre-push checks. Greenfield and brownfield native CLI journeys passed and their merged main CI is green. The fresh brownfield SessionStart actually updated the installed source before repository inspection.

## Acceptance + steps

- [x] The shipping owner explicitly puts post-merge receipts in the final report and native evidence, without another receipt PR.
- [x] Plan-only wording/state changes reuse matching baseline proof with affected checks.
- [x] Ignored local configuration rejection directly proves marker bytes remain unchanged.
- [x] Full source Ready integration checks pass; Complete/pre-push and hosted checks remain mandatory for delivery.

## Risks + recovery

Affected verification must not conceal unverified code or configuration. Retain the matching-baseline requirement and full fallback for unknown impact. Native remote checks remain the delivery proof; prose alone cannot establish it.

## ux_reference

N/A — workflow guidance and a transaction regression have no product UI.

## Verification

Result: Passed
Evidence: Both focused updater transactions pass, including saved marker bytes. The full source Ready gate passed. The native Ready command with --base HEAD passed against the real brownfield plan-only change: it ran workflow/security checks and did not repeat application tests. Existing baseline proof remained intact. Complete/pre-push and hosted checks remain mandatory before delivery; the overall pilot also repeats approved shipping after publication.
E2E: Passed — the existing native affected-check command validated the real plan-only fixture change, retaining shared security/workflow checks and the passing application baseline. This source change adds guidance, not a new runtime path; post-publication consumer behavior remains part of the overall acceptance pilot.

Delivery target: Merge
Delivery: Pending
