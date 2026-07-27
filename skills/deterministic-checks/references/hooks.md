# Hook Wiring

1. Existing tracked hook manager = owner; absent → `.githooks/` + setup runs `git config core.hooksPath .githooks`.
2. `pre-commit` = fast staged lint/format; React adds its staged scanner command.
3. `pre-push` = affected-full from push base..head → universal + impacted-owner gates.
4. CI = same classifier + gate commands; required status = one always-run aggregate; expensive jobs skip only proven non-impacted scope.
5. Hooks invoke project commands only; non-blocking/failed/cancelled result = `FAIL`.
