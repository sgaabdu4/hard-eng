# Repair observed skill failures

Start = failing request + observed behavior + intended outcome. Fix the smallest responsible instruction; rerun the request.

```mermaid
flowchart TD
  F{Failure}
  F -->|Wrong task| T[Fix trigger or invocation]
  F -->|Missed detail| M[Sharpen route; shared rule inline]
  F -->|Excess context| E[Route conditional detail]
  F -->|Stops early| S[Clarify completion; split only if still failing]
  F -->|Conflict| O[One owner; delete duplicates]
  F -->|Cryptic| C[Restore missing meaning]
  T & M & E & S & O & C --> R[Rerun original + nearby valid request]
  R --> V{Resolved?}
  V -->|Yes| D[Done]
  V -->|No| F
  V -->|Unknown| G[Report missing evidence]
```

Verification = original failure corrected + nearby valid behavior preserved. Unknown → name missing evidence; no new universal rule without a demonstrated need.
