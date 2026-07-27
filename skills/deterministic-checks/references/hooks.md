# Hook Wiring

1. Existing tracked hook manager = owner; absent → `.githooks/` + setup runs `git config core.hooksPath .githooks`.
2. `pre-commit` = fast staged lint/format; React adds its staged scanner command.
3. `pre-push` = affected-full from push base..head → universal + impacted-owner gates.
4. CI = same classifier + gate commands; required status = one always-run aggregate; expensive jobs skip only proven non-impacted scope.
5. Hooks invoke project commands only; non-blocking/failed/cancelled result = `FAIL`.
6. Git fixture/self-test = `mktemp` cwd + unset every `git rev-parse --local-env-vars` variable (`GIT_DIR` + `GIT_WORK_TREE` + `GIT_COMMON_DIR` + `GIT_INDEX_FILE` + `GIT_OBJECT_DIRECTORY`) + `GIT_CEILING_DIRECTORIES=<fixture parent>`; inherited repository Git environment = `FAIL`.
7. Fixture regression = parent `git rev-parse --git-dir` + `git status --porcelain` identical before/after fixture run.
8. Project-owned hook manager (Husky etc.) self-test = same isolation; machine-uncertifiable → `CONCERNS` + exact wiring proposal.
