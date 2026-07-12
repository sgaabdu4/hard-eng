# Repository Stage

Decision inventory = repository root + canonical remote/project identity + branch + base/HEAD revision + feature identity + relevant related repositories.

1. Resolve requested feature → candidate repository/worktree.
2. Verify Git identity natively → capture branch + immutable revisions.
3. Search workspace/docs/config → include or rule out coupled repositories.
4. Reconcile mismatch/inaccessibility → one accepted identity or blocker.

Complete = every identity field proven; repository stage cannot skip.
