# Standards And Spec Evidence

For PR, branch, commit, or spec-linked review, the `code-review` skill and its
[two-axis contract](../../code-review/references/two-axis-review.md) own axis
classification and the final report.
Thermo-Nuclear Review contributes maintainability evidence and severity inside
those separate Standards and Spec sections. When one underlying issue affects
both axes, report the distinct evidence under each axis; do not merge or rerank
the axes into one severity-only list.

## Review Shape

- Read the user request, PR description, plan, or spec before judging intent
- Read full hunks and nearby owners before judging structure
- Compare implementation against public behavior, contracts, routes, schema, fixtures, and tests
- Classify every accepted finding under Standards or Spec using the two-axis owner
- Separate required changes from optional design taste
- Prefer deletion, owner reuse, and simpler invariants over new wrappers

## Smell Baseline

Challenge duplicated logic, pass-through abstractions, primitive obsession, shotgun edits, feature flags scattered through busy flows, nullable mode explosions, hidden fallbacks, large files without owner boundaries, and tests that assert implementation details instead of behavior.
