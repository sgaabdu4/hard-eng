# Hard Eng for Codex

Hard Eng is one stateful OpenAI Codex workflow for work that must be understood,
built, proved, and shipped without losing its place. It keeps Plan, the
Implement ⇄ Verify Build loop, Ship, and evidence-backed Learn under one
`$hard-eng` entry point. Small, clear work stays direct.

![Hard Eng workflow: he-plan, he-build with an Implement and Verify loop, he-ship, and conditional he-learn](assets/readme/hard-eng-hero.png)

## Pick the smallest route

| Request | Route |
| --- | --- |
| Read-only answer, mechanical edit, or small well-understood fix | Work directly and run proportionate project checks |
| New feature, material behavior, ambiguous product/UI, risky migration, or requested lifecycle | Invoke `$hard-eng` and enter Plan |
| Clear bounded fix that needs tracked proof or shipping | Invoke `$hard-eng`; use Direct Build when its safety contract permits |

Hard Eng never weakens repository rules, security, accessibility, privacy,
migration, or data-loss checks to fit the direct route. If intent or a material
decision is unclear, Codex stops before mutation, shows the uncertainty, asks a
targeted question, and waits.

## The five-minute flow

### 1. Plan until every material decision is resolved

```text
Use $hard-eng to plan and deliver this feature: <objective>.
```

Codex discovers product, user, design, state, data, API, operations, rollout,
risk, proof, and ownership facts before asking only what evidence cannot answer.
The sole visible planning owner is repository-root `plan.md`. It cannot pass
with open readiness items, unmapped source requirements, detached adversarial
findings, missing proof, or an unapproved digest.

For UI work, Plan includes a complete inspectable flow with realistic sanitized
mock data. Existing products reuse their actual tokens and components.
Greenfield or radical visual work may use two or three OpenAI Imagegen direction
boards only after approval of the exact call budget. The selected direction is
translated into code-native tokens and an interactive prototype; generated
pixels never become the component, responsive, interaction, or accessibility
owner. The user approves the direction before Build.

### 2. Build in an Implement ⇄ Verify loop

Each vertical slice cycles through:

```text
expected failure → canonical implementation → focused verification → diff review
                         ↑                         │
                         └──── repair same slice ──┘
```

Codex loads only the accepted slice excerpt, reuses or extends the canonical
owner, and binds red, implementation, verification, and review proof to the same
candidate tree. Verification failure returns directly to implementation inside
Build; there is no separate Verify stage. Before a third unchanged hypothesis,
Codex stops and asks for the missing decision or capability instead of retrying.

User-visible work pauses at the approved review cadence with comparable real-app
screenshots and video when sequence matters. An implementation defect stays in
Build; a changed product, scope, acceptance, or design decision returns to Plan.

### 3. Ship the exact candidate

Ship is deterministic and model-free:

```sh
he check --all --repo .
he ship --repo . --run <run-id> --json
```

The registry inventories project-owned checks, rejects a diff-only proof set,
kills timed-out process groups, confines scanned wrapper owners to the
repository, shadows model CLIs, rejects candidate mutation, and records bounded
digests. Candidate untracked files must be listed
individually with `--allow-untracked <relative-file>`; secrets and unknown paths
fail closed.

User-visible publication waits for approval of the final evidence pack and exact
candidate fingerprint. Publication then binds the commit, tree, first parent,
target ref, remote currentness, exact-SHA CI, actionable review threads, rules
where supported, and rollback target. The user approves the final live
observation before the run becomes Complete.

### 4. Learn only from a proven gap

Learn is a conditional interrupt. It admits a repeated miss, escaped defect,
safety-critical gap, or clearly high-leverage workflow gap only with typed
provenance. It repairs the behavior, reproduces the bad case, and adds the
smallest fail-before/pass-after guard in the existing owner. A tree-changing
guard returns to focused Build verification.

## State, compaction, and resume

State lives outside the working tree in the Git worktree family’s common
metadata. It is bound to one repository, checkout, Codex task, run, and revision.
Ordinary tasks receive no run-specific Hard Eng context. Session-start and
pre-compaction hooks restore only an already-bound run.

Read state without changing it:

```sh
he runs --repo .
he status --repo . --run <run-id>
he doctor --repo .
```

After compaction, the same task resumes its exact phase, cursor, slice, and
revision. In a new task, supply the run ID and ask `$hard-eng` to resume it.
Another task cannot take over silently; takeover requires explicit approval at
the current revision.

## Codebase Memory and Context Mode

Hard Eng uses [Codebase Memory](https://github.com/DeusData/codebase-memory-mcp)
for topology, symbols, callers, dependencies, routes, architecture, and impact.
It uses only the CLI transport—never the Codebase Memory MCP transport:

```sh
codebase-memory-mcp cli list_projects
codebase-memory-mcp cli index_repository '{"repo_path":"<absolute-repository-path>"}'
codebase-memory-mcp cli get_architecture '{"project":"<project-id>"}'
codebase-memory-mcp cli search_graph '{"project":"<project-id>","name_pattern":".*Handler.*","limit":20}'
codebase-memory-mcp cli trace_path '{"project":"<project-id>","function_name":"Handler","direction":"both","depth":3}'
codebase-memory-mcp cli detect_changes '{"project":"<project-id>"}'
```

The runtime observer resolves the exact repository project and executes one
bounded `codebase-memory-mcp cli ...` operation. A health or index operation
alone cannot satisfy Plan or Build; Ship requires fresh `detect_changes`.
Only a recorded CLI failure permits a bounded `rg` fallback.

Hard Eng uses [Context Mode](https://github.com/mksglu/context-mode) for large
logs, command output, documents, diffs, APIs, and datasets. It is an evidence
index/search surface, never a file editor:

```sh
context-mode doctor
context-mode index <path> --source <label> --project <absolute-repository-path>
context-mode search "<query>" --source <label> --project <absolute-repository-path> --limit 10
```

Only bounded receipts and digests enter lifecycle state. Raw outputs, queries,
caches, and session history stay outside the checkpoint.

## Native setup

Requirements: OpenAI Codex, Git, Node.js 22 or newer, macOS or Linux, and the
default `~/.codex` under the selected home. `~/.agents` is the canonical
personal source. Codex discovers skills directly from `~/.agents/skills`;
Hard Eng uses a standalone `hard_eng` MCP state tool and standalone hooks, with
no plugin, marketplace, or Hard Eng-owned `~/.codex/skills/*` symlink.

From the trusted `~/.agents` checkout, inspect without mutation:

```sh
node scripts/setup.mjs doctor
```

Preview installation, inspect every proposed path, then approve the exact
immutable digest:

```sh
node scripts/setup.mjs install --dry-run
node scripts/setup.mjs install --confirm <plan-digest>
```

Updates use the same two-step contract:

```sh
node scripts/setup.mjs update --dry-run
node scripts/setup.mjs update --confirm <plan-digest>
```

Setup is transactional, preserves unrelated Codex configuration, refuses
unknown or modified owned targets, and returns a private hash-verified rollback
bundle after a changed installation. If a killed transaction leaves a journal,
inspect and recover the exact generation:

```sh
node scripts/setup.mjs recover --dry-run
node scripts/setup.mjs recover --confirm <plan-digest>
```

Restore the current installed generation only after a fresh preview:

```sh
node scripts/setup.mjs rollback --backup <rollback-bundle-digest> --dry-run
node scripts/setup.mjs rollback --backup <rollback-bundle-digest> --confirm <plan-digest>
```

Private setup manifests, journals, and rollback bundles live under
`.hard-eng-install/`. Setup reports hashes and relative paths, never backed-up
bytes or secrets.

## Cost guarantees

- Use your cheaper/default model and ordinary reasoning for routine direct
  work. Escalate model capability or reasoning only when the task's semantic
  risk justifies it. Hard Eng never selects, pins, or silently switches a
  model; the choice stays visible and yours.
- One concise `$hard-eng` skill and one small state tool own the lifecycle.
- Hard Eng launches no model eval, subagent, review fleet, Imagegen call,
  daemon, cron job, model switch, or unchanged retry automatically.
- Plan loads once; routine Build loads only the current slice excerpt.
- Checkpoint state stores bounded facts and digests, not transcripts or raw
  output.
- Implement and Verify share one loop; invalidated checks rerun, not the whole
  world.
- Imagegen defaults to zero calls and always needs a user-approved call budget.
- Deterministic gates help weaker models fail safely; they do not fabricate
  missing product judgment or code understanding.

The release-only model eval is excluded from ordinary Plan, Build, Ship, and
Learn. Previewing it makes zero calls and prints the user-selected low/strong
models, purpose, cases, predicted call count, and cap. A run requires the same
explicit cap plus the confirmation flag; it executes sequentially, stops on
the first failure, never retries, and can never exceed four calls:

```sh
node scripts/release-eval.mjs --repo . --low-model <low-model> --strong-model <strong-model> --max-calls 4
node scripts/release-eval.mjs --repo . --low-model <low-model> --strong-model <strong-model> --max-calls 4 --confirm-model-evals
```

## Codex worktrees and ignored local files

Tracked hidden files arrive through Git. Ignored files do not. Inspect required
local inputs with:

```sh
he doctor --worktree --repo .
he doctor --worktree --repo . --worktree-path <exact-relative-path>
```

Codex supports [`.worktreeinclude`](https://learn.chatgpt.com/docs/environments/git-worktrees).
Hard Eng accepts only exact repository-relative ignored paths so a pattern
cannot expand into credentials or caches. Codex copies approved entries when it
creates the worktree; Hard Eng validates the source and does not implement a
second copier.

Broad globs, home paths, `.git`, `.codex`, dependency/build/cache folders,
symlinks, sockets, and missing or tracked paths fail. A hidden ignored directory
is allowed, but a nested secret must be named exactly. Every `.env`, key, or
credential-like path needs explicit approval.

## Troubleshooting

- `he doctor --repo .` reports run permissions, pending actions, and locks
  without repairing or deleting them.
- `node scripts/setup.mjs doctor` reports native skill, launcher, standalone
  hook/MCP, Codebase Memory CLI, and Context Mode health without exposing
  configuration contents.
- Plan or candidate drift returns to reconciliation; never edit fingerprints or
  state by hand.
- A pending external action must be observed and reconciled once before retry.
- A stale lock is reported with its identity; deletion needs scoped approval.
- On Codebase Memory failure, diagnose or index once before bounded text search.
  On Context Mode failure, run `context-mode doctor` once before fallback.

## Uninstall

Preview removal, inspect the exact digest, then authorize it:

```sh
node scripts/setup.mjs uninstall --dry-run
node scripts/setup.mjs uninstall --confirm <plan-digest>
```

Uninstall removes only manifest-owned files and refuses modified or unknown
targets. Run state remains preserved. State deletion is a separate destructive
operation with one exact root and a fresh confirmation:

```sh
node scripts/setup.mjs purge-state --state-root <exact-state-root> --dry-run
node scripts/setup.mjs purge-state --state-root <exact-state-root> --confirm <plan-digest>
```

## Development

```sh
npm test
node runtime/he.mjs check --all
```

CI invokes the same registry. The runtime has no production npm dependencies.
Third-party notices are in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md). Hard Eng is licensed under
[`MIT`](LICENSE).
