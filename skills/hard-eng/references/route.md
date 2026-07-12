# Route

Classify the request from evidence before creating state. If evidence leaves a
material uncertainty about intent, scope, ownership, deletion, live wiring, or
accepted behavior, stop before mutation, show the exact uncertainty, ask the
smallest targeted question, and wait for the user. Do not turn uncertainty into
an inferred route.

When a run is already bound, submit `clarification.required` with one to three
bounded question IDs and the conflict digest before asking. The runtime binds
the current plan/candidate and moves to `await-user-clarification`; no other
event is legal until `clarification.answered` records an explicit user answer.
An unbound direct task asks without creating or guessing a run.

| Request evidence | Route |
| --- | --- |
| New feature, user-visible workflow, ambiguity, scope expansion | Plan |
| Auth, billing, schema, migration, privacy, permissions, destructive/data-loss risk | Plan |
| Matching accepted `plan.md` digest | Build |
| Small bug with clear reproduction and acceptance | Direct, or Direct Build when lifecycle tracking was requested |
| Mechanical edit, narrow docs change, read-only answer/audit | Direct |
| Adoptable bounded candidate and explicit Ship request | Ship |
| Open admitted finding and explicit Learn request | Learn interrupt |

Convenience never bypasses project rules, security, accessibility, trust, or
data-loss boundaries. Explain a non-safety override before accepting it.

For Direct Build, record a bounded contract with objective, acceptance, exact
scope, non-goals, why Plan triggers do not apply, user invocation evidence, and
review cadence. Direct Build is illegal for a new feature, material product/UI
choice, schema/auth/billing/migration/data-loss risk, unresolved acceptance, or
broad scope.

When routing needs repository structure, callers, dependencies, routes, or
impact, use Codebase Memory first. Use Context Mode for large evidence. Ask the
user only for facts that cannot be discovered safely.
