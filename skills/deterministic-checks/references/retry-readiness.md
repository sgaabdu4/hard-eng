# Retry Readiness

## Entry

- Use before first paid or state-changing external/native attempt when behavior depends on an external/runtime/platform contract.
- Use after every state-changing contract-surprise, native-runner, release, or paid-pipeline failure.
- Read-only access + safe read retry = autonomous; use this full flow only when the read failure exposes material contract/security uncertainty.
- Product repository owns probes + receipts; this reference owns admission.

## Flow

1. Bind failure = exact revision + environment + job/step/phase + observed red output + first bad boundary + original observable violation.
2. `diagnosing-bugs` PASS = canonical owner + mechanism + blast radius + preserved red-capable reproduction.
3. `research` PASS for every external/runtime/platform assumption = primary URL/version/date + resolved local version/tool/path/runner.
4. Audit adjacent assumptions = syntax + cardinality + quoting + paths + waits + job boundaries + platform + version + state; each gets `PASS | N/A | BLOCKED` + proof.
5. Run cheapest compatible real-tool parse/compile/execute sentinel; validation-only target-native lane when local parity is impossible.
6. Parallelize independent cheap checks; prerequisite red cancels dependent setup/build/publish work.
7. Failure ends actor + any protected-retry authorization; recheck the original observable violation + record failed approach fingerprint = mechanism + dependency/tool + mode/target; same approach/variant is forbidden.
8. Further recoverable state-changing OR paid attempt = materially changed proven mechanism + steps 1–6 `PASS` → continue automatically; retry causing irreversible destructive loss or machine-scope write = fresh exact user approval.
9. Read-only failure = choose a changed safe mechanism + retry automatically; full steps 1–6 apply only for material contract/security uncertainty.

## Receipt

| Field | Required |
|---|---|
| Failure | Revision + environment + boundary + red evidence |
| Cause | Owner + mechanism + blast radius |
| Research | Primary sources + resolved integration |
| Adjacent | Assumption matrix + verdict/proof |
| Sentinel | Compatible tool/runner + bounded command + exit/receipt |
| Violation | Original observable check + current red/green result |
| Approach | Failed fingerprint + materially changed mechanism |
| Retry | Read-only = authorization `n/a`; recoverable/paid = changed mechanism + exact revision + mode + target + actor; irreversible destructive/machine-scope = fresh exact approval |

## Stop

- Static/grep/substring/AST intent check ≠ interpreter/compiler/runner semantic proof.
- Missing primary contract or compatible sentinel → `FAIL`; expensive/full/publisher retry forbidden.
- Missing fresh exact approval for a retry causing irreversible destructive loss or machine-scope write → `FAIL`; continuity or prior approval cannot substitute; recoverable/paid retry with steps 1–6 `PASS` + read-only access/retry = no approval.
- Changed cause, target, mode, revision, or environment → stale receipt.
