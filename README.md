# hard-eng

<p align="center">
  <img src="assets/readme/hard-eng-hero.png" alt="Hard Eng: plan, build in an implement-verify loop, ship, and learn from evidence" width="100%">
</p>

<p align="center">
  <strong>One stateful engineering workflow for OpenAI Codex.</strong><br>
  Plan with evidence. Build until every gate is green. Ship the proven artifact. Learn only from proven process gaps.
</p>

> [!IMPORTANT]
> **Alpha:** Hard Eng is being rebuilt from scratch. Planning, local build convergence, shipping, and evidence-driven learning are implemented.

## Start here

```text
$he plan <feature>  Plan a material feature or product-behavior change
$he resume          Continue after compaction or in a new task
$he status          Read progress without changing state
$he build           Run the approved Implement ⇄ Verify loop
$he ship            Publish the exact green artifact
$he learn           Process proven learning candidates explicitly
```

Small, clear fixes and read-only questions stay direct. Existing bugs and incidents start with their diagnostic workflow; they enter `$he plan` only when investigation exposes a new product decision.

## The lifecycle

| Owner | What happens | Exit condition |
| --- | --- | --- |
| `he-plan` | Repository evidence → outcomes → flows → UX → contracts → technical design → tests → rollout → slices → approval | No material decision remains unresolved |
| `he-build` | One vertical slice at a time through RED → GREEN → REFACTOR → deterministic checks → review → fix | Every applicable gate passes on one unchanged snapshot |
| `he-ship` | Synchronize → prove artifact identity → commit → push or PR → CI → merge verification | The verified artifact exists at the approved remote target |
| `he-learn` | Observe every stage and promote proven process failures into narrow prevention | Candidate is prevented, rejected with evidence, or remains explicitly open |

`he-build` owns implementation and verification as one loop. `he-learn` is an evidence-driven overlay, not another required lifecycle stage.

## Install

```bash
./setup.sh
./setup.sh check
```

Setup installs pinned tools, the global worktree hook dispatcher, and validates the system. Managed skills stay pinned: setup never invokes `npx skills` or rewrites `.skill-lock.json`.

## Planning without guesswork

Every repository has one root `PRODUCT.md` and `DESIGN.md`. Hard Eng validates both before planning, researches missing facts, then asks only for intent the evidence cannot establish. Non-visual repositories use `DESIGN.md` to record that boundary and its revisit trigger.

Questions arrive in decision-sized stages. A stage advances only after approval or an approved skip. The canonical `PLAN.md` records decisions, blockers, unknowns, slices, evidence, and the exact resume point, so compaction and new tasks never depend on chat memory. Context7 and Codebase Memory are CLI-only; specialists contribute evidence but never own state.

## Safe worktrees and state transfer

Hard Eng continues in an existing linked worktree or a clean primary checkout. A dirty primary moves the task to an isolated worktree. Approved task-owned planning files transfer to a same-HEAD worktree; the destination becomes the sole fresh PLAN owner while unrelated user changes remain untouched.

Repositories declare required ignored environment files in root `.worktreeinclude`, one exact path per line. The global hook copies only those files, never overwrites a destination, and applies owner-only permissions. Dependencies and generated state rebuild through project setup.

Install the machine-level dispatcher once:

```bash
~/.agents/scripts/git-hooks/install.sh install
```

## Build until green

After plan approval, `$he build` resumes the first incomplete vertical slice. Each observable behavior follows TDD and focused deterministic gates. Accepted findings loop through fix and verification; unavailable decisions become explicit PLAN items instead of guesses.

Final convergence covers applicable tests, lint, scanners, code review, security, design, performance, documentation, and runtime evidence. Readiness is visible, but it is not a weighted escape hatch: every applicable axis must pass.

User-visible work proves the full browser or device journey with screenshots, a video for the primary temporal flow, and console, network, and durable-state checks. Non-visual work records equivalent logs, traces, or command evidence.

Automated assertions, persisted state, deployment, and visual artifacts are separate evidence classes. Requested or produced media must be opened and reviewed across its complete timeline; a runner result or artifact manifest cannot substitute for seeing the actual workflow. Each artifact is bound to its digest, revision, environment, run, successful attempt, and viewport before completion can pass.

The last local gate partitions one exact evidence set into bounded review units for ephemeral read-only `gpt-5.6-sol` auditors. Every indexed unit is reviewed exactly once, then validated results are deterministically combined. Each child runs in an empty temporary repository with tools disabled and cannot read the source checkout or controller homes. A unit that times out before producing any review item gets one infrastructure retry; a second stall fails closed. Missing coverage, input overflow, tool use, or current/historical credential exposure also fails closed. Accepted findings return to Implement ⇄ Verify.

Only an unchanged snapshot with readiness 100, current evidence, no open items, and a clean independent audit is ready for `$he ship`. Build never commits, pushes, opens a PR, or waits on CI.

## Ship the proven artifact

`$he ship` synchronizes with repository policy and compares the result with the green build. Drift, conflicts, review findings, or actionable CI failures return to `he-build`. An unchanged artifact passes publish gates, commits without bypassing hooks, proves its remote identity, and follows the approved direct-push or PR path.

## Learn from evidence

Plan, build, and ship create learning candidates only for verified recurrence, user correction, systemic critical gaps, false-pass gates, or repeated waste. `he-learn` prefers a root invariant and regression test, then deterministic gates, then tools, and only then skills or prose. Prevention returns to the current stage for proof; shipping requires zero open candidates.

## Example prompts

```text
$he plan add account recovery with email and passkey paths
$he resume
$he status
$he build
$he ship

Fix the typo in the account menu.                 # small, clear fix → direct
Investigate this failing checkout test.            # failure → diagnose first
Review this branch against its approved PLAN.md.   # review → code-review
```
