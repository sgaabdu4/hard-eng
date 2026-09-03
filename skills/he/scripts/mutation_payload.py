#!/usr/bin/env python3
"""Turn a finished mutmut run into the record-mutation payload so totals and survivor keys are never typed by hand."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KILLED = {1, 3, 37}
SURVIVED = {0}
NO_COVERAGE = {5, 33}
TIMEOUT = {36, 24, -24, 152, 255}
SKIPPED = {34}
DISPOSITION_KEYS = ("disposition", "reason", "consequence")


class MutationPayloadError(Exception):
    """The run is incomplete or a survivor has no disposition."""


def meta_path(results: Path, scope_file: str) -> Path:
    return results / f"{scope_file}.meta"


def exit_codes(results: Path, scope_file: str) -> dict[str, int | None]:
    path = meta_path(results, scope_file)
    if not path.is_file():
        raise MutationPayloadError(f"{scope_file} was never mutated: {path} is missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise MutationPayloadError(f"{path} is unreadable: {error}") from error
    codes = data.get("exit_code_by_key") if isinstance(data, dict) else None
    if not isinstance(codes, dict) or not codes:
        raise MutationPayloadError(f"{path} carries no mutant results")
    return {str(key): value for key, value in codes.items()}


def classify(scope_file: str, key: str, code: int | None) -> str:
    if code is None:
        raise MutationPayloadError(f"{scope_file}: {key} was not checked; finish the run first")
    if code in KILLED:
        return "killed"
    if code in SURVIVED:
        return "survived"
    if code in NO_COVERAGE:
        return "no_coverage"
    if code in TIMEOUT:
        return "timeout"
    if code in SKIPPED:
        return "skipped"
    raise MutationPayloadError(f"{scope_file}: {key} ended with exit code {code}; rerun that mutant")


def survivor_row(key: str, dispositions: dict[str, object]) -> dict[str, str]:
    row = dispositions.get(key)
    if not isinstance(row, dict):
        raise MutationPayloadError(f"survivor {key} has no disposition; add it to the dispositions file")
    entry = {"mutant": key}
    for field in DISPOSITION_KEYS:
        value = row.get(field)
        if isinstance(value, str) and value.strip():
            entry[field] = value.strip()
    if "disposition" not in entry or "reason" not in entry:
        raise MutationPayloadError(f"survivor {key} needs disposition and reason")
    return entry


def build(
    results: Path, scope: list[str], dispositions: dict[str, object], *, version: str, argv: list[str]
) -> dict[str, object]:
    totals = {"killed": 0, "survived": 0, "timeout": 0, "no_coverage": 0}
    survivors: list[dict[str, str]] = []
    for scope_file in scope:
        for key, code in sorted(exit_codes(results, scope_file).items()):
            status = classify(scope_file, key, code)
            if status == "skipped":
                continue
            totals[status] += 1
            if status == "survived":
                survivors.append(survivor_row(key, dispositions))
    return {
        "runner": "mutmut",
        "version": version,
        "argv": argv,
        "scope": sorted(set(scope)),
        "totals": totals,
        "survivors": survivors,
    }


def load_dispositions(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise MutationPayloadError(f"dispositions file is unreadable: {error}") from error
    if not isinstance(data, dict):
        raise MutationPayloadError("dispositions file must map mutant keys to rows")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("mutants"))
    parser.add_argument("--scope", action="append", required=True, help="repository-relative source file")
    parser.add_argument("--dispositions", type=Path, help="JSON: mutant key -> disposition, reason, consequence")
    parser.add_argument("--version", required=True, help="runner version as printed by mutmut version")
    parser.add_argument("argv", nargs="+", help="exact mutmut command after --")
    options = parser.parse_args()
    try:
        payload = build(
            options.results,
            options.scope,
            load_dispositions(options.dispositions),
            version=options.version,
            argv=options.argv,
        )
    except MutationPayloadError as error:
        print(f"mutation-payload: FAIL {error}", file=sys.stderr)
        return 1
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
