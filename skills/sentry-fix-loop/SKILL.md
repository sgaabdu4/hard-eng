---
name: sentry-fix-loop
description: Fix a Sentry issue, ship the fix, clean merged work, and close the issue.
disable-model-invocation: true
---

Inspect and reproduce the Sentry issue. Fix its root cause, add a regression test, run checks, commit, and push to `origin/main`. Delete only branches and worktrees proven merged into `origin/main`. Close the issue after verification. Preserve unrelated work and report blockers.
