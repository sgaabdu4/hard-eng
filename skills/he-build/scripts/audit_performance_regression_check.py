#!/usr/bin/env python3
"""Synthetic regressions for token-stable, bounded-parallel final audit."""
from __future__ import annotations

import threading
import time


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
            or peak != 2
            or events.index("end-1") > events.index("start-2")
            or events.index("end-2") > events.index("start-3")
            or schedule != {
                "cacheProven": True, "serialProbeCount": 2, "parallelWorkerCount": 2,
            }):
        fail("audit fan-out occurred before a measured cache hit")

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
    if (peak != 1 or len(cold_events) != 3 or cold_schedule != {
            "cacheProven": False, "serialProbeCount": 3, "parallelWorkerCount": 1,
    } or [result["index"] for result in cold_results] != [1, 2, 3]):
        fail("audit parallelized without measured cache reuse")

    metrics = module.audit_performance_metrics(
        [
            {"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 10},
            {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 20,
             "reasoning_output_tokens": 5},
        ],
        elapsed_ms=321, shard_count=2, common_prefix_bytes=4096,
        schedule={"cacheProven": True, "serialProbeCount": 2, "parallelWorkerCount": 1},
    )
    if metrics != {
        "elapsedMs": 321, "shardCount": 2, "commonPrefixBytes": 4096,
        "cacheHitBasisPoints": 2500, "uncachedInputTokens": 150,
        "outputTokens": 30, "reasoningOutputTokens": 5,
        "cacheProven": True, "serialProbeCount": 2, "parallelWorkerCount": 1,
    }:
        fail("audit performance receipt lost token or scheduling evidence")
