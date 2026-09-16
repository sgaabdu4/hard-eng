# Advance the canonical Appwrite skill reference

Status: Complete

## Outcome + scope

Advance the existing canonical Appwrite skill submodule to the verified upstream
revision that documents the Dart Function runtime ABI boundary. Do not copy or
edit canonical skill content in this repository.

## Repository context

Hard Eng distributes backend guidance through
`.agents/skill-sources/appwrite-backend`. The selected upstream revision
clarifies that the generated runtime context is private, confines dynamic work
to one documented boundary, and requires typed application handling beyond it.

## Decisions + authorization

Blockers: None
The user authorized this pointer-only release, pull request, merge, and delivery.
The existing submodule is the source of truth; an updated pointer avoids a
divergent local copy.

## Baseline + execution

Result: Passed
Evidence: The selected canonical revision `7dd4a895c336d7889f53bd062569b52a2a5a1843`
is merged on its default branch. Its main CI passed and its 58 source contracts
and pinned formatter check passed before publication.

## Acceptance + steps

- [x] The submodule pointer resolves to the verified upstream revision.
- [x] The source diff contains no copied canonical skill content.
- [x] The exact Hard Eng candidate passes its native Ready gate.

## Risks + recovery

An unavailable or incompatible submodule revision blocks publication. Restore
the prior pointer if integrated checks fail; do not patch the distributed copy
to conceal an upstream issue.

## ux_reference

N/A — this is a guidance-source pointer update with no product UI.

## Verification

Result: Passed
Evidence: The upstream main CI and local canonical contracts passed for the
selected revision. The exact pointer candidate passed the source Ready gate
with 687 tests. Native pre-push, PR, main CI, and Delivered checks remain
required for publication.
E2E: N/A — the canonical owner separately proved its runtime boundary.

Delivery target: Merge
Delivery: Pending — PR merge, main CI, and native Delivered verification are
required.
