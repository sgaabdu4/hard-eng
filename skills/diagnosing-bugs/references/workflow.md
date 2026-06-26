# Bug Diagnosis Workflow

Start from the evidence source the user asked for: Sentry, logs, a pasted stack,
CI output, a failing UI flow, or a local command.
If no source is named, choose the shortest user-like reproduction path.

## Diagnosis Loop

1. Build a tight feedback loop.
   Prefer a failing test, focused script, HTTP request, CLI fixture, or local UI
   path that reproduces the exact symptom.
   The loop should run unattended and in seconds when practical.

2. Reproduce and minimise.
   Prove the failure matches the user report, then remove unrelated setup until
   the smallest still-failing case remains.
   Wrong failure means wrong fix.

3. State competing hypotheses.
   Write the likely causes in plain language.
   Tie each hypothesis to one observable fact that would confirm or rule it out.

4. Instrument narrowly.
   Add temporary logs, probes, assertions, query inspection, or debugger checks
   only where they distinguish hypotheses.
   Do not leave noisy instrumentation behind.

5. Fix the root owner.
   Change the canonical owner of the broken behavior, contract, state machine,
   schema mapping, or boundary.
   Avoid caller-by-caller patches when one owner should enforce the rule.

6. Add the regression proof.
   Keep or add the smallest durable test that fails before the fix and passes
   after it.
   For flaky bugs, prove the failure rate drops with repeated runs or a
   deterministic control.

7. Clean up and report.
   Remove temporary probes.
   Report the symptom, root cause, evidence, fix, and verification command.

## Stop Conditions

- The reproduction cannot be built with available tools
- The evidence points outside the repo or to data the user has not approved
  changing.
- The requested change would weaken security, data loss, validation, or
  accessibility boundaries.

In those cases, stop with the evidence gathered and the smallest next question.
