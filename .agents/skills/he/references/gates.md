# Adapt + repair checks

Apply when adapting or repairing project checks; use native diagnostics for enforced requirements.

Plan migration: Ready/Complete plans now need an explicit `E2E:` disposition. When reopening or validating an older plan, derive it from that plan's recorded runtime evidence or a concrete inapplicability reason; missing evidence remains pending. Do not relabel historical tests as fresh execution or turn local proof into remote delivery.

| Agent decision | Required proof |
| --- | --- |
| Package/source coverage | Match actual production owners, nested packages + native workspaces. Review scan roots, generated/vendor attributes, ignored files and dynamic entry points; a clean report cannot prove omitted code was examined. |
| Affected selection | `depends_on` = reviewed direct package-impact edges from native manifests, workspace/service setup and root lockfile/tool providers; traversal includes transitive dependents. Missing mapping is unknown, not `[]`, so package checks stay full. A known no-change/plan-only diff may run shared checks. Hard Eng config, workflow and scaffold changes stay full; root package/lockfile changes select that root + its reviewed consumers. |
| CI ownership | Inspect existing jobs before assigning Hard Eng work. Each required assertion has one job/owner; compare arguments, reports and thresholds before removing duplicates. Keep local native checks; integrate missing CI assertions into existing jobs and name their required results in `shipping.checks`. Setup preserves existing workflows and leaves adaptation pending; it generates a new workflow only with a project shipping policy. |
| Import boundaries | Derive public/private interfaces + allowed dependencies from actual architecture. Prove allowed → pass, forbidden → fail, restored → pass, including relevant aliases, exports + test imports. Do not invent boundaries to satisfy a gate. |
| Performance | Choose representative workloads/environment + justified latency, memory, frame or operation budgets. Intentionally exceed each budget to prove failure. Flutter rendering needs profile-mode device measurements; debug unit tests are insufficient. See [Efficiency](efficiency.md) for bulk/async cases. |
| Security + dependencies | Review actual trust boundaries, native exclusions, extractor coverage + selected lockfiles/images. Confirm the scanned image is the intended build; scanner success does not establish exploitability or complete coverage. |
| Missing inputs | Repair missing/stale coverage, reports, generated sources or comparison refs at their producer/selection owner. Preserve the required metric, threshold and scope; disabling the metric or asserting the disabled configuration in a test does not repair the input. Unavailable proof remains a failed/blocked check. |
| Exceptions | Only proven false positives or intentional supported patterns; narrow native exception + adjacent reason/evidence. Keep the rule active elsewhere. |
| Parallelism | Opt in only independent commands with distinct outputs; account for child workers, memory + connections. Builds, generators and report cleaners may need ordering. |

CI adaptation is one-time repository work, not a second check runner or receipt store. Reuse native job dependencies and failure propagation; required checks must report for affected and unaffected changes. Wire reviewed package impact before relying on `--base`; unknown mappings intentionally run full scope. Provision only the selected owners' tools, reuse native caches without stale-version fallback, and measure both critical-path time and runner minutes. Do not widen timeouts to conceal duplication. A build/performance/browser prerequisite remains required when its consumer moves jobs.

`shipping.ci_seconds` bounds each named check's reported execution time. A three-second aggregate does not measure its upstream jobs: retain meaningful worker checks in the policy and measured native workflow/job timeouts. Report end-to-end CI elapsed time separately; do not claim a whole-pipeline budget from the aggregate's duration. Existing monoliths require a deliberate assertion-by-assertion migration before removing their product triggers; setup never deletes them automatically.

Use existing [Python](../templates/hard-eng.python.json), [JavaScript](../templates/hard-eng.javascript.json) or [Dart/Flutter](../templates/hard-eng.dart.json) templates when adapting a new package. Do not copy a template over project-specific contracts.

## Plan checks

Load for planning-stage checks or plan validation failures. Use [HE Plan](../../he-plan/SKILL.md) for readiness + authorization; [PLAN.md](../../he-plan/templates/PLAN.md) owns required fields.

| Command | Required declaration |
| --- | --- |
| `python3 .hooks/hard-eng.py check --plan-stage Draft` | Filled plan; permits pending baseline/intermediate verification. |
| `python3 .hooks/hard-eng.py check --plan-stage Ready` | Ready or Complete; baseline Passed with evidence; UX Passed with a Markdown image reference or reasoned N/A; explicit E2E disposition; no declared blockers. |
| `python3 .hooks/hard-eng.py check --plan-stage Complete` | Complete; above requirements + implementation evidence, no unchecked requirements, and no pending local E2E. Deployment-only E2E requires Deploy and configured delivery checks. |

Every command also runs native project checks. Ordinary `check` (including Stop/pre-push/CI) requires Complete for non-Markdown changes; Markdown-only planning can stop at Draft/Ready. Changed root/feature plans take precedence; otherwise active plans apply. An unchanged historical Complete plan cannot cover new work relative to a known base. Missing bases fail plan validation; a new branch's zero base or an unborn repository uses Git's empty tree (the whole initial snapshot). Unchanged repositories can still be audited without inventing a task plan.

The check validates structure + declarations, not evidence truth, approval, relevance or delivery chronology. A passing Draft/Ready run is not implementation completion. Baseline Exception is rejected. If the Ready or Complete command fails, return the same plan to Draft with the actual blocker; do not replace failure with N/A or leave a false Ready/Complete claim. Starting failures follow [HE Plan's baseline repair route](../../he-plan/SKILL.md#baseline-repair); build regressions stay in their current effort. Neither route may weaken checks to bypass actual findings.
