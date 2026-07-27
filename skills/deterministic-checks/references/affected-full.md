# Affected-Full Gates

## Contract

- Affected-full = universal gates always + full applicable gate row per impacted owner.
- Classifier = one repository-owned path → owner/dependent map shared by hooks + CI; layout hard-coding in global skills forbidden.
- Changed paths = added + modified + deleted + renamed from push base..head.
- Unknown path + missing/unreachable base + global/shared/toolchain/CI/classifier change → full repository.

## Execute

- Independent owners parallel + bounded; dependency/shared state ordered; external mutation serial via one release actor.
- Hooks + CI run the same classifier + project commands.
- Skip = only scope the classifier proved non-impacted.
- Aggregate PASS = universal + every affected owner green; failure/cancel/unknown → `FAIL`.
- Documentation-only change → universal gates only when repository policy maps no dependent owner.

## Required Regressions

- One owner changed → universal + that owner/dependents only.
- Independent owners changed → both full rows + parallel-safe aggregate.
- Global/shared/toolchain/CI/classifier change → full repository.
- Missing base + unknown path → fail closed.
- Failed/cancelled affected job → aggregate `FAIL`.
