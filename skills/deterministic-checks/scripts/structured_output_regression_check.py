#!/usr/bin/env python3
"""Behavioral fixtures for strict external-tool structured-output channels."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import NoReturn


class AmbiguousOutput(ValueError):
    pass


def fail(message: str) -> NoReturn:
    raise SystemExit(f"structured-output-regressions: FAIL: {message}")


def parse_machine_channel(payload: bytes) -> dict[str, object] | list[object]:
    try:
        text = payload.decode("utf-8", errors="strict")
        value = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AmbiguousOutput("channel is not exactly one JSON document") from error
    if not isinstance(value, (dict, list)):
        raise AmbiguousOutput("channel JSON must be structured")
    return value


def legacy_first_delimiter(payload: bytes) -> object:
    text = payload.decode("utf-8")
    starts = [offset for marker in ("{", "[") if (offset := text.find(marker)) >= 0]
    if not starts:
        raise AmbiguousOutput("no inferred JSON start")
    return json.loads(text[min(starts) :])


def expect_rejected(label: str, payload: bytes) -> None:
    try:
        parse_machine_channel(payload)
    except AmbiguousOutput:
        return
    fail(f"{label} was accepted as a machine-only channel")


def check_valid_channels() -> None:
    stdout = b'\n[{"status":"ok"}]\n'
    if parse_machine_channel(stdout) != [{"status": "ok"}]:
        fail("machine-only stdout did not parse")
    with tempfile.TemporaryDirectory() as name:
        output = Path(name) / "result.json"
        output.write_bytes(b'{"status":"ok"}')
        if parse_machine_channel(output.read_bytes()) != {"status": "ok"}:
            fail("dedicated output file did not parse")


def check_mixed_output_rejected() -> None:
    fixtures = {
        "ANSI log": b'\x1b[33mwarning\x1b[0m\n[{"status":"ok"}]',
        "warning": b'warning: cached metadata is stale\n[{"status":"ok"}]',
        "version/update banner": (
            b'tool v11.17.0\nupdate available: v11.18.0\n[{"status":"ok"}]'
        ),
        "bracketed prefix": b'[notice] resolving dependencies\n[{"status":"ok"}]',
        "trailing noise": b'[{"status":"ok"}]\ncompleted successfully',
        "brace in human log": (
            b'warning: ignored settings {cache}\n{"status":"ok"}'
        ),
    }
    for label, payload in fixtures.items():
        expect_rejected(label, payload)

    for label in ("warning", "version/update banner"):
        if legacy_first_delimiter(fixtures[label]) != [{"status": "ok"}]:
            fail(f"{label} did not reproduce first-delimiter false acceptance")


def main() -> None:
    check_valid_channels()
    check_mixed_output_rejected()
    print("structured-output-regressions: PASS")


if __name__ == "__main__":
    main()
