# Diagnose

1. Inventory every reporter-provided failure + constraint + example + rejected remedy; later guidance supersedes only exact conflicts.
2. Establish expected vs actual behavior + first known bad boundary + environment/revision + resolved OS/shell/interpreter/compiler/tool/version/path + available logs/tests/runtime access.
3. Reproduce with proof capable of red; record exact command/path/input/output. Reporter-provided examples = immutable reproduction inventory; simplified fixture requires proven equivalence for every distinguishing condition. Flake → preserve seed/timing/frequency and repeated-run sample.
4. Minimize input + state + components + timing while the same failure remains red.
5. Track only evidence-supported hypotheses as `claim → prediction → discriminating check → result`; run the cheapest high-signal check; retain rejected counterevidence.
6. Instrument the narrowest boundary with existing debugger/log/test hooks. Source instrumentation needs explicit edit authority; redact secrets/PII and remove temporary instrumentation before return.
7. Trace decisive evidence to the canonical owner + direct callers + connected data/contracts/tests/config/runtime surfaces.
8. Prove mechanism: owner state explains observation + controlled change/perturbation changes the reproduced result + credible alternatives are rejected or bounded.
9. Classify every solution-driving assumption: repository-owned fact → local proof; external/runtime/platform contract → `research` before fix selection.
10. Close every diagnosis-ledger item by proof, explicit supersession, `N/A`, or exact blocker; omission = incomplete.

## Stop

- Reproduction unavailable → return attempted proof + environment variance + missing access/input + next reproducer.
- Required runtime/data access unavailable → return exact authority/tool/evidence needed.
- Red-capable proof cannot be built → `CONCERNS`; never infer root cause from a green-only check.
- Source text/grep/substring/static intent = wiring evidence only; interpreter/compiler/runner behavior requires execution at the compatible seam.
- Completion = proven mechanism or explicit blocker; plausible hypothesis alone = incomplete.
