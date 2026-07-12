---
name: setup-pre-commit
description: Use when explicitly asked to set up pre-commit or commit-time hooks with Husky or lint-staged.
user-invocable: true
---

# Setup Pre-Commit

Install deterministic commit-time formatting, typecheck, and test hooks for the current repo.

Load `references/workflow.md` before editing.

Preserve existing hook/formatter config unless the user approves changes. Do not
commit unless the user explicitly asks.
