# Structural Design

1. Prove accepted behavior + current owner/public surface + direct callers/dependencies through Codebase Memory CLI and native source.
2. List leaked caller knowledge: validation + policy + ordering + fallback + flags + storage/data shape + errors + performance.
3. Choose smallest complete move: delete concept + consolidate owner + deepen interface; new seam only for current variation.
4. Define proposed contract: entry points + inputs/outputs + invariants + errors + ordering + side effects + dependency direction.
5. Trace replacement through callers + packages + schema/data + keys/cache + routes + tests/fixtures + docs/config.
6. Use `$test-quality` → public-surface proof that survives internal refactor; retain old proof until replacement sensitivity is shown.
7. Report current leak + proposed owner/contract + concepts deleted + migration/blast radius + proof + unresolved decision.

- External dependency → explicit boundary; test adapter/mock may justify a seam when production + test are real variants.
- Internal test convenience alone ≠ public seam.
- Material behavior/architecture choice not accepted → return to `$he` before mutation.
