---
name: hard-eng
description: Use when the user invokes $hard-eng, requests a serious feature-to-ship lifecycle, or needs durable Plan, Build, Ship, and conditional Learn state across compaction or Codex worktrees. New or ambiguous features enter Plan; bounded accepted work can enter Build.
---

# Hard Eng

Use one local state tool and load only the reference for the current boundary.
Hard Eng never chooses a model or automatically launches an eval, subagent,
Imagegen call, daemon, cron job, or semantic review fleet.

## Enter or resume

- Call `state` with `status` once. If bound, obey its exact `phase`, `cursor`,
  `next`, and revision; do not infer progress from chat history.
- If unbound, read [route.md](references/route.md). `status` reveals nothing;
  `resume` requires the user-selected run ID and any required takeover approval.
- Never call human-only `he runs` from an unbound model task. The user obtains a
  run ID from `plan.md` or their terminal.

## Load one reference

| Boundary | Reference |
| --- | --- |
| Route or Direct contract | [route.md](references/route.md) |
| Plan | [plan.md](references/plan.md) |
| UI decision or prototype | [ui-decision-lab.md](references/ui-decision-lab.md) |
| Build | [build.md](references/build.md) |
| Ship | [ship.md](references/ship.md) |
| Admitted finding | [learn.md](references/learn.md) |
| Corruption, interruption, drift, or Handoff | [recovery.md](references/recovery.md) |

## State and evidence

- Submit a typed `event` only after its required evidence exists. Unsupported
  prose never advances state.
- Plan work has one repository-root `plan.md`; Direct Build creates none.
- Use Codebase Memory first for structural/impact work and Context Mode for
  large output. Store only their bounded receipts, never raw output.
- Scope expansion or a changed accepted-plan digest stops Build/Ship and returns
  to Plan reconciliation.
- Keep user updates short, show decisions/evidence at human boundaries, and
  wait whenever the state owner is `user`.
