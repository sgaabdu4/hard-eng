# Test Design + Review

## Route

1. Read behavior sources + changed owner/callers + existing tests; state exact risk to prove.
2. Build scenario matrix: happy + boundaries + invalid/empty/null + permission + failure/recovery + concurrency/time/state transitions as applicable.
3. Choose narrowest public seam that observes behavior without internal implementation access.
4. Arrange minimal realistic data; keep owned collaborators real; isolate only external I/O/system boundaries when slow/nondeterministic/destructive/unavailable.
5. Act through public API/UI/system event; assert user-visible result, public return/state, emitted contract, or durable side effect.
6. Prove sensitivity: absent/broken target behavior → new/changed test fails for intended reason; restore behavior → focused proof passes.
7. Ask `$deterministic-checks` for applicable execution evidence; interpret failures without weakening assertions or suppressing gates.
8. For high-risk logic, mutate meaningful conditions/boundaries/results; fix surviving behavior gaps, classify equivalent/invalid cases with evidence.
9. Review suite → delete duplicate/implementation-coupled tests; retain smallest set proving distinct risks.

## Quality Review

| Check | Reject when |
|---|---|
| Behavior | Assertion describes internal method/state/component shape. |
| Sensitivity | Test passes with target behavior absent/broken. |
| Seam | Lower-level seam misses material integration; broader seam adds no confidence. |
| Doubles | Owned business collaborator mocked; mock expectation becomes implementation assertion. |
| Data | Fixture hides relevant state or permits impossible input. |
| Assertion | Merely `exists`, snapshot churn, broad count/status, or unrelated side effect. |
| Isolation | Order/time/network/global state can leak between cases. |
| Diagnostics | Failure cannot identify violated behavior. |

## Evidence

- Record behavior IDs + test paths + focused pass/fail result supplied by `$deterministic-checks`.
- Red proof = exact expected failure + reason; setup/compile/fixture failure ≠ valid red.
- Mutation proof = targeted owner + killed/survived/no-coverage disposition; score alone = insufficient.
