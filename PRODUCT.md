# Hard Eng Product

## Purpose

Hard Eng is the user's canonical personal engineering system for OpenAI Codex.
Its source is `$HOME/.agents`. Codex discovers its native skills directly from
`$HOME/.agents/skills`. Standalone hooks and the `hard_eng` state MCP connect
that source to Codex.

Hard Eng makes serious feature and shipping work understandable, resumable,
evidence-backed, and deterministic without automatically spending additional
model calls.

## Users and scope

The primary user is an engineer using Codex on macOS or Linux across unrelated
repositories. Project-local `AGENTS.md`, product/design owners, code, tests, and
CI remain authoritative for each repository.

Hard Eng targets OpenAI Codex.

## Lifecycle

The lifecycle is:

`Plan → Build (Implement ↔ Verify) → Ship → Complete`

Learn is a conditional evidence-backed interrupt that creates a durable guard
and returns to its recorded Build or Ship boundary. It is not an automatic
post-task stage.

- New features, material behavior, ambiguous product/UI decisions, and explicit
  lifecycle requests enter `$hard-eng` Plan.
- Small clear fixes, mechanical edits, explanations, and read-only audits may
  remain direct.
- Plan asks only questions that repository evidence cannot answer safely. It
  resolves the product, design, data, API, ownership, operations, rollout, and
  proof contract, performs one A1–A8 adversarial pass, and requires approval of
  the exact repository-root `plan.md` digest.
- UI Plan provides a complete inspectable coded flow with realistic sanitized
  mock data and key states. Optional Imagegen direction boards require explicit
  call-budget approval and never replace coded interaction/accessibility proof.
- Build implements one vertical slice through its canonical owner and verifies
  that same slice before it can advance. Failed proof returns to the slice.
- Ship is deterministic and model-free: intent, candidate identity, secrets,
  generated/destructive safety, repository-confined checks with fail-fast model
  CLI guards, risk proof, docs/config, publication, CI, rollback, and
  currentness.

## Continuity

Machine continuity lives outside the working tree under
`$GIT_COMMON_DIR/common/hard-eng/v1`. Checkpoints are compact canonical JSON and
render only a bounded Markdown capsule to the model.

Bindings are HMAC-scoped to the exact repository, task, turn, tool call, and
revision. Same-task compaction/resume restores the exact cursor. A fresh task
must explicitly resume a run. An unrelated task in the same checkout receives
zero run context and cannot mutate the run.

Material uncertainty enters `await-user-clarification`, performs no candidate
mutation, and returns only to the recorded boundary after an explicit answer.

## Native source surface

The canonical source owns:

- complete global enforcement in `AGENTS.md`;
- product and design truth in `PRODUCT.md` and `DESIGN.md`;
- one native `$hard-eng` entry skill plus retained specialist skills;
- seven exact-pinned upstream skill submodules;
- focused runtime, hook, MCP, setup, and deterministic test owners;
- one `tests/` root and one repository-root feature `plan.md` when Plan is used.

These are the complete lifecycle and delivery owners. Specialist skills remain
direct native capabilities; setup preserves one source path and one wiring
owner per surface.

## Upstream sources

The approved pinned upstream repositories are:

- `building-flutter-apps`
- `appwrite-backend`
- `fallow-skills`
- `react-doctor`
- `vercel-agent-skills`
- `sentry-for-ai`
- `sentry-cli`

Pins never update automatically. Local skills either use a validated relative
link or a small adapter that points to the exact upstream owner without copying
its workflow.

## Cost contract

Ordinary operation, setup, Plan, Build, Ship, and Learn launch zero automatic
model evals, subagents, Imagegen calls, semantic review fleets, or model
switches. Hard Eng never changes the user's model, reasoning effort, service
tier, agent-thread limit, or review model.

Codebase Memory is mandatory for applicable topology/impact work and Context
Mode for applicable large evidence. They are local support tools, not stages or
state owners.

## Setup and live ownership

`node scripts/setup.mjs` is the single setup owner for doctor, install, update,
uninstall, recovery, rollback, and separately approved state purge.
Mutations are dry-run/digest/approval bound, transactional, and rollback-safe.

Setup may touch only plan-bound Hard Eng-owned wiring. It preserves unrelated
or private files, Codex task/auth/log/cache/trust state, Codebase Memory,
Context Mode, and custom agent profiles without separately approved
dispositions.

## Change rule

Any change to lifecycle behavior, routing, state, setup, supported source,
cost guarantees, user-visible proof, publication, or live ownership updates
this file in the same accepted plan.
