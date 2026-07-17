#!/usr/bin/env python3
"""Synthetic regressions for token-stable, bounded-parallel final audit."""
from __future__ import annotations
import sys
import threading
import time

import audit_runtime


def check_audit_performance_regressions(module, fail) -> None:
    snapshot = "sha256:" + "0" * 64
    digest = "sha256:" + "0" * 64
    first = module.audit_prompt(snapshot, digest, "packet")
    second = module.audit_prompt(
        snapshot, digest, "packet-two", shard_index=2, shard_count=3,
    )
    if ("Complete coverage shard = 1/1" not in first
            or "Complete coverage shard = 2/3" not in second
            or "assigned exactly once" not in first
            or first.split("<review-packet>\n", 1)[0]
            != second.split("<review-packet>\n", 1)[0]):
        fail("audit shards lost exact binding or stable cacheable prompt prefix")

    events = []
    active = 0
    peak = 0
    lock = threading.Lock()
    cache = {1: 0, 2: 64, 3: 64, 4: 64}
    def scheduled(index, _scope):
        nonlocal active, peak
        with lock:
            events.append(f"start-{index}")
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
            events.append(f"end-{index}")
        return {"index": index, "cached_input_tokens": cache[index]}
    results, schedule = module.warm_then_parallel(
        ("a", "b", "c", "d"), scheduled,
        lambda result: result["cached_input_tokens"], 3,
    )
    if ([result["index"] for result in results] != [1, 2, 3, 4]
            or peak != 3
            or events.index("end-1") > events.index("start-2")
            or schedule != {
                "cacheProven": True, "serialProbeCount": 1, "parallelWorkerCount": 3,
            }):
        fail("audit did not preserve one warm shard plus ordered bounded fan-out")

    peak = 0
    active = 0
    cold_events = []
    def cold(index, _scope):
        nonlocal active, peak
        with lock:
            cold_events.append(f"start-{index}")
            active += 1
            peak = max(peak, active)
        time.sleep(0.005)
        with lock:
            active -= 1
        return {"index": index, "cached_input_tokens": 0}
    cold_results, cold_schedule = module.warm_then_parallel(
        ("a", "b", "c"), cold, lambda result: result["cached_input_tokens"], 3,
    )
    if (peak != 2 or len(cold_events) != 3 or cold_schedule != {
            "cacheProven": False, "serialProbeCount": 1, "parallelWorkerCount": 2,
    } or [result["index"] for result in cold_results] != [1, 2, 3]):
        fail("zero cache metric serialized correctness-independent audit shards")

    variable_active = 0
    variable_peak = 0
    def variable(index, _scope):
        nonlocal variable_active, variable_peak
        with lock:
            variable_active += 1
            variable_peak = max(variable_peak, variable_active)
        time.sleep(0.001 if index == 1 else 1.1)
        with lock:
            variable_active -= 1
        return {"index": index, "cached_input_tokens": 0}
    variable_started = time.monotonic()
    variable_results, variable_schedule = module.warm_then_parallel(
        tuple("abcdefg"), variable, lambda result: result["cached_input_tokens"], 4,
        deadline=variable_started + 36.1,
    )
    if ([result["index"] for result in variable_results] != list(range(1, 8))
            or variable_peak < 2 or variable_schedule["parallelWorkerCount"] < 2
            or time.monotonic() - variable_started > 5.5):
        fail("fast warm latency permanently under-provisioned the worker pool")
    if audit_runtime.whole_run_deadline(100, 3600) != 3700:
        fail("packetization time was excluded from the whole-run deadline")

    urgent_workers = audit_runtime.deadline_workers(
        remaining_shards=9, warm_elapsed_s=60, remaining_s=3540,
        latency_remaining_s=240, max_workers=8,
    )
    ordinary_workers = audit_runtime.deadline_workers(
        remaining_shards=9, warm_elapsed_s=60, remaining_s=3540, max_workers=8,
    )
    if urgent_workers <= 1 or urgent_workers > 8 or ordinary_workers != 1:
        fail("latency objective did not accelerate urgent work or changed ordinary scheduling")

    required = audit_runtime.deadline_workers(
        remaining_shards=80, warm_elapsed_s=220, remaining_s=3380, max_workers=8,
    )
    if required != 7:
        fail("deadline capacity did not select the smallest feasible bounded worker count")
    try:
        audit_runtime.deadline_workers(
            remaining_shards=80, warm_elapsed_s=220, remaining_s=2700, max_workers=6,
        )
    except module.AuditError as error:
        if "AUDIT_DEADLINE_INFEASIBLE" not in str(error):
            fail("deadline capacity returned an unstructured failure")
    else:
        fail("deadline-infeasible audit launched remaining shards")
    launched = []
    try:
        module.warm_then_parallel(
            ("a", "b"),
            lambda index, _scope: launched.append(index) or {"cached_input_tokens": 0},
            lambda result: result["cached_input_tokens"], 1,
            deadline=time.monotonic() + 1,
        )
    except module.AuditError as error:
        if "AUDIT_DEADLINE_INFEASIBLE" not in str(error) or launched != [1]:
            fail("deadline rejection lost its cause or launched remaining shards")
    else:
        fail("scheduler ignored its deadline capacity admission")

    cancelled = threading.Event()
    def interrupted(index, _scope):
        if index == 1:
            return {"index": index, "cached_input_tokens": 0}
        if index == 2:
            time.sleep(0.01)
            raise module.AuditError("worker failed")
        cancelled.wait(1)
        return {"index": index, "cached_input_tokens": 0}
    try:
        module.warm_then_parallel(
            ("a", "b", "c", "d"), interrupted,
            lambda result: result["cached_input_tokens"], 3, cancel=cancelled.set,
        )
    except module.AuditError as error:
        if str(error) != "worker failed" or not cancelled.is_set():
            fail("peer failure lost its cause or cancellation signal")
    else:
        fail("peer worker failure produced a partial aggregate")

    transport_cancelled = threading.Event()
    timer = threading.Timer(0.05, transport_cancelled.set)
    timer.start()
    started = time.monotonic()
    try:
        module.run_codex_stream(
            [sys.executable, "-c", "import time; time.sleep(10)"], "packet", 5,
            cancelled=transport_cancelled,
        )
    except module.AuditError as error:
        if "cancelled after peer failure" not in str(error) or time.monotonic() - started > 2:
            fail("peer cancellation did not promptly stop its audit transport")
    else:
        fail("cancelled audit transport remained alive")
    finally:
        timer.cancel()

    metrics = module.audit_performance_metrics(
        [
            {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 10},
            {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 20,
             "reasoning_output_tokens": 5},
        ],
        elapsed_ms=321, shard_count=2, common_prefix_bytes=4096,
        schedule={"cacheProven": True, "serialProbeCount": 2, "parallelWorkerCount": 1,
                  "latencyProfile": "urgent", "latencyTargetMs": 300000},
    )
    if metrics != {
        "elapsedMs": 321, "shardCount": 2, "commonPrefixBytes": 4096,
        "cacheHitBasisPoints": 2500, "uncachedInputTokens": 150,
        "outputTokens": 30, "reasoningOutputTokens": 5,
        "cacheProven": True, "serialProbeCount": 2, "parallelWorkerCount": 1,
        "latencyProfile": "urgent", "latencyTargetMs": 300000,
    }:
        fail("audit performance receipt lost token or scheduling evidence")
