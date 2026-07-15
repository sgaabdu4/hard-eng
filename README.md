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

Direct work is the default. A clear, bounded UI tweak, fix, refactor, test, documentation edit, or configuration change uses the relevant specialist, checks worktree readiness, edits the canonical owner, runs focused gates, and captures browser/device proof when the result is visible. It does not create a PLAN or repair `PRODUCT.md`/`DESIGN.md` merely to begin.

Hard Eng starts only when you invoke it or when a material new capability needs unresolved product, UX, architecture, testing, and rollout decisions to persist across stages. Calling something a “feature,” touching several files, or finding old context documents does not make it Hard Eng work.

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

Questions appear only for material decisions evidence cannot resolve. Resolved or irrelevant stages checkpoint and continue automatically; only real decisions, external boundaries, and final full-plan approval pause. Findings with an accepted outcome stay in the build loop, while changed intent reopens only affected planning and automatically revalidates unchanged downstream proof. The canonical `PLAN.md` records decisions, blockers, unknowns, slices, evidence, and the exact resume point, so compaction and new tasks never depend on chat memory. Context7 and Codebase Memory are CLI-only; specialists contribute evidence but never own state.

## Safe worktrees and state transfer

Hard Eng continues in the checkout you selected. An existing linked worktree or branch continues as-is, and a clean primary/main checkout may be used directly. A dirty primary with unrelated changes asks once whether to continue there or create a worktree; Hard Eng never creates or moves to one automatically. When you select a different checkout, approved task-owned planning files transfer to the same-HEAD destination in either direction while unrelated user changes remain untouched.

This Hard Eng source repository is the explicit exception: its local policy is primary-only, so it always continues in the primary checkout and never offers, creates, or uses a worktree.

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

The last local gate gives one complete bounded evidence packet to one ephemeral read-only `gpt-5.6-sol` auditor. The child runs in an empty temporary repository with tools disabled and cannot read the source checkout or controller homes. A timeout before any review item gets one infrastructure retry; a second stall fails closed. Missing coverage, packet overflow, tool use, or current/historical credential exposure also fails closed. Accepted findings return to Implement ⇄ Verify.

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
Make the existing dashboard cards equal height.   # bounded UI change → direct + focused visual proof
Investigate this failing checkout test.            # failure → diagnose first
Review this branch against its approved PLAN.md.   # review → code-review
```
