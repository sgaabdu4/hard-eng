# Playwright E2E

- Existing Playwright config/scripts/spec style = runner owner.
- Durable test = isolated state/account/data + stable role/label/test-id selectors + user-visible assertions.
- Shared mutable state, order dependence, arbitrary sleeps, implementation selectors = invalid proof.
- Explore with browser control when useful; regression proof runs through project Playwright.
- Trace = targeted diagnosis or `on-first-retry`; always-on heavy recording = avoid.
- Retry-pass = flaky evidence, not `PASS` → `$diagnosing-bugs`.
- Failure evidence = failing assertion + screenshot + trace/console/network only when diagnostic.
