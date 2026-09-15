# Advance the canonical Appwrite skill reference

Status: Complete

## Outcome + scope

Advance the existing canonical Appwrite skill submodule pointer to the verified
upstream revision that corrects Dart Function authentication examples. Do not copy
or edit the canonical skill contents in this repository.

## Repository context

Hard Eng distributes the canonical backend guidance through
`.agents/skill-sources/appwrite-backend`. Its current pointer predates the
upstream correction. The upstream revision passed its master CI before this
integration task began.

## Decisions + authorization

Blockers: None
The user authorized this pointer-only release, pull request, merge and delivery.
The existing submodule is the source of truth; a pointer update is sufficient and
avoids a divergent local copy.

## Acceptance + steps

- [x] The submodule pointer resolves to the verified upstream revision.
- [x] Existing source contracts accept the updated pointer without copied skill
  content or unrelated source changes.

## Baseline + execution

Result: Passed
Evidence: The clean source main checkout is at the prior verified release. The
upstream canonical repository reports successful master CI for the target
revision. Local inspection shows the task diff contains only the submodule
pointer and this required plan.

## Risks + recovery

An unavailable or incompatible submodule revision blocks publication. Restore the
previous pointer if its focused source contract fails; do not patch the
distributed copy to hide an upstream issue.

## ux_reference

N/A — this is a documentation-source pointer update with no product UI.

## Verification

Result: Passed
Evidence: Upstream master CI passed for the selected canonical revision. The
canonical skill's source contract passed 24 tests on the selected pointer.
Native pre-push results remain pending on the exact committed candidate.
E2E: N/A — no user-facing runtime behavior changes here.

Delivery target: Merge
Delivery: Pending — PR merge, main CI and native delivered verification are
required.
