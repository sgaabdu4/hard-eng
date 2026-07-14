---
name: he-ship
description: Deliver a green Hard Eng PLAN through sync, publish gates, Git delivery, and CI.
---

# Hard Eng Ship

## Contract

- Input = `$he`-selected fresh PLAN + `route_target=$he-ship` + exact green snapshot.
- Output = repository-policy delivery + terminal receipt, or checkpointed return to `$he-build`.
- Owner = sync + snapshot continuity + commit/push/PR/CI/merge policy + delivery receipt.
- Code/test/doc fixes = `$he-build`; ship never patches a failing artifact.
- Load [workflow.md](references/workflow.md) before shipping or resume.

## Invariants

- Delivery policy = repository rule or exact user instruction; PR/direct/merge choice is never inferred.
- Existing exact authorization = continue without re-asking; missing material scope = checkpoint + one question.
- Scope = target + remote + paths + commit(s) + push + PR/direct + merge policy.
- Sync/content/CI change → PLAN issue + `building`/`active_slice=final` + new stale round → `$he-build`.
- Built snapshot ⇄ implementation commit = `reconcile-head`; mismatch blocks publish.
- PLAN = state evidence; implementation commit excludes PLAN; repository policy decides PLAN persistence.
- Publish gates = `$deterministic-checks` `publish` + dry-run push + remote/branch protections.
- Final learning consolidation = `$he-learn`; open candidate or prevention mutation → `$he-build`.
- Forbidden = force push + bypassed hook/check + hidden path + fabricated CI/PR/merge result.

## Complete

- Intended artifact = exact green snapshot.
- Repository delivery contract = satisfied + verified remotely.
- Required CI = green; required review/merge = complete per policy.
- Required evidence contracts = PASS.
- PLAN = `shipped` + ship stage complete + receipt/URLs/SHAs/results + no open item/candidate.
