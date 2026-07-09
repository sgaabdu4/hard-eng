---
name: resolving-merge-conflicts
description: Use when resolving an in-progress git merge or rebase conflict.
---

# Resolving Merge Conflicts

Resolve the active merge or rebase without discarding either side's intent.

## Contract

- Read the current merge/rebase state first
- Trace each conflict to primary sources
- Preserve both intents where possible
- Run the project's automated checks after resolving
- Continue the merge/rebase only after conflicts and checks are clean

Load `references/workflow.md` before editing conflicts.
