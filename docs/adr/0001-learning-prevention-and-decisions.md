# 0001 — Learning checkpoints and durable decisions

Status: Accepted

## Context

The user requested repeated-failure prevention and decision capture throughout agent work, extending the initial HE Learn proposal. Hooks previously covered session start and completion only.

## Decision

- Use session and supported failure checkpoints; the agent judges evidence in its current context. Ordinary prompt/tool callbacks were removed under the user's September 14 efficiency correction because their repeated message added no evidence.
- Prefer deterministic prevention; skill creation is a last resort under Writing Great Skills.
- Skills live in `.agents/skills/`; terse durable decisions live in `docs/adr/`.
- Reuse current task authorization and proof owners; no learning database or global memory writes.

## Consequences

Native hooks can deliver consistent prompts while tests/checkers enforce specific invariants. Semantic learning and future applicability still require agent judgment and behavioral proof. Client event/output differences must be verified.

## Evidence

User implementation and location instructions, 11 September 2026. [Implementation plan](../../features/he-learn/PLAN.md) records source checks, native behavior and client limitations. Acceptance of this decision does not claim delivery.
