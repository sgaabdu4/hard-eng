---
name: setup-pre-commit
description: Use for Husky, lint-staged, Prettier, typecheck, test, or commit-time quality hook setup.
user-invocable: true
---

# Setup Pre-Commit

Install deterministic commit-time formatting, typecheck, and test hooks for the current repo.

Load `references/workflow.md` before editing.

Preserve existing hook/formatter config unless the user approves changes. Do not
commit unless the user explicitly asks.
