---
name: he-learn
description: Turn a verified process failure into narrow durable prevention without blocking normal product delivery.
---

# Hard Eng Learn

## Contract

- Input = affected repository + explicit `he learn` evidence OR verified trigger from any route.
- Any route = Direct + Diagnose + Feature Loop + Build + Ship; active Feature Brief = not required.
- Output = `<repo>/.agents/learning/<learning-id>.json` + assigned prevention destination, or exact non-candidate.
- Lifecycle = unchanged; overlay only.
- Load [workflow.md](references/workflow.md) before classification or repair.

## Ownership

- Failure classification + prevention owner + follow-through = this skill.
- Recurrence/root-cause proof = `repeated-failure-learning`.
- Prevention implementation = destination owner under its normal direct/`he` route.
- Product implementation = current stage owner; learning does not seize it.
- Repository learning state + runtime wiring = [learning_state.py](scripts/learning_state.py).

## Invariants

- Trigger = verified repository recurrence OR engineering correction OR false passing check OR systemic protected-boundary gap OR repeated manual waste.
- One-off implementation finding = current build loop; learning candidate = forbidden.
- Record fact once in affected repository = failure + evidence + root cause + occurrences + prevention owner + required proof.
- Global `~/.agents` = learning engine only; repository-specific record/prevention promotion = forbidden.
- Narrowest durable owner = remove cause → reuse/repair owner → invariant/type → regression test → scanner/hook → CI → script/tool.
- Mechanically detectable prevention = executable rule/tool/fixture at the closest owner; prose-only prevention = incomplete.
- Skill fallback = same root proven ≥2 by `repeated-failure-learning` + explicit deterministic limit + canonical `<repo>/.agents/skills/<name>/`.
- Skill discovery = Codex + Copilot read canonical `.agents/skills` directly; Claude uses setup-owned `.claude/skills/<name>` symlink.
- Prevention placement = before the expensive/failure boundary + cheaper than recurrence; independent checks parallel.
- Trigger record = `learning_state.py start`; spawn one depth-1 `he-learn` helper only when output says `helper=he-learn`.
- Repair = tracked + non-blocking; duplicate helper selection for one record = forbidden.
- Block/pause only when continued product work risks security/privacy/data loss/irreversible action or another protected boundary.
- Cross-repository repair = destination-owned normal flow; routine source PLAN pause/writer lease/nested lifecycle = forbidden.
- Open learning blocks task closure; resolved, non-candidate, or deferred with an owner + real next action permits closure.

## Complete

- Candidate validity = evidence-backed.
- Prevention owner + proof = explicit.
- Applied prevention = violation fixture + valid fixture + actual-seam proof.
- Repository check = `~/.agents/setup.sh repo-check <repo>` PASS.
- Deferred prevention = repository-owned next action without blocking unrelated delivery.
