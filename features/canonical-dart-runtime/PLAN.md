# Adopt the canonical Dart runtime boundary guidance

Status: Complete

## Outcome + scope

Advance the existing Appwrite skill submodule to its verified default-branch revision. Keep the untyped Open Runtimes host context at function entrypoints and pass validated values into typed handlers. No copied consumer skill, adapter package or private project details.

## Repository context

The canonical function examples previously passed dynamic context through application helpers. The canonical reference now documents the actual generated runtime's private context type, narrowly scoped lint exceptions and typed request conversion. This source change only advances the existing submodule pointer and records the required plan.

## Decisions + authorization

Blockers: None
The user authorized fixing the canonical Appwrite owner and distributing it through Hard Eng. The canonical default branch is master; use its merged revision fbf1737069c98552f6cf39fc1cf2357c9f33ee6c.

## Baseline + execution

Result: Passed
Evidence: Hard Eng source f60caaf passed its PR gate. The preceding verified source 77776e8 passed main CI. Canonical Appwrite PR 6 and its merged default-branch CI passed all 56 contract tests.

## Acceptance + steps

- [x] The canonical reference describes the actual supported runtime boundary.
- [x] Existing canonical changes and native safety contracts remain present.
- [x] The submodule points to the merged canonical revision.

## Risks + recovery

Advancing the wrong branch could omit prior guidance. The new commit descends from the previous pinned 12fac79 revision and changes only the function reference. Revert the pointer if integrated checks fail.

## ux_reference

N/A — skill reference guidance has no product UI.

## Verification

Result: Passed
Evidence: The actual Open Runtimes context/server invocation fixture passed. All 56 canonical tests and hosted CI passed. The source Complete/pre-push gates remain mandatory before shipping this pointer.
E2E: Passed — invoked the actual Open Runtimes context through the documented Future<Object?> entrypoint boundary. Function package tests verify typed input conversion; no invented public context import is required.

Delivery target: Merge
Delivery: Pending
