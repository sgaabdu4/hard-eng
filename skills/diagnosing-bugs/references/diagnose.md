# Diagnose

1. Establish expected vs actual behavior + first known bad boundary + environment/revision + available logs/tests/runtime access.
2. Reproduce with proof capable of red; record exact command/path/input/output. Flake → preserve seed/timing/frequency and repeated-run sample.
3. Minimize input + state + components + timing while the same failure remains red.
4. Track only evidence-supported hypotheses as `claim → prediction → discriminating check → result`; run the cheapest high-signal check; retain rejected counterevidence.
5. Instrument the narrowest boundary with existing debugger/log/test hooks. Source instrumentation needs explicit edit authority; redact secrets/PII and remove temporary instrumentation before return.
6. Trace decisive evidence to the canonical owner + direct callers + connected data/contracts/tests/config/runtime surfaces.
7. Prove mechanism: owner state explains observation + controlled change/perturbation changes the reproduced result + credible alternatives are rejected or bounded.

## Stop

- Reproduction unavailable → return attempted proof + environment variance + missing access/input + next reproducer.
- Required runtime/data access unavailable → return exact authority/tool/evidence needed.
- Red-capable proof cannot be built → `CONCERNS`; never infer root cause from a green-only check.
- Completion = proven mechanism or explicit blocker; plausible hypothesis alone = incomplete.
