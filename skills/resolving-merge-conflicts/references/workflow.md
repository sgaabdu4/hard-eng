# Resolving Merge Conflicts Workflow

## Current State

Inspect:

- `git status --short`
- merge or rebase state files
- conflicting files
- relevant git history

## Primary Sources

For each conflict, understand why both sides changed:

- commit messages
- PRs
- issues or tickets
- surrounding code
- tests and docs tied to the change

## Resolve

Preserve both intents where possible. When they are incompatible, pick the resolution matching the merge's stated goal and note the trade-off.

Always resolve intentionally. Do not abort unless the user explicitly asks.

## Verify

Discover and run the project's automated checks, usually:

- typecheck
- tests
- format

Fix anything the merge broke.

## Finish

Stage resolved files and continue the merge or rebase process until complete.
