---
name: he-ship
description: Deliver a verified build through a task branch and PR, check the intended remote result, and clean up the completed task safely. Use for PR creation, shipping, merging or release/deployment requests; skip planning, implementation and review-only work.
---

# Hard Eng Ship

- Input = [HE Build](../he-build/SKILL.md) local Ready-for-ship evidence + user's delivery scope. Reuse authorization; a skill, plan or green check adds none. Resolve the actual repository, branch/PR and requested environment from the task + project instructions. Missing material authority/target → finish safe preparation, then ask only for that boundary.
- Contract = [native shipping checks](references/checks.md); configure from repository facts in the existing gate file. Missing configuration/access/proof blocks. Use project-owned release commands and existing Git/`gh`; do not introduce a provider, tracker, upload service or watcher automatically.

```mermaid
flowchart TD
  A[Current build proof + delivery scope] --> B[Task branch + scoped PR with evidence]
  B --> C[Native ready check]
  C -->|Pass + merge authorized| M[Guarded merge]
  C -->|PR-only request| P[Report PR and actual checks]
  M --> D[Verify merged revision + required delivery proof]
  D -->|Pass| K[Guarded task cleanup]
  K --> R[Record actual outcome in same plan]
  C & D -->|Code failure| F[HE Build: fix + affected proof]
  F --> B
  C & D & K -->|Unavailable prerequisite| U[Preserve proof + exact resume condition]
  click C "references/checks.md"
  click M "references/checks.md"
  click K "references/checks.md"
  click F "../he-build/SKILL.md"
```

## Prepare + deliver

- Isolation = reuse this task's branch/worktree + existing PR. If work began in a shared/base checkout, isolate the authorized changes before shipping; preserve unrelated staged/unstaged files. One coordinator owns Git/ref/environment mutations. No blanket staging, history rewrite or branch-rule change.
- UI changes = before + after evidence in the PR. Reuse the baseline captured before implementation; capture the matching final route/state/viewport and inspect both through [E2E](../e2e/SKILL.md). Screenshots show appearance; interactions may need a short recording. Use supported GitHub attachments and the labeled format in the contract. Missing original evidence → recover the real baseline in isolation, never invent it. Preserve published proof through cleanup.
- PR = actual problem/result + scoped diff + tests/evidence + material risks. Resolve a matching existing PR before creating one. A failed lookup is unknown, not absence. PR creation does not grant merge authority. Recheck after source changes; handle actionable review findings through existing [Code Review](../code-review/SKILL.md) and HE Build.
- Verification = native check on the current PR/revision; pending, skipped required work, an old green run or a successful command with missing proof cannot establish delivery. For Deploy, the configured project check must inspect the intended deployed revision and affected runtime through E2E. No generic health page or local screenshot substitutes for the changed remote behavior.
- Recovery = inspect the actual remote result before retrying interrupted actions. Code/config changes → HE Build + fresh affected/final checks. Delivery-only outages/permissions → preserve local Complete and record the unfinished delivery + exact resume condition. Use the project's scoped recovery procedure; no blind migration retry or rollback.

## Completion + cleanup

- Same plan = local build Complete remains distinct from `Delivery target: PR`, `Merge` or `Deploy` in Verification. Retain full pending delivery requirements as prose; replace pending claims only with actual evidence. Never tick remote proof before it exists or create a second state file.
- Cleanup = only after confirmed merge and required delivery proof. Retain the same relative plan in the persistent checkout, recovering it from the verified merged revision if needed; preserve unrelated edits. Deliberately clean only known generated artifacts, then run the guard; preserve current/main, dirty/untracked/unknown ignored, locked, reused or changed task worktrees/branches. Initialized submodules or different fetch/push endpoints → retain the task for its repository-owned procedure. Do not delete another active task's checkout. Uncertain ownership/activity → retain it and report the blocker. No force-removal to make cleanup pass.
- Handoff = PR/revision + current CI result + required release/runtime proof + cleanup outcome + remaining limitations. Say submitted, merged or deployed according to what happened; local Complete is not a delivered task. Credentials and publication rights remain external prerequisites.
- Efficiency = reuse matching proof; measure pre-push/CI duration against configured project budgets. Optimize demonstrated setup/critical-path waste at the existing gate owner; retain required checks, latest-tool policy and failure detection. No repeated full review, fixed agent count, score target or unmeasured “fastest” claim.
