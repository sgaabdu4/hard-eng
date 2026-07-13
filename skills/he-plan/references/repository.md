# Repository Stage

Decision inventory = repository root + canonical remote/project identity + worktree/branch/base/HEAD/dirty state + ignored-input/setup/smoke readiness + feature identity + root `PRODUCT.md`/`DESIGN.md` status + related repositories.

1. Resolve requested feature → candidate repository/worktree.
2. Run `$deterministic-checks` worktree `read` gate → capture identity + immutable revision + dirty evidence.
3. Apply `$deterministic-checks` worktree-readiness workflow → classify ignored state + setup/smoke owners → create/recreate isolated worktree → require `write` PASS.
4. Run `$deterministic-checks` repository-context branch → capture valid/invalid evidence.
5. Missing/invalid pair → apply Stage Route product context + `$atomic-ui` DESIGN route: research code/docs/history/assets → ask unresolved intent → approve → write → validate.
6. Run setup + smallest smoke proof; failure/missing required input → repair provisioning before feature mutation.
7. Search workspace/docs/config → include or rule out coupled repositories; each Git repository owns its own root pair/readiness proof.
8. Reconcile mismatch/inaccessibility → one accepted ready identity + valid approved context pair or blocker.

Complete = isolated `write` PASS + ignored/setup/smoke proof + every identity field proven + root pair valid/current/approved; repository stage cannot skip.
