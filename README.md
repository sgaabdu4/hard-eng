<p align="center">
  <img src="assets/readme/hard-eng-hero.png" alt="Hard Eng: plan with one Feature Brief, build in an implement-verify loop, ship, and learn from evidence" width="100%">
</p>

<p align="center">
  <strong>Fast, evidence-backed engineering for OpenAI Codex and Claude Code.</strong><br>
  Align once. Build in verified vertical slices. Put extra scrutiny only where the risk is.
</p>

<p align="center">
  <a href="#what-you-get">What you get</a> ·
  <a href="#start-here">Start here</a> ·
  <a href="#route-matrix">Routes</a> ·
  <a href="#the-fast-feature-loop">Feature Loop</a> ·
  <a href="#install">Install</a>
</p>

> [!IMPORTANT]
> **Alpha:** Hard Eng is evolving quickly. Its contract is stable on the essentials: explicit intent, root-cause fixes, deterministic proof, and protected approval boundaries.

## What you get

One canonical repository, wired natively into both agents. No copied files, no plugin packaging, nothing to keep in sync.

| Piece | What it is |
| --- | --- |
| `AGENTS.md` | One behavior contract, loaded by Codex and Claude Code in every session |
| `skills/` | Focused skills: lifecycle (`he`, `he-plan`, `he-build`, `he-ship`, `he-learn`), evidence (`question-me`, `research`, `diagnosing-bugs`, `e2e`), review (`code-review`, `security-review`, `test-quality`), and more |
| Deterministic gates | Contract tests, design checks, and managed-skill verification — enforced by Git hooks at commit and push |
| Native wiring | A `~/.codex/AGENTS.md` symlink and `~/.claude/CLAUDE.md` import stub; both agents read skills straight from `~/.agents/skills` |

## Start here

Most work needs no command. Give the agent a clear outcome and it chooses the lightest safe route. Skills activate on their own: Codex resolves `$skill-name` mentions and matches skill descriptions; Claude Code triggers skills from their descriptions automatically.

```text
he plan <feature>  Create a lean Feature Brief and reach Ready-to-build
he resume          Continue from the accepted brief or next slice
he status          Read progress without changing state
he build           Implement and verify the approved slices
he ship            Deliver the exact green artifact
he learn           Process an evidence-backed workflow improvement
```

## Route matrix

| Route | Use it when | What happens |
| --- | --- | --- |
| Direct | The outcome is bounded and clear | Inspect, edit the canonical owner, run focused gates, report |
| Feature Loop | A new or changed capability needs product alignment | One lean Feature Brief, one Ready-to-build approval, then verified vertical slices |
| Diagnose-first | A bug, flake, failure, or regression exists | Reproduce, find root cause and blast radius, then fix and prove |
| Critical overlay | A slice touches payment, auth, security, privacy, destructive data, irreversible behavior, or material uncertainty | Strengthen the contract, evidence, and independent review for that slice only |

Calling work a “feature,” touching many files, or finding an old context document does not automatically add process. Direct is the default. The Feature Loop exists when an observable capability needs alignment; the Critical overlay follows risk instead of making an entire project heavy.

## The Fast Feature Loop

### 1. Align once

Hard Eng reads the repository, researches current external facts when needed, and creates one lean, living Feature Brief:

- **Outcome**
- **Non-goals**
- **Material decisions**
- **Acceptance examples**
- **Affected canonical areas**
- **Risk and rollback**
- **First vertical slice**

Questions are asked one at a time. Once the brief contains no unresolved material choice, the agent asks for one Ready-to-build approval. That approval covers the accepted feature outcome—not destructive actions, external writes, commits, pushes, merges, or publication.

There is no arbitrary limit on material questions. Before each one, the agent researches the available evidence, answers discoverable facts itself, and asks only the next material desired-state decision. Each answer determines the next relevant question; already-settled answers and prewritten questionnaires are not repeated.

Ready-to-build still takes one reply. The agent emits a short fingerprint-bound reply after showing the complete brief, and the user echoes it once. A decision answer or generic acknowledgement cannot be reused as build approval, and changing the accepted outcome rotates the reply.

The brief has six plain states: `planning`, `build-ready`, `building`, `green`, `shipped`, and `cancelled`.

### 2. Build in working slices

Each slice delivers observable behavior through an Implement ⇄ Verify loop. Tests and deterministic checks run near the change, so feedback comes from working code early instead of from a large speculative plan.

Discovering another caller, file, owner, schema, route, test, or configuration is normal engineering evidence. The agent updates the implementation and affected proof without reopening the brief. Replanning happens only when evidence changes the accepted outcome or the material risk contract.

### 3. Review what actually changed

Review is anchored to the actual diff, affected behavior, blast radius, and risk-targeted evidence. Standard work gets focused owner review. A critical slice adds the relevant specialist and independent review when its risk requires it, while unrelated safe slices retain the standard flow.

Findings return to Implement ⇄ Verify. An implementation defect is fixed and re-proved; a genuine outcome or risk-contract discovery reopens only the smallest affected part of the brief.

### 4. Ship the proven artifact

Shipping verifies the working artifact before delivery and verifies that committed `HEAD` still matches it after hooks, then runs publish gates and crosses only the Git or deployment boundary the user explicitly approved. Build does not silently commit, push, open a pull request, merge, publish, or perform another external write.

## The question contract

The agent asks only when the answer materially changes:

- product outcome or user-visible behavior;
- UX choice;
- policy or default;
- security or privacy;
- data-loss exposure;
- an irreversible decision;
- one-off/local versus repository/deployed delivery when that changes the observable operation, durable ownership, or risk.

Reversible engineering details belong to the agent. It chooses from repository evidence, keeps the design simple, and verifies the result. A new file or test is not a reason to ask permission again.

If a correction changes the accepted outcome or risk contract, the agent shows the exact delta and asks for confirmation. Clear bounded corrections continue immediately.

## Quality safeguards

Speed comes from removing duplicated ceremony, not from weakening engineering:

- KISS, YAGNI, DRY, and one source of truth remain mandatory.
- Bugs are diagnosed before they are patched.
- Regression fixes rerun the original reported examples at the boundary where users observed them, including the packaged or released artifact when applicable.
- Correctness covers the root cause and blast radius, including connected callers, schemas, keys, routes, tests, docs, configuration, and live wiring.
- Security, trust, privacy, accessibility, schema, and data-loss protections are preserved.
- Replacements leave one canonical path and remove superseded aliases, compatibility paths, and dual routing.
- Deterministic project gates run before model judgment.
- A green checkpoint binds the exact non-PLAN repository artifact; any later drift returns to the build loop before shipping.
- User-visible behavior receives browser or device evidence; non-visual work receives equivalent command, log, trace, or state evidence.
- Destructive actions, external writes, commits, pushes, merges, and publication retain exact approval boundaries.

One exact external approval may cover a named resource, a bounded action set, and explicit exclusions. Routine clicks and unchanged retries inside that scope do not trigger another approval; a changed target, effect, artifact, or destructive boundary does.

No workflow can promise literally zero regressions. Hard Eng aims for lower regression risk through smaller feedback loops, focused proof, and review proportional to the actual risk.

## Context and continuity

The Feature Brief owns accepted intent; slice checkpoints own implementation state and evidence. The agent can reset context after alignment or between slices, and `he resume` restores the accepted brief, current slice, open evidence, and next action from repository state rather than chat memory.

Exploration is disposable; decisions and proof receipts are durable. Progress updates report material state changes, blockers, approval boundaries, and proof. Routine tool narration and unchanged polling are omitted. Unrelated work starts a fresh task after a long delivery so old context, plans, and approvals cannot leak into it.

Terminal Feature Briefs never block new work. If they become clutter, the agent can remove only the exact terminal PLAN paths the user approves after showing their states and hashes; active or unverified plans are never swept away.

## Learning without blocking delivery

Hard Eng records proven process gaps when evidence shows recurrence, a false-pass gate, a systemic critical gap, or repeated waste. Product delivery continues while the improvement is investigated unless continuing would risk security, privacy, accessibility, data integrity, or another protected boundary. Learning never silently spawns background work, and prevention prefers a root invariant and regression test, then a deterministic gate or tool, and only then more prose.

## Measuring whether it is better

Compare similar completed tasks and track:

| Signal | Desired |
| --- | --- |
| Time from request to first verified slice | Down |
| Tokens spent before working-code evidence | Down |
| Ready-to-build approval rounds before standard build | One |
| Material question cadence | One useful, evidence-backed question per turn |
| Replans caused by file/owner/test discovery | Zero |
| Escaped defects in changed behavior | Down |

Metrics are evidence, not quotas. They must never reward skipping a protected check or hiding a defect.

## Instruction ownership

`AGENTS.md` contains only behavior that should apply unchanged across unrelated repositories. Hard Eng repository facts, maintenance rules, and delivery policy belong in `AGENTS.override.md`. A repository-specific rule must not be promoted into the global file merely because it sounds like a general engineering principle.

## Worktrees and local state

Hard Eng continues in the checkout you selected. An existing branch or linked worktree continues as-is; a clean primary checkout can be used directly. If the primary checkout contains unrelated work, the agent asks once whether to stay or create a worktree. It never moves work automatically.

This repository is intentionally primary-only. Other repositories can declare required ignored local inputs in `.worktreeinclude`; only those narrow paths transfer, while dependencies and generated state rebuild through setup.

## Install

Requirements: macOS or Linux on ARM64/x86-64, Zsh, Bash, or Fish, Node.js 22.5+, npm, Git, Python 3, Codex and/or Claude Code, curl, and tar.

```bash
./setup.sh install
./setup.sh check
```

`install` converges the pinned npm runtime and binaries, the pinned Context Mode plugin for Codex and Claude Code, the canonical `~/.codex/AGENTS.md` symlink, the `~/.claude/CLAUDE.md` import stub and `~/.claude/skills` symlink, the global Git-hook dispatcher, and one managed shell PATH block. In this repository the dispatcher also enforces the publish gates: managed-skill and design checks at every commit, the full contract suite at every push. RTK is installed only as the official pinned binary; setup does not add an RTK plugin, hook, or generated `RTK.md`.

Verified matching state is kept. Hard Eng-owned outdated state is replaced transactionally; unrelated files, commands, plugins, hooks, and shell content are preserved. A conflicting user-owned target stops setup instead of being overwritten. Authentication and credentials are not provisioned. To remove the Git hooks, run `scripts/git-hooks/install.sh uninstall`; the remaining wiring is plain symlinks and stub files you can delete at any time.

`check` verifies installed and repository state without changing home, profile, Codex, Claude Code, Git, cache, or repository state. Its reconstruction and tool probes use disposable system scratch space.

Pin updates are explicit:

```bash
./setup.sh update /tmp/reviewed-setup-manifest.json
git diff -- scripts/setup/manifest.json runtime/npm/package.json runtime/npm/package-lock.json
./setup.sh check
```

`update` requires a clean repository and a complete reviewed manifest. It verifies npm tarballs, the Context Mode tag commit, every platform binary checksum, and the regenerated lock before transactionally replacing the three canonical pin files. Failure restores their exact prior bytes and modes. It never resolves “latest,” commits, or pushes.

Managed skills stay pinned and are not rewritten during routine setup. The aggregate repository gate validates the actual PRODUCT/DESIGN owners, every skill package and local Codex metadata file, lifecycle contracts, and the complete tracked Appwrite regression suite. Scheduled managed-skill updates run the same publish gates before committing or pushing.

## Examples

```text
Add account recovery with email and passkey paths.  # Feature Loop
Fix the typo in the account menu.                   # Direct
Make existing dashboard cards equal height.        # Direct + visual proof
Investigate this failing checkout test.             # Diagnose-first
Add passkey recovery to the approved feature.       # Show outcome delta, then confirm
he resume                                           # Continue accepted state
he ship                                             # Request exact delivery approvals
```

<p align="center">
  MIT licensed · humans read <a href="README.md">README.md</a>, agents read <a href="AGENTS.md">AGENTS.md</a>
</p>
