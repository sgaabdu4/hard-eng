# Media attachment compatibility

Status: Complete

## Outcome + scope

Accept the native GitHub CLI video evidence body shape: a `Before:` or `After:`
label followed by one standalone allowed GitHub asset URL. Preserve the existing
Markdown-image form and all missing, duplicate, foreign-URL, and unchanged-UI
rejections. Document direct `gh pr create` and `gh pr edit` use with
`--body-file` and `--attach`. Do not alter shipping policy, upload behavior,
other parsers. Record the separately approved, verified required status check
in the existing decision checklist.

## Repository context

`.hooks/ship_evidence.py` currently accepts only same-line Markdown image
references. `.hooks/shipping.py` consumes its URLs and checks the attachment
at GitHub. `tests/test_shipping.py` owns the integration seam. The existing
HE Ship checks reference owns the user-facing command guidance.

## Decisions + authorization

Blockers: None

The user authorized this source repair and its publication through a task PR
and merge. The allowed write set is the evidence parser, its owned regression
coverage, shipping guidance, the branch-protection decision, and this plan. The
user separately approved requiring the GitHub Actions `hard-eng` check on main;
existing protections remain unchanged. No global installation or unrelated
project changes are authorized.

## Acceptance + steps

- [x] A changed UI PR accepts distinct inspected Markdown image attachments.
- [x] A changed UI PR accepts distinct inspected native-video URLs on the line
  after each `Before:` and `After:` label.
- [x] Missing, duplicate, foreign, and unchanged-appearance evidence still
  fails at the shipping verification seam.
- [x] HE Ship guidance shows `gh pr create` and `gh pr edit` with
  `--body-file` and `--attach`, with no browser-upload prerequisite.
- [x] After explicit approval, native GitHub readback confirms the required
  `hard-eng` check, administrator enforcement, and disabled force pushes/deletion.
Focused regression proof, the native local CLI flag probe, and all 17 Complete
source gates passed, including 709 tests and 88.38% line coverage.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` passed all 17
source gates after hydrating this worktree's recorded skill submodules; its
native test gate reported 699 passed and 88.37% line coverage. The smallest
slice is a parser grammar extension followed by the existing shipping
integration test double; no new library or wrapper is needed.

## Risks + recovery

GitHub CLI rewrites an attached video reference to a standalone raw URL. The
official documentation and local `gh` help are the current evidence; the
focused test will distinguish the native shape from a broader URL relaxation.
If it fails, retain the existing strict grammar and report the unsupported body
shape rather than accepting arbitrary URLs.

## ux_reference

N/A — this changes a native evidence parser and command documentation, with no product screen or rendered product interaction.

## Verification

Result: Passed
Evidence: The original parser produced the expected focused RED: native-video
and mixed image/video cases failed. The repaired 17-case focused regression and
the full 56-case shipping suite passed. The CRLF native-video regression also
failed before the final regex correction and passed after it. Targeted Ruff
format/lint checks passed. Local `gh` 2.100.0 help listed `--attach` and
`--body-file` for both `gh pr create` and `gh pr edit`.
E2E: N/A — a deterministic local shipping verifier fixture exercises the
native PR-body parsing boundary without a product or device journey.

Delivery target: Merge
Delivery: Pending — PR checks, merge, main CI, and guarded cleanup remain required.
