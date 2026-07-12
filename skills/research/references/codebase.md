# Codebase Evidence

1. Establish root + revision + worktree state + applicable rules + current accepted product/design/architecture.
2. Establish source boundaries: related repositories/packages/services + corpus/fixtures/generated artifacts + each canonical generator/owner.
3. Topology/impact → apply global Codebase Memory CLI contract; verify every graph claim natively.
4. Inspect relevant behavior: entrypoints/routes + UI + domain/backend/data + contracts/schema + auth/permissions/errors + integrations.
5. Inspect delivery context: dependencies/lockfiles/supply-chain policy + config/flags + telemetry + tests/CI + runtime/infra + NFRs + history + code/review ownership.
6. Test negative assertions with bounded search; record search scope + exclusions + inaccessible evidence.
7. Finish when each relevant surface has evidence, `N/A` reason, or explicit blocker; unexplained coverage gap = `FAIL`.

- Index disposable snapshot when active worktree mutation risk exists; never delete/overwrite another project index.
- Runtime/log/metric/trace access requires existing authorization; secrets never enter notes.
- Blocker = missing/inaccessible proof + affected decision + next owner/action; never convert it to an assumption.
