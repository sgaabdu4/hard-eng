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
    def scheduled(index, _scope):
        nonlocal active, peak
        with lock:
            events.append(f"start-{index}")
            active += 1
            peak = max(peak, active)
        time.sleep(0.03 if index == 1 else 0.06)
        with lock:
            active -= 1
            events.append(f"end-{index}")
        return index
    results = module.warm_then_parallel(("a", "b", "c", "d"), scheduled, 3)
    if (results != [1, 2, 3, 4] or peak < 2
            or events.index("end-1") > events.index("start-2")):
        fail("audit did not warm one stable prefix before ordered parallel review")
