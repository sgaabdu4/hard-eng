# Mutation Receipt

1. Placement = every feature before ship: `plan_state.py record-mutation` on the green tree per runner → `he-ship` `assert-green` refuses without a current receipt covering every source file changed since the approval base (`receipts/mutation.json`); inner-loop slice gates + commit/push hooks = forbidden.
2. Runner = project-pinned dependency resolved from the repository lockfile; JS/TS candidate = Stryker; Python candidate = mutmut; Dart/Flutter = no accepted runner → `runner none` + `sensitivity_proof` from `test-quality`.
3. First wiring per repository = `research` PASS on the runner's current CLI/config contract; this file never pins external invocation syntax.
4. Execution = `bounded_run.py` + explicit whole-run timeout; not a manifest family → impacted-owner scope allowed + recorded in the receipt.
5. Receipt = tool + version + exact argv + declared scope (every changed file for that runner's languages; test/regression files excluded) + totals (killed/survived/timeout/no_coverage) + one ledger row per survivor; one run per runner, mixed-language scope in one run = refused.
6. Deterministic `PASS` = run completed on declared scope + survivor total equals ledger rows; missing run/scope/row = `FAIL`.
7. Survivor disposition (fixed | equivalent | invalid | deferred + consequence) = `test-quality` judgment; kill-score threshold alone = insufficient.
