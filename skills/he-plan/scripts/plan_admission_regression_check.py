#!/usr/bin/env python3
"""Regression proof for Hard Eng semantic plan admission."""

from __future__ import annotations


def fixture(*, risk: str = "critical") -> str:
    perspectives = (
        "| owner-first | owners, callers, states | PASS | sha256:" + "a" * 64 + " |\n"
        "| boundary-first | failures, recovery, operations | PASS | sha256:" + "b" * 64 + " |"
        if risk == "critical"
        else "| complete | full standard-risk plan | PASS | sha256:" + "c" * 64 + " |"
    )
    failure = (
        "\n".join(
            f"| FM-{index} | C-1 guarantee transition | dependency rejects after durable commit | "
            "queued | reconciler | bounded retry after lease | T-1 durable-state assertion |"
            for index in range(1, 11)
        )
        if risk == "critical" else
        "| FM-NA | no async or irreversible C-1 boundary | synchronous bounded operation | "
        "unchanged durable record | request owner | request timeout | T-1 contract assertion |"
    )
    guarantee = (
        """\n## Guarantee Model
| ID | Type | Contract | Trace |
|---|---|---|---|
| G-1 | membership | owner=C-1; authority=database; authority_ref=primaryDatabase; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; snapshot=membershipCutoff; capture=transactional_once; high_water=membershipHighWater; order=membershipSortKey; query_index=membershipOrderIndex; completion=cursor_exhausted_at_high_water | R-1 C-1 FM-1 T-1 S-1 |
| G-2 | identity-access | owner=C-1; authority=provider; authority_ref=identityProvider; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; permission=sessions.read; pagination=exhaustive_cursor; cursor=sessionCursor; credential_match=hash_canonical_id; expiry=expireAt; incomplete=deny | R-1 C-1 FM-2 T-1 S-1 |
| G-3 | exhaustive | owner=C-1; authority=database; authority_ref=primaryDatabase; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; inventory=schemaManifest; partition=accountId; query_index=accountOwnedRows; cursor=documentId; orphan=include; completion=zero_remaining | R-1 C-1 FM-3 T-1 S-1 |
| G-4 | external-effect | owner=C-1; authority=provider; authority_ref=messageProvider; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; intent=effectIntentId; version=effectGeneration; scope_key=actorGeneration; precall_fence=required; stale=reject; cleanup=cleanupTombstone; cutover=drain_then_activate | R-1 C-1 FM-4 T-1 S-1 |
| G-5 | irreversible | owner=C-1; authority=client; authority_ref=secureStorage; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; capability_owner=client; created_before=request; server_storage=hash_only; lost_response=same_capability_retry | R-1 C-1 FM-5 T-1 S-1 |
| G-6 | time-bound | owner=C-1; authority=provider; authority_ref=jobRuntime; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; lease_ms=181001; execution_ms=90000; recovery_ms=60000; jitter_ms=30000; relation=strict_gt_sum | R-1 C-1 FM-6 T-1 S-1 |
| G-7 | configuration | owner=C-1; authority=configuration; authority_ref=deploymentManifest; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; mode=full; scope=deploymentManifest; baseline=sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd; preserve=all_unrelated; proof=T-1 | R-1 C-1 FM-7 T-1 S-1 |
| G-8 | dependency | owner=C-1; authority=server; authority_ref=sliceDag; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; provider_slice=S-1; consumer_slice=S-1; foundation=C-1; relation=precedes_or_same | R-1 C-1 FM-8 T-1 S-1 |
| G-9 | retention | owner=C-1; authority=database; authority_ref=primaryDatabase; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; active=zero; terminal=retained; retention_ms=7862400000; deletion_override=explicit_exhaustive; proof=T-1 | R-1 C-1 FM-9 T-1 S-1 |
| G-10 | reconciliation | owner=C-1; authority=database; authority_ref=primaryDatabase; evidence=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee; trigger=actorCheckin; inventory=futureWork; query_index=actorFutureWork; cursor=workId; version=actorGeneration; overdue=mark_missed; lease_ms=60000; completion=zero_remaining | R-1 C-1 FM-10 T-1 S-1 |\n"""
        if risk == "critical" else ""
    )
    return f"""# fixture

## Audit policy
- risk_tier = {risk}

## Feature
- R-1 = complete operation

## Decision Model
| ID | Decision/default | Alternatives | Selected behavior | Authority | Evidence | Consequences/revisit |
|---|---|---|---|---|---|---|
| D-1 | operation completion default | implicit completion vs explicit terminal result | explicit terminal result | user | user: operation must return a terminal result | revisit if the public workflow changes |

## Flows
- F-1 = queued to terminal

## Contracts
- C-1 = operation owner

## Testing
- T-1 = behavior proof

## Traceability
| ID | Requirement | Decision | Flow/state | Contract/owner | Proof | Telemetry/rollout | Slice |
|---|---|---|---|---|---|---|---|
| TR-1 | R-1 complete operation | D-1 explicit terminal default | F-1 queued to terminal | C-1 operation owner | T-1 behavior proof | bounded status metric | S-1 |

## Failure Model
| ID | Boundary/transition | Failure/interrupt | Durable state | Recovery owner | Retry/timeout | Observable proof |
|---|---|---|---|---|---|---|
{failure}
{guarantee}

## Plan challenge
| Perspective | Scope | Result | Evidence |
|---|---|---|---|
{perspectives}

## Slices
| ID | Outcome |
|---|---|
| S-1 | Complete R-1 |
"""


def check_plan_admission(module, fail) -> None:
    module.validate_plan_admission(fixture())
    module.validate_plan_admission(fixture(risk="standard"))
    module.validate_plan_admission(
        fixture()
        .replace("- risk_tier = critical", "- risk_tier = standard")
        .replace(
            "| owner-first | owners, callers, states | PASS | sha256:" + "a" * 64 + " |\n"
            "| boundary-first | failures, recovery, operations | PASS | sha256:" + "b" * 64 + " |",
            "| complete | full standard-risk plan | PASS | sha256:" + "c" * 64 + " |",
        )
    )

    cases = {
        "missing decision model": fixture().replace("## Decision Model", "## Missing Decisions"),
        "generic user approval": fixture().replace(
            "user: operation must return a terminal result", "user: approve",
        ),
        "untraced decision": fixture().replace(
            "| D-1 | operation completion default",
            "| D-2 | audit visibility default | hidden vs visible | visible | engineering | sha256:"
            + "d" * 64
            + " | revisit if audit ownership changes |\n| D-1 | operation completion default",
        ),
        "hidden requirement": fixture().replace(
            "- R-1 = complete operation", "- R-1 = complete operation\n- R-2 = hidden behavior",
        ),
        "missing traceability": fixture().replace("## Traceability", "## Missing"),
        "placeholder recovery": fixture().replace("reconciler", "TBD"),
        "missing guarantee model": fixture().replace("## Guarantee Model", "## Missing Guarantees"),
        "uncovered failure guarantee": fixture().replace("FM-1 T-1 S-1", "FM-2 T-1 S-1"),
        "membership without immutable high water": fixture().replace("high_water=membershipHighWater; ", ""),
        "membership cutoff can be recaptured": fixture().replace("capture=transactional_once", "capture=repeatable"),
        "membership without indexed query": fixture().replace("query_index=membershipOrderIndex", "query=index"),
        "membership without completion predicate": fixture().replace("completion=cursor_exhausted_at_high_water", "completion=paginate"),
        "identity without exact pagination": fixture().replace("pagination=exhaustive_cursor", "pagination=first_page"),
        "identity without provider permission": fixture().replace("permission=sessions.read; ", ""),
        "identity fail open": fixture().replace("incomplete=deny", "incomplete=allow"),
        "exhaustive without account index": fixture().replace("query_index=accountOwnedRows", "query=index"),
        "exhaustive omits orphans": fixture().replace("orphan=include", "orphan=exclude"),
        "external effect without generation scope": fixture().replace("scope_key=actorGeneration; ", ""),
        "external effect without cleanup": fixture().replace("cleanup=cleanupTombstone; ", ""),
        "external effect activates before drain": fixture().replace("cutover=drain_then_activate", "cutover=activate_then_drain"),
        "irreversible server receipt after request": fixture().replace("capability_owner=client; created_before=request", "capability_owner=server; created_before=response"),
        "lease equals execution envelope": fixture().replace("lease_ms=181001", "lease_ms=180000"),
        "full manifest without baseline": fixture().replace("baseline=sha256:" + "d" * 64, "baseline=scope_digest"),
        "full manifest drops unrelated": fixture().replace("preserve=all_unrelated", "preserve=declared_only"),
        "slice foundation follows consumer": fixture().replace("provider_slice=S-1; consumer_slice=S-1", "provider_slice=S-2; consumer_slice=S-1"),
        "retention asserts row zero": fixture().replace("terminal=retained", "terminal=zero"),
        "reconciliation sends overdue work": fixture().replace("overdue=mark_missed", "overdue=send_late"),
        "reconciliation lacks indexed query": fixture().replace("query_index=actorFutureWork; ", ""),
        "guarantee lacks authority evidence": fixture().replace("evidence=sha256:" + "e" * 64 + "; ", "", 1),
        "untraced proof": fixture().replace("T-1 durable-state assertion", "T-2 durable-state assertion"),
        "critical FM-NA": fixture().replace(
            "| FM-1 | C-1 guarantee transition | dependency rejects after durable commit | queued | reconciler | bounded retry after lease | T-1 durable-state assertion |",
            "| FM-NA | no boundary | no failure | unchanged | owner | timeout | T-1 proof |",
        ),
        "missing boundary challenge": fixture().replace(
            "| boundary-first | failures, recovery, operations | PASS | sha256:" + "b" * 64 + " |\n",
            "",
        ),
        "unbound slice": fixture().replace("| S-1 | Complete R-1 |", "| S-2 | Complete R-1 |"),
        "unowned contract": fixture().replace("- C-1 = operation owner", "- C-2 = operation owner"),
    }
    for label, text in cases.items():
        try:
            module.validate_plan_admission(text)
        except module.PlanStateError:
            continue
        fail(f"plan admission accepted {label}")
