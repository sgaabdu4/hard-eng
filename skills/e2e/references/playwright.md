# Playwright E2E

- Existing Playwright config/scripts/spec style = runner owner.
- Durable test = isolated state/account/data + stable role/label/test-id selectors + user-visible assertions.
- Shared mutable state, order dependence, arbitrary sleeps, implementation selectors = invalid proof.
- Explore with browser control when useful; regression proof runs through project Playwright.
- Trace = targeted diagnosis or `on-first-retry`; always-on heavy recording = avoid.
- Retry-pass = flaky evidence, not `PASS` → `diagnosing-bugs`.
- Failure evidence = failing assertion + screenshot + trace/console/network only when diagnostic.

## Video proof

- Video gate = `e2e` SKILL owner; this file = capture mechanics only.
- Primary producer = `product-walkthrough-video` proof mode: `"pointer": false` + default strict config → undecorated frames; decorated/overlaid media ≠ proof.
- Proof journeys = click/scroll/type/press + final assertion; `drag` requires the decorated pointer → walkthrough mode only.
- Review report = SHA-256-bound video hash + dimensions + duration + `playbackEvidence` → visual-evidence receipt review fields as `independently_measured`; skill approval feeds, never replaces, the receipt.
- Fallback (skill unavailable) = runner capture `test.use({ video: 'on' })` scoped per spec; repo-wide always-on forbidden.
- Fallback library capture = `browser.newContext({ recordVideo: { dir, size } })` + matching `viewport`; path = `page.video().path()` after `context.close()`; assert final state before close.
- Captured `.webm` must decode with duration + dimensions under the visual-evidence validator; trace `.zip` ≠ video.
- Review + receipt = `visual-evidence.md` owner.
