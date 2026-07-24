# Feature Brief Alignment

## Input Contract

| Field | Required content |
|---|---|
| `brief_path` | Selected `features/<slug>/PLAN.md` |
| `alignment_boundary` | Outcome + material constraints this question pass owns |
| `evidence` | Verified facts + sources + freshness |
| `decision_inventory` | Material decisions + current status |
| `accepted_constraints` | Current accepted outcome/risk constraints |
| `completion_criteria` | No unresolved material decision |

Missing input → return `FAIL` + exact missing field; never reconstruct product intent.

## Alignment Loop

1. Reconcile inventory against evidence + accepted constraints; assign `SKILL.md` Admission status.
2. `objective-gap` → `$research` with exact question + decision + scope + freshness; merge `Verified/Inferred/Unknown`; reclassify.
3. `contradiction` → show conflicting claims + sources; ask for resolution only when authority/freshness cannot settle it.
4. Select material `user-decision` items; batch independent items + keep dependent questions sequential.
5. User answer → map to inventory ID + accepted decision; correction changing outcome/risk → show exact delta + impact; restart at step 1.
6. No unresolved item → emit Alignment Review to `$he-plan`; do not ask a per-question or per-section approval.

## Alignment Review

```md
### Feature Brief Alignment
- Outcome: <observable result>
- Accepted decisions: <id = decision>
- Recommendations: <pending recommendation or none>
- Assumptions: <requires confirmation or none>
- Contradictions: <evidence conflict or none>
- Open questions: <material decision or none>
- Risks: <risk + mitigation/owner>
- Brief updated: <path or none>
- Deferred scope: <item + consequence or none>
- Readiness: PASS | CONCERNS | FAIL
```

## Return Gate

- `PASS` = completion criteria proven + recommendations dispositioned + assumptions confirmed + contradictions/open questions empty.
- `CONCERNS` = response needed or explicit defer/skip proposed with consequence.
- `FAIL` = missing input/evidence blocks a material decision.
- Return = review fields; `$he-plan` alone presents the complete brief + requests one Ready-to-build approval.
