# External Evidence

1. Define decision + freshness boundary + authoritative source class.
2. Bind local integration = vendor/product + operation + SDK/API version + endpoint/mode/config.
3. Browse exact official docs/API reference/spec/changelog/source for the bound contract.
4. Verify decision-relevant endpoint/method + request/response/state/error + idempotency/order/security semantics.
5. Use secondary sources only for discovery/context; label them.
6. Cite direct URL + publication/update date/version beside every material claim; preserve conflicts.
7. Finish when the decision is answered or missing primary proof is explicit.

- Current/high-stakes fact → browse; cached model memory alone = insufficient.
- Payments/auth/webhooks/data-destructive/infra → official primary proof required even when local code/types/tests agree.
- Model memory + names + local code + SDK types + mocks/tests + secondary sources = discovery; never external contract proof.
- Missing/ambiguous/version-mismatched primary proof → `Unknown` + `CONCERNS|FAIL`; dependent plan/code/review/claim = blocked.
- Quote minimally; summarize within source limits.
