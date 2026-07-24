# Plan Admission

## Purpose

- Admission = prove accepted design is implementable + failure-complete before `build-ready`.
- User approval = product/decision acceptance; never substitutes for engineering completeness.
- Final build audit = implementation verification; first discovery of a planned owner/state/boundary/scenario = false planning gate.

## Required Evidence

`## Decision Model` table header:

`ID | Decision/default | Alternatives | Selected behavior | Authority | Evidence | Consequences/revisit`

- Row = unique `D-*`; authority = `user|engineering|external`.
- User decision evidence = `user: <verbatim concrete decision>`; generic `yes|approve|continue|go ahead|do it|ok` = forbidden.
- Engineering/external decision evidence = SHA-256 receipt from complete decision evidence.
- Policy/default/eligibility/inclusion/exclusion/permission/role/initial-state choice = explicit row; umbrella quality/safety label = incomplete.
- Every `D-*` maps through traceability; every traced decision has one owner row.

`## Traceability` table header:

`ID | Requirement | Decision | Flow/state | Contract/owner | Proof | Telemetry/rollout | Slice`

- Row = `TR-*` + concrete `R-*` + `D-*` + `F-*` + `C-*` + `T-*` + `S-*` references.
- Every accepted requirement/risk + failure-model proof maps forward once; broad labels do not cover multiple unnamed behaviors.
- Every authoritative `R-*|D-*|F-*|C-*|T-*|S-*` owner is traced; hidden/untraced owner IDs = blocker.
- Every canonical `C-*` row records its exact consumers as repeated `` `trace:TR-#` `` edges; validator requires bidirectional equality with Traceability.
- Every `T-*` row records each required production/proof/config path as `` `owner:S-#:repository/relative/path` ``; ≥1 edge per row.
- Every trace proof has an owner edge in that row's consuming slice; multi-slice trace ≠ permission to claim a proof owned only by another slice.
- `Technical` changed-owner claims use the same owner edge; every edge targets an exact `planned_paths` member.
- Owner paths = normalized repository-relative literals; absolute/traversal/glob/control/duplicate edges = invalid.

`## Failure Model` table header:

`ID | Boundary/transition | Failure/interrupt | Durable state | Recovery owner | Retry/timeout | Observable proof`

- Row = one `FM-*` crash/failure timing at one `C-*` boundary + traced `T-*` proof + repeated `` `slice:S-#` `` edges.
- Inventory = before call + during/ambiguous call + accepted call/before local persistence + persistence failure + timeout/expiry + duplicate/concurrent + retry exhaustion + process termination + operator recovery as reachable.
- Async/distributed/irreversible/security/privacy/data-risk plan = concrete model; `FM-NA` forbidden.
- Standard plan with no reachable async/external/partial/irreversible boundary = one evidenced `FM-NA` row.
- Every non-terminal durable state = one recovery owner + bounded next action; unowned state = blocker.

`## Guarantee Model` table header:

`ID | Type | Contract | Trace`

- Any plan with concrete `FM-*` rows = one `G-*` row per enforceable cross-boundary guarantee; every concrete failure maps to at least one row.
- Type = `membership|identity-access|exhaustive|external-effect|irreversible|time-bound|configuration|dependency|retention|reconciliation`.
- Contract = exact `key=value; ...` typed schema; unknown/missing/duplicate key + whitespace-bearing/free prose value = invalid.
- Common = `owner=C-*` traced in row + `authority=database|provider|permission|configuration|client|server` + exact `authority_ref` + SHA-256 `evidence` + comma-separated `proofs=T-#,T-#`.
- `membership` = `snapshot + capture=transactional_once + high_water + order + query_index + completion=cursor_exhausted_at_high_water`; owner fields = distinct.
- `identity-access` = provider `permission + enumeration + cursor + completeness + order + credential_match=hash_canonical_id|exact_id + expiry + incomplete=deny`.
- Identity cursor mode = `enumeration=exhaustive_cursor + completeness=cursor_exhausted`; cursor advances provider pages in declared order.
- Identity complete-list mode = `enumeration=complete_response + completeness=total_eq_length`; require returned total = parsed list length, deterministic local order, exhaustive local cursor, and deny on provider/parse/count mismatch.
- `exhaustive` = `inventory + partition + query_index + cursor + orphan=include + completion=zero_remaining`.
- `external-effect` = durable `intent` + distinct `resource_id + id_policy=provider_unique_once|provider_authorized_deterministic|provider_returned + retry_key=resource_id|intent + version + scope_key + precall_fence=required + stale=reject + cleanup + cutover=drain_then_activate`; owner fields = distinct.
- External ID policy = unique/deterministic provider-authorized ID → persist before first call + retry by `resource_id`; provider-returned ID → retry by durable `intent`; custom derivation without cited provider authority = invalid.
- `irreversible` = `capability_owner=client|server_acknowledged + created_before=request + server_storage=hash_only + lost_response=same_capability_retry`.
- `time-bound` = positive integer `lease_ms/execution_ms/recovery_ms/jitter_ms + relation=strict_gt_sum`; validator proves `lease > execution + recovery + jitter`.
- `configuration` = full manifest SHA-256 baseline + `preserve=all_unrelated`, or scoped overlay + `preserve=outside_scope_unchanged`; traced `proof=T-*` required.
- `dependency` = `provider_slice + consumer_slice + foundation=C-* + relation=precedes_or_same`; validator proves provider slice ordinal ≤ consumer.
- `retention` = `active=zero + terminal=retained + retention_ms + deletion_override=retain|explicit_exhaustive + proof=T-*`.
- `reconciliation` = `trigger + inventory + query_index + cursor + version + overdue=mark_missed + lease_ms + completion=zero_remaining`.
- Trace = concrete `R-* C-* FM-* T-* S-*`; every reference must exist; one row may cover multiple failure timings of one guarantee.
- `proofs` = exact proof set in Trace; mismatch/omitted foundation proof = invalid.
- Standard plan with evidenced `FM-NA` = section omitted; any standard plan with a concrete failure model uses the same typed gate.

`## Slices` ownership graph:

- Each `S-*` subsection has one exact `maps` row + one `planned_paths` row.
- `maps` = exact concrete `R-*|F-*|C-*|FM-*|G-*|T-*` set derived from Traceability + failure slice edges + Guarantee Trace + proof owner edges; ranges/umbrella labels = invalid.
- `first_build_action` = `+`-joined typed `` `action:kind:S-#:T-#:path` `` tokens only; `kind=modify|create|delete`; split requires `` `action:split:S-#:T-#:source->new-owner` ``.
- Action proof must declare every action path in the consuming slice; every path must exist in that slice manifest; split requires a distinct manifested output owner.

`## Plan challenge` table header:

`Perspective | Scope | Result | Evidence`

- Standard = one independent read-only `complete` review.
- Critical = independent read-only `owner-first` + `boundary-first` reviews.
- Reviewer = ephemeral `codex exec` + no mutation/tools + exact PLAN/repository evidence; review is plan-only, never final code audit.
- Evidence = SHA-256 of complete structured result; only clean `PASS` enters the table.
- Finding = cited gap + earliest owning stage + materiality + required correction; same-root repeat → `$repeated-failure-learning` + pause.

## Classification

| Finding changes | Class | Route |
|---|---|---|
| Implementation already contradicted a concrete approved `TR-*`/`FM-*` row | implementation defect | current build owner fix ⇄ affected proof |
| New/changed state, transition, schema, API/event, owner, dependency guarantee, retry/recovery, security/privacy boundary, operational control, or proof family | plan defect | pause build → reopen earliest affected planning stage |
| Same semantic root after one correction | systemic recurrence | `$repeated-failure-learning` → `$he-learn`; no new audit round |

- Unchanged product outcome does not make a plan defect an implementation defect.
- Plan-defect correction updates canonical accepted content + downstream traceability; issue chronology never becomes replacement architecture.
- User reconfirmation = changed product/UX/trade-off/scope only; engineering-only correction still reruns admission + final full-PLAN approval contract.

## Gate

1. Run plan challenges → resolve every material finding at earliest owner.
2. Repeat affected planning stages + consistency; unrelated accepted proof auto-revalidates.
3. Run `python3 "$HOME/.agents/skills/he-plan/scripts/plan_admission.py" --plan <PLAN.md>` → PASS.
4. Present canonical plan for user approval; approval checkpoint independently reruns the validator.

Complete = decision model + exhaustive structured trace + failure model + critical guarantee model + clean risk-tier challenge + deterministic admission PASS + zero open item.
