# Retry Readiness

## Entry

- Use before first paid/native/external attempt when behavior depends on an external/runtime/platform contract.
- Use after every contract-surprise, native-runner, release, or paid-pipeline failure.
- Product repository owns probes + receipts; this reference owns admission.

## Flow

1. Bind failure = exact revision + environment + job/step/phase + observed red output + first bad boundary + original observable violation.
2. `diagnosing-bugs` PASS = canonical owner + mechanism + blast radius + preserved red-capable reproduction.
3. `research` PASS for every external/runtime/platform assumption = primary URL/version/date + resolved local version/tool/path/runner.
4. Audit adjacent assumptions = syntax + cardinality + quoting + paths + waits + job boundaries + platform + version + state; each gets `PASS | N/A | BLOCKED` + proof.
5. Run cheapest compatible real-tool parse/compile/execute sentinel; validation-only target-native lane when local parity is impossible.
6. Parallelize independent cheap checks; prerequisite red cancels dependent setup/build/publish work.
7. Failure ends actor + retry approval; recheck the original observable violation + record failed approach fingerprint = mechanism + dependency/tool + mode/target; same approach/variant is forbidden.
8. Further paid/native/external attempt = fresh explicit user approval + materially changed proven mechanism + steps 1–6 `PASS`.

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
| Retry | Fresh approval + exact revision + mode + target + actor |

## Stop

- Static/grep/substring/AST intent check ≠ interpreter/compiler/runner semantic proof.
- Missing primary contract or compatible sentinel → `FAIL`; expensive/full/publisher retry forbidden.
- Missing fresh approval after a failed paid/native/external attempt → `FAIL`; continuity or prior approval cannot substitute.
- Changed cause, target, mode, revision, or environment → stale receipt.
