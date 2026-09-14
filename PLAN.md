# Install latest tools before executing checks

Status: Complete

## Outcome + scope

Resolve current tools with mise install and its normal network timeout before executing them. Reuse mise's native version metadata for the following execution step. Apply this to generated CI and gate provisioning while preserving explicit SDK versions, project workflow customizations and real failures.

## Repository context

The workflow and tool_setup.py relied on mise exec/env for cold provisioning. Upstream mise2026.9.6 classifies both as fast commands despite MISE_PREFER_OFFLINE=false, imposing a three-second lookup limit. Existing configure_ci migration owns supported changes to installed workflows.

## Decisions + authorization

Blockers: None

The user authorized confirmed shared-flow repairs, verification and PR/main delivery. One builder reuses the workflow, provisioner, migration and tests. Every install requests fresh latest versions with the existing zero-age cache setting; execution reuses the freshly resolved metadata with mise's native one-hour cache. No new dependency, file, custom cache, retry layer or global installation.

## Acceptance + steps

- [x] Native cold setup installs current tools and execution selects that installation.
- [x] Failed installation or unresolved versions stop before environment selection.
- [x] New and installed generated workflows retain configured SDKs and custom content; migration is idempotent.
- [x] Packaged scanners, pnpm build permissions and existing SDK PATH remain intact.
- [x] Focused provisioning, failure and workflow regressions pass; final integration follows below.

## Baseline + execution

Result: Passed
Evidence: Original source9fd257c passed its source gate, but cold generated CI failed at a three-second uv lookup and could not launch it. The new regressions fail against the old provisioning/migration owner. Current108 focused tests and direct Pyrefly pass. This is an authorized baseline repair.

## Risks + recovery

Always resolve latest before reusing metadata. Preserve explicit version arguments and reject unresolved-version warnings. Native prototypes exposed invalid offline flags, fallback to host uv and omitted scanner paths; those approaches were removed before delivery. A failed intermediate gate and fixture annotation failure remain recorded as failed experiments, not delivery proof. Existing update candidate checks and rollback remain required.

## ux_reference

N/A — command provisioning and generated CI have no visual interface.

## Verification

Result: Passed
Evidence: Native cold installation retained attestation verification, installed uv0.12.13 and asserted that execution used the matching isolated installation. The actual provision_tools path then resolved all five scanner executables from the managed tool directory.108 focused tests pass, including failure handling, custom workflow migration, idempotence and exact Dart/Flutter tool selection. Direct Pyrefly and whitespace checks pass. The final integrated Complete gate is pending.

Delivery target: Merge
Ready for ship — final integrated Complete gate passed all17 checks,504 tests and four performance checks; tests completed in113.41seconds. Existing GitHub authentication was used for provisioning after anonymous API quota exhaustion, matching CI. No check or attestation was disabled.
Delivery: Pending — exact PR/main checks and native delivery proof required before consumers receive the source revision.
