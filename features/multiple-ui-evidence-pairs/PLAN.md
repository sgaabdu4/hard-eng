# Multiple UI evidence pairs

Status: Complete

## Outcome + scope

A changed UI PR may publish more than one Before/After pair. Keep the missing, duplicate, foreign-URL and unchanged-UI rejections. Do not change upload behavior or other parsers.

## Repository context

`.hooks/ship_evidence.py` required exactly one `Before:` and one `After:` attachment. `.hooks/shipping.py` checks each returned URL at GitHub. `tests/test_shipping.py` owns the integration seam. The HE Ship checks reference owns the user-facing rule.

## Decisions + authorization

Blockers: None

The user asked for this change and a task PR. The write set is the evidence parser, its shipping tests, the checks reference and this plan.

## Acceptance + steps

- [x] A changed UI PR with an image pair and a video pair passes, and all four attachments are checked at GitHub.
- [x] A PR with unequal Before and After counts, no pair, or any repeated URL fails at the shipping verification seam.
- [x] The HE Ship checks reference states the one-or-more-pairs rule.

## Baseline + execution

Result: Passed
Evidence: Before the parser change, the new two-pair test failed with the one-pair error. After it, the 92-case shipping suite passed.

## Risks + recovery

A PR could pair the wrong Before with the wrong After. The verifier checks counts and distinct URLs only. People and E2E inspection own the pairing. Revert the parser change to return to one pair.

## ux_reference

N/A — this changes a native evidence parser and command documentation, with no product screen or rendered product interaction.

## Verification

Result: Passed
Evidence: The two-pair accept test failed before the change and passed after it. Two reject cases (a repeated pair and unequal counts) pass. The full shipping suite passed with 92 tests.
E2E: N/A — the shipping verifier fixture exercises the PR-body parsing boundary without a product or device journey.

Delivery target: PR
