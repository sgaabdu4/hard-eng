# Rollout Stage

## Decide

| Area | Required decision |
|---|---|
| Release | environments + internal/beta/tenant/percentage strategy + deployment/migration order + dependencies |
| Control | flag only from gradual-release/rollback need; owner + removal trigger/date |
| Observe | events/metrics + dashboards/alerts + privacy + adoption/success/guardrail/rollback thresholds |
| Prepare | owners/reviewers + support visibility/runbook + user/stakeholder communication |
| Recover | rollback triggers/procedure + data compatibility + irreversible boundary + post-release review |

- Telemetry = minimum decision-useful data; unnecessary personal data = forbidden.

## Route

1. Derive deployment/migration dependency graph from technical design + environments.
2. Choose direct/gradual/internal/tenant/percentage release from measured risk; add flag only when it changes control/recovery.
3. Define success/guardrail/rollback signals → minimum events/metrics → dashboard/alert owner + threshold.
4. Sequence deploy/migrate/enable/observe/support/communicate; name owner + proof at each boundary.
5. Simulate failure before/during/after release → rollback procedure + data compatibility + irreversible stop.
6. Schedule flag removal/post-release review only when created by this plan.

## Complete

- Each release/migration/monitor/rollback action has owner + order + threshold + proof.
- Compatibility, support, alert response, and flag removal = explicit when applicable.
- Skip proposal only for a proven non-released/non-operational change.
