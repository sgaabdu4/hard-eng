# Learn

Learn is a conditional Build/Ship interrupt, not an automatic final ceremony.
Admit only a normalized miss seen twice, an escaped defect, a
security/safety/data-loss/accessibility-critical gap, or a high-leverage gap
whose recurrence cost exceeds the guard cost.

Submit `finding.admitted` only with bounded provenance: stable ID and SHA-256
fingerprint, severity, action, source stage, typed source reference, occurrence
count and one evidence digest per occurrence, affected owner, immediate repair,
admission reason, and proposed durable guard. `repeated` requires at least two
occurrences. No provenance means no transition.

Repair the immediate behavior, reproduce the process gap with the smallest bad
fixture, and place the guard in the narrowest existing owner: test, linter,
scanner, schema, CI, owner documentation, or only when irreducibly semantic, a
skill reference. Do not create a learning corpus or another workflow layer.

Submit `learn.guard-proven` with the finding ID, whether the tree changed, and:

- owner kind and bounded owner reference;
- bad-fixture digest;
- `fail_before: {result: fail-expected, evidence_digest}`;
- `pass_after: {result: pass, evidence_digest, candidate_fingerprint}`; and
- the bounded list of stale rules consolidated or removed.

A tree-changing guard invalidates candidate proof and returns to focused Build
verification for the affected slice. A no-tree guard returns to the exact
recorded Build/Ship boundary. Complete remains blocked while any admitted
finding is open. Never invoke a second model or retry an unchanged failure.
