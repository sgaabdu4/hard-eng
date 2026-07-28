# Hook Wiring

1. Existing tracked hook manager = owner; absent → `.githooks/` + setup runs `git config core.hooksPath .githooks`.
2. `pre-commit` = fast staged lint/format; React adds its staged scanner command.
3. `pre-push` = affected-full from push base..head → universal + impacted-owner gates.
4. CI = same classifier + gate commands; required status = one always-run aggregate; expensive jobs skip only proven non-impacted scope.
5. Hooks invoke project commands only; non-blocking/failed/cancelled result = `FAIL`.
6. Every Git subprocess = sanitized environment; Git exports its per-invocation variables to hooks, so an inherited `GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` resolves `-C` + discovery + pathspecs + index against the hook's repository instead of the requested checkout.
7. Sanitation owner = `<agents-root>/skills/deterministic-checks/scripts/git_env.py`; Python passes `env=git_env()` per call or `scrub_environ()` at an entry point; shell runs `unset $(git rev-parse --local-env-vars)`; hook-scoped exception = `git-env-hygiene: exempt <reason>` marker.
8. Git fixture/self-test = `mktemp` cwd + sanitized environment + `GIT_CEILING_DIRECTORIES=<fixture parent>`; inherited repository Git environment = `FAIL`.
9. Fixture regression = parent `git rev-parse --git-dir` + `git status --porcelain` identical before/after fixture run.
10. Project-owned hook manager (Husky etc.) self-test = same isolation; machine-uncertifiable → `CONCERNS` + exact wiring proposal.
