# Adapt + repair checks

Apply when adapting or repairing project checks; use native diagnostics for enforced requirements.

| Agent decision | Required proof |
| --- | --- |
| Package/source coverage | Match actual production owners, nested packages + native workspaces. Review scan roots, generated/vendor attributes, ignored files and dynamic entry points; a clean report cannot prove omitted code was examined. |
| Import boundaries | Derive public/private interfaces + allowed dependencies from actual architecture. Prove allowed → pass, forbidden → fail, restored → pass, including relevant aliases, exports + test imports. Do not invent boundaries to satisfy a gate. |
| Performance | Choose representative workloads/environment + justified latency, memory, frame or operation budgets. Intentionally exceed each budget to prove failure. Flutter rendering needs profile-mode device measurements; debug unit tests are insufficient. See [Efficiency](efficiency.md) for bulk/async cases. |
| Security + dependencies | Review actual trust boundaries, native exclusions, extractor coverage + selected lockfiles/images. Confirm the scanned image is the intended build; scanner success does not establish exploitability or complete coverage. |
| Exceptions | Only proven false positives or intentional supported patterns; narrow native exception + adjacent reason/evidence. Keep the rule active elsewhere. |
| Parallelism | Opt in only independent commands with distinct outputs; account for child workers, memory + connections. Builds, generators and report cleaners may need ordering. |

Use existing [Python](../templates/hard-eng.python.json), [JavaScript](../templates/hard-eng.javascript.json) or [Dart/Flutter](../templates/hard-eng.dart.json) templates when adapting a new package. Do not copy a template over project-specific contracts.

## Plan checks

Load for planning-stage checks or plan validation failures. Use [HE Plan](../../he-plan/SKILL.md) for readiness + authorization; [PLAN.md](../../he-plan/templates/PLAN.md) owns required fields.

| Command | Required declaration |
| --- | --- |
| `python3 .hooks/hard-eng.py check --plan-stage Draft` | Filled plan; permits pending baseline/intermediate verification. |
| `python3 .hooks/hard-eng.py check --plan-stage Ready` | Ready or Complete; baseline Passed or explicit Exception with evidence/authorization/impact; UX Passed with evidence or reasoned N/A; no declared blockers. |
| `python3 .hooks/hard-eng.py check --plan-stage Complete` | Complete; above requirements + implementation evidence and no unchecked requirements. |

Every command also runs native project checks. Ordinary `check` (including Stop/pre-push/CI) requires Complete for non-Markdown changes; Markdown-only planning can stop at Draft/Ready. Changed root/feature plans take precedence; otherwise active plans apply. An unchanged historical Complete plan cannot cover new work relative to a known base. Missing bases fail plan validation; a new branch's zero base or an unborn repository uses Git's empty tree (the whole initial snapshot). Unchanged repositories can still be audited without inventing a task plan.

The check validates structure + declarations, not evidence truth, approval or relevance. A passing Draft/Ready run is not implementation completion. Reopen the same plan if completion verification fails; do not replace failure with N/A or leave a false Complete claim.
