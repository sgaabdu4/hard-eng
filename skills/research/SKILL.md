---
name: research
description: Verify current repository, vendor API, or library facts before a decision.
---

# Research

## Contract

- Start = exact research question + decision it must unblock + freshness requirement.
- User-supplied source/claim/checklist = minimum coverage ledger; inspect each item or return explicit `N/A | Unknown`.
- Evidence order = local authoritative source → primary external source → secondary context.
- External-contract-dependent plan/code/review/claim → matching primary-source route `PASS` first.
- External/runtime/platform-dependent solution selection or implementation = current primary-source `PASS` before edit + local integration binding.
- External/runtime/dependency remedy = current primary contract + bounded public analogous-incident/remedy search before edit; peer workaround = discovery, never authority.
- First paid or state-changing external/native attempt = current primary-source receipt + local syntax/contract proof + resolved version/tool/path.
- Contract-surprise failure = pause retry → current official docs/changelog/runner manifest + adjacent-assumption audit → smallest correction.
- Official source proves contract + compatible parser/compiler/runner probe proves local semantics; neither substitutes for the other.
- Separate `Verified` + `Inferred` + `Unknown`; every material claim → path or URL + revision/date/version.
- Existing code = current state, not approval; negative claim = bounded coverage + limitation.
- No production mutation; reusable Markdown notes only when future work will consume them.

## Route

| Need | Load | Skip proof |
|---|---|---|
| Repository topology/behavior/impact | [codebase.md](references/codebase.md) | No repository question |
| Current facts/standards/changelogs/papers/URLs | [external.md](references/external.md) | Local evidence fully answers decision |
| Current dependency/library API | [library-docs.md](references/library-docs.md) | No library/version question |

- Multiple needs → load every matching reference; do not make one source impersonate another.

## Completion

- Coverage owner = matching route reference.
- Active configured Feature Brief = record local/external evidence through `skills/he/scripts/execution_evidence.py record-research` before approval; receipt path = `features/<slug>/receipts/research.json`.
- Receipt freshness = `--fresh-until YYYY-MM-DD`; local source SHA-256 = automatic + rechecked; external source = one matching `--source-version` each.
- Configured Direct mutation = `execution_evidence.py start-direct` + current request digest + runtime session id + exact intended paths + matching research fields before the first write.
- Each relevant surface = inspected + evidence, `N/A` + reason, or unknown + next proof.
- Narrative summary cannot collapse or silently omit a coverage-ledger item.
- Contradiction → preserve both claims; resolve by authority/freshness or return decision blocker.
- Reusable note → repository convention; absent convention → user-approved path.

## Output

| Section | Content |
|---|---|
| Decision answer | Answer first |
| Verified | Claim + source + revision/date/version |
| Inferred | Inference + supporting evidence + confidence |
| Unknown | Gap + impact + next proof |
| Coverage | Inspected / `N/A` / inaccessible |
| Sources | Primary first; secondary labeled |

- Missing decision-grade evidence → `CONCERNS` or `FAIL`; never manufacture certainty.
