# Hook Wiring

1. Existing tracked hook manager = owner; absent → `.githooks/` + setup runs `git config core.hooksPath .githooks`.
2. `pre-commit` = fast staged lint/format; React adds its staged scanner command.
3. `pre-push` = full affected/project gate; CI = same full command + authority.
4. Hooks invoke project commands only; non-blocking exit = `FAIL`.
