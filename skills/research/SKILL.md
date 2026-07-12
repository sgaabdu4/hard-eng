---
name: research
description: Gather decision-grade repository, web, or library evidence for planning or implementation.
---

# Research

## Contract

- Start = exact research question + decision it must unblock + freshness requirement.
- Evidence order = local authoritative source → primary external source → secondary context.
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
- Each relevant surface = inspected + evidence, `N/A` + reason, or unknown + next proof.
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
