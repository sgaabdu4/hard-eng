# Investigate

1. Prove CLI + syntax + identity + target: `command -v sentry` → version/help → fresh auth/whoami → explicit `<org>/<project>`.
2. Fix scope: IDs/query + environment + time window; `all` → exhaust pagination.
3. Inventory: `sentry issue list <target> -q 'is:unresolved <filters>' -t <window> -f --json --fields <needed>` → stable scoped IDs.
4. Gather returned-ID evidence: `issue view` + `issue events` → applicable `trace view` + `log list` + `replay view`.
5. Explicit Seer request only → `issue explain|plan` → accept/reject through source/runtime proof.

- Missing identity/target/scope proof → blocker; never switch transport.
- Multiple issues → batch only by verified shared cause; retain evidence/status per ID.
- Failure → bounded stderr + exit → diagnose once with `--help`; no unchanged retry.
- Complete = variants + counterexample + correlation checked, or exact evidence blocker.
