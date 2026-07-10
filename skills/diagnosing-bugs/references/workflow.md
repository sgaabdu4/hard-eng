# Bug Diagnosis Workflow

Start from the evidence source the user named: Sentry, logs, CI output, a
stack trace, a failing UI flow, or a local command. If no source is named,
choose the shortest user-like reproduction path.

## Phase 1: Build A Tight Loop

This is the core of the skill. Build a pass/fail signal that can go red on the
exact user-described bug and green after the fix.

Try loop shapes in this order:

1. Failing test at the seam that reaches the bug
2. HTTP request or curl script against a running service
3. CLI command with fixture input and expected output
4. Headless browser script with DOM, console, or network assertions
5. Captured trace replayed through the code path
6. Throwaway harness around the smallest runnable subsystem
7. Property, fuzz, stress, or repeated loop for non-deterministic bugs
8. Bisection or differential loop across commits, configs, or versions
9. Human-in-the-loop script based on `scripts/hitl-loop.template.sh`

Tighten the loop before moving on:

- Make it faster by narrowing setup and skipping unrelated init
- Make it sharper by asserting the exact symptom
- Make it deterministic by pinning time, seeds, filesystem, and network
- For flaky bugs, raise reproduction rate until the loop is useful

Completion criterion: one agent-runnable command has already been run, drives
the real bug path, asserts the exact symptom, and produces a stable verdict.
If that command cannot be built, stop and ask for the missing artifact or
access instead of guessing.

## Phase 2: Reproduce And Minimise

Run the loop and prove it fails for the same reason the user reported. Capture
the exact symptom: error, wrong output, missing UI state, timing, or log.

Then minimise the failing case. Remove inputs, callers, config, data, and steps
one at a time, rerunning the loop after each cut. Done means every remaining
element is load-bearing: removing any one makes the loop go green.

Wrong failure means wrong fix.

## Phase 3: Rank Hypotheses

Write three to five ranked hypotheses before testing any one of them. Each
hypothesis must be falsifiable:

`If <cause> is true, then <probe/change> will produce <observable result>.`

Show the ranked list to the user when useful, especially if domain context can
re-rank it quickly. Do not block if the user is away and the evidence is enough
to proceed.

## Phase 4: Instrument Narrowly

Probe one prediction at a time. Prefer debugger or REPL inspection when
available. Otherwise add targeted logs or assertions at boundaries that
distinguish hypotheses.

Rules:

- Tag temporary logs with a unique prefix such as `[DEBUG-a4f2]`
- Never log everything and grep later
- For performance regressions, establish a baseline measurement before fixing
- Use query plans, profilers, timings, or bisection instead of noisy logs

## Phase 5: Fix And Prove

Fix the canonical owner of the broken behavior, contract, state machine,
mapping, schema, route, or boundary. Avoid caller-by-caller patches when one
owner should enforce the rule.

Turn the minimised repro into a regression test before the fix when a correct
seam exists. The correct seam exercises the real bug pattern as it occurs at
the call site. If no correct seam exists, document that architecture gap and
use the best available outer loop as proof.

Proof order:

1. Watch the regression test fail or document why no correct seam exists
2. Apply the fix
3. Watch the regression test pass
4. Rerun the original Phase 1 loop against the unminimised scenario

## Phase 6: Cleanup And Learn

Before declaring done:

- Original repro no longer reproduces
- Regression test passes, or the missing seam is documented
- All `[DEBUG-...]` instrumentation is removed
- Throwaway harnesses are deleted or moved to a clearly marked debug location
- The correct hypothesis and root cause are stated in the report

Then ask what would have prevented the bug. If the answer is architecture,
seams, ownership, or testability, hand off to `codebase-design` with the
specific evidence gathered during the fix.

## Stop Conditions

- A red-capable loop cannot be built with available tools
- The evidence points outside the repo or to data the user has not approved
  changing
- The requested change would weaken security, data loss, validation, or
  accessibility boundaries

Stop with the evidence gathered and the smallest next question.
