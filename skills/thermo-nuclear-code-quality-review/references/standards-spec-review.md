# Standards And Spec Review

Use this for PR, branch, commit, or spec-linked review.

## Axes

- Standards: the code is structurally weak, hard to maintain, unsafe, duplicated, or under-tested even if it matches the requested change
- Spec: the code does not satisfy the stated user request, PRD, issue, plan, contract, or acceptance criteria

Findings should name the axis. A single issue can be both.

## Review Shape

- Read the user request, PR description, plan, or spec before judging intent
- Read full hunks and nearby owners before judging structure
- Compare implementation against public behavior, contracts, routes, schema, fixtures, and tests
- Separate required changes from optional design taste
- Prefer deletion, owner reuse, and simpler invariants over new wrappers

## Smell Baseline

Challenge duplicated logic, pass-through abstractions, primitive obsession, shotgun edits, feature flags scattered through busy flows, nullable mode explosions, hidden fallbacks, large files without owner boundaries, and tests that assert implementation details instead of behavior.
