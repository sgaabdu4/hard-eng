# TDD

## Entry

- Use only when TDD/red-green-refactor explicitly requested.
- Unit of progress = one observable behavior at one public seam.
- Scenario order = simplest meaningful outcome → boundaries/failures → integration risks.

## Loop

1. Specify one behavior: precondition + action + observable result; choose narrowest meaningful seam.
2. **RED** → write one behavior test; `$deterministic-checks` supplies focused execution; require failure for missing/wrong behavior.
3. **GREEN** → implement minimum complete behavior; focused test + affected existing tests pass.
4. **REFACTOR** → remove duplication/clarify ownership without changing behavior; same proofs remain green.
5. Recompute scenario inventory → repeat only for next uncovered behavior.
6. High-risk logic or explicit mutation request → targeted mutation review; kill meaningful survivors or record evidence-backed disposition.

## Stops

- Test cannot fail meaningfully → redesign assertion/seam before production code.
- Red from setup/type/fixture/environment defect → fix harness; rerun RED.
- Required behavior changes during loop → update accepted contract before continuing.
- Do not add speculative production generality, broad fixtures, internal mocks, or assertions merely to kill a mutant.

## Complete

- RED + GREEN evidence exists per behavior increment.
- Refactor preserves public behavior + affected proofs.
- Scenario inventory + applicable mutation disposition or `N/A` satisfy `SKILL.md` completion.
