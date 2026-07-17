#!/usr/bin/env python3
"""Regression proof for attributable audit-child failures."""

from __future__ import annotations

import json
import sys


def check_audit_failure_diagnostics(module, fail) -> None:
    reasons = []
    attempts = []

    def zero_item_exit():
        attempts.append(1)
        raise module.RetryableAuditError(
            "AUDIT_CHILD_EXIT: exit=1 completed_items=0 error_events=1 usage=missing"
        )

    try:
        module.one_infrastructure_retry(
            zero_item_exit, module.RetryableAuditError, reasons.append,
        )
    except module.RetryableAuditError as error:
        message = str(error)
    else:
        fail("two zero-item child exits did not exhaust the bounded retry")
        return
    if (len(attempts) != 2 or reasons != ["child-process-exit"]
            or "AUDIT_RETRY_EXHAUSTED" not in message
            or "first=child-process-exit" not in message
            or "second=child-process-exit" not in message):
        fail("audit retry exhaustion lost attributable attempt reasons")

    state = module.new_event_state()
    module.consume_event(json.dumps({
        "type": "item.completed", "item": {"type": "error"},
    }), state, emit_progress=False)
    if state.error_events != 1 or state.completed_items != 0:
        fail("child error-event accounting changed completed-review evidence")
    zero_detail = module.child_failure_detail(
        1, state.completed_items, state.error_events, state.usage is not None,
    )
    if not all(part in zero_detail for part in (
        "AUDIT_CHILD_EXIT", "exit=1", "completed_items=0",
        "error_events=1", "usage=missing",
    )):
        fail("zero-item child exit omitted structured failure provenance")

    module.consume_event(json.dumps({
        "type": "item.completed", "item": {"type": "agent_message"},
    }), state, emit_progress=False)
    completed_detail = module.child_failure_detail(
        1, state.completed_items, state.error_events, state.usage is not None,
    )
    if "completed_items=1" not in completed_detail:
        fail("completed child exit cannot be distinguished from zero-item transport failure")

    def child_exit(item_type: str):
        script = (
            "import json,sys;sys.stdin.read();"
            f"print(json.dumps({{'type':'item.completed','item':{{'type':'{item_type}'}}}}),flush=True);"
            "raise SystemExit(1)"
        )
        return module.run_codex_stream([sys.executable, "-c", script], "packet", 5)

    try:
        child_exit("error")
    except module.RetryableAuditError as error:
        if not all(part in str(error) for part in (
            "AUDIT_CHILD_EXIT", "completed_items=0", "error_events=1",
        )):
            fail("real zero-item child exit lost its structured retry evidence")
    else:
        fail("real zero-item child exit was not retry-qualified")
    try:
        child_exit("agent_message")
    except module.AuditError as error:
        if isinstance(error, module.RetryableAuditError) or "completed_items=1" not in str(error):
            fail("real completed child exit lost its non-retry evidence")
    else:
        fail("real completed child exit was accepted as clean")
