# Advance the Appwrite skill to its Appwrite 2.2 schema guard fix

Status: Complete

## Outcome + scope

Advance the canonical Appwrite skill submodule to the merged upstream revision
whose schema guard works against Appwrite 2.2 and CLI 27.3. Do not copy or edit
canonical skill content in this repository.

## Repository context

Hard Eng distributes backend guidance through
`.agents/skill-sources/appwrite-backend`. Skill version 2.1.5 fixes
`appwrite-schema-guard.mjs`, which failed every capture and check on Appwrite
2.2 output before comparing schemas.

## Decisions + authorization

Blockers: None
The user authorized this pointer-only bump after the installer PR merged. The
existing submodule is the source of truth; an updated pointer avoids a
divergent local copy.

## Baseline + execution

Result: Passed
Evidence: Revision `8a4572ecca844d7e4ce2ee42436791b1dcdc85e7` is merged on the upstream default branch, its Tests check passed, and it descends from the current pin `95c08c9`.

## Acceptance + steps

- [x] The submodule pointer resolves to the verified upstream revision.
- [x] The source diff contains no copied canonical skill content.
- [x] The exact Hard Eng candidate passes its native check.

## Risks + recovery

An incompatible revision blocks publication. Restore the prior pointer if
integrated checks fail; do not patch the distributed copy.

## ux_reference

N/A — this is a guidance-source pointer update with no product UI.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed on the pointer candidate.
E2E: N/A — the canonical owner proved the schema guard with a round-trip test on real Appwrite 2.2 shapes.

Delivery target: Merge
Delivery: Pending — PR merge, main CI, and native Delivered verification.
