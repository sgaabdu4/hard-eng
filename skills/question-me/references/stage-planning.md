# Planning Stage

## Input Contract

| Field | Required content |
|---|---|
| `stage` | Current `$he-plan` stage |
| `stage_brief` | Boundary + decisions this stage owns |
| `evidence` | Verified facts + sources + freshness |
| `decision_inventory` | Required decisions + current status |
| `prior_decisions` | Approved upstream constraints |
| `completion_criteria` | Exhaustive stage exit proof |

Missing input → return `FAIL` + exact missing field; never reconstruct stage intent.

## Per-Question Loop

1. Reconcile inventory against evidence + prior decisions; assign `SKILL.md` Admission decision status.
2. `objective-gap` → `$research` with exact question + decision + scope + freshness; merge `Verified/Inferred/Unknown`; reclassify.
3. `contradiction` → show conflicting claims + sources; ask for resolution only when authority/freshness cannot settle it.
4. Select earliest `user-decision`; render one question with evidence + consequence + recommendation; batch only independent items.
5. User answer → map to inventory ID + recorded decision; correction → show changed decision + downstream impact; restart at step 1.
6. No unresolved item → emit Stage Review; ask only `Approve this stage?`; return the response unchanged to `$he-plan`.

## Stage Review

```md
### Stage Review: <stage>
- Understood: <stage outcome>
- Approved decisions: <id = decision>
- Recommendations: <pending recommendation or none>
- Assumptions: <requires confirmation or none>
- Contradictions: <evidence conflict or none>
- Open questions: <material decision or none>
- Risks: <risk + mitigation/owner>
- Files updated: <path or none>
- Proposed skipped work: <item + why + consequence or none>
- Readiness: PASS | CONCERNS | FAIL
- Final user response: <verbatim or none>
```

## Return Gate

- `PASS` = completion criteria proven + recommendations accepted/rejected + assumptions confirmed + contradictions/open questions empty.
- `CONCERNS` = response needed or explicit defer/skip proposed with consequence.
- `FAIL` = missing input/evidence blocks a material decision.
- Return = review fields + verbatim final user response; `$he-plan` alone interprets approval, skip, persistence, invalidation, or advancement.
