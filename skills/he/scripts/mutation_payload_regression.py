#!/usr/bin/env python3
"""Regression: the mutation payload helper reads mutmut results faithfully and refuses incomplete or unexplained runs."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"), str(SCRIPT_DIR)]

from script_runner import run_script

HELPER = SCRIPT_DIR / "mutation_payload.py"
SCOPE = "skills/he/scripts/example.py"
KEY = "skills.he.scripts.example.x_fn__mutmut_"


def fail(label: str) -> None:
    print(f"mutation-payload regression: FAIL ({label})")
    raise SystemExit(1)


def write_meta(results: Path, codes: dict[str, int | None], scope: str = SCOPE) -> None:
    path = results / f"{scope}.meta"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"exit_code_by_key": codes}), encoding="utf-8")


def run(results: Path, *extra: str, scope: str = SCOPE) -> tuple[int, str, str]:
    args = ["--results", str(results), "--scope", scope, "--version", "3.7.0", *extra, "mutmut", "run"]
    result = run_script(HELPER, args)
    return result.returncode, result.stdout, result.stderr


def check_statuses(base: Path) -> None:
    results = base / "complete"
    write_meta(results, {KEY + "1": 1, KEY + "2": 3, KEY + "3": 37, KEY + "4": 36, KEY + "5": 5, KEY + "6": 34})
    code, out, err = run(results)
    if code != 0:
        fail(f"complete run should build: {err}")
    payload = json.loads(out)
    if payload["totals"] != {"killed": 3, "survived": 0, "timeout": 1, "no_coverage": 1}:
        fail(f"totals: {payload['totals']}")
    if payload["scope"] != [SCOPE] or payload["argv"] != ["mutmut", "run"] or payload["version"] != "3.7.0":
        fail("scope, argv, or version not carried through")
    write_meta(results, {KEY + "1": 99})
    code, _, err = run(results)
    if code == 0 or KEY + "1" not in err:
        fail("unknown exit code must be refused by name")


def check_survivors(base: Path) -> None:
    results = base / "survivors"
    write_meta(results, {KEY + "1": 0, KEY + "2": 1})
    code, _, err = run(results)
    if code == 0 or KEY + "1" not in err:
        fail("survivor without disposition must be refused by name")
    rows = base / "rows.json"
    rows.write_text(
        json.dumps({KEY + "1": {"disposition": "deferred", "reason": "log text", "consequence": "none"}}),
        encoding="utf-8",
    )
    code, out, _ = run(results, "--dispositions", str(rows))
    if code != 0:
        fail("survivor with a row must build")
    rows.write_text(json.dumps({KEY + "1": {"disposition": "equivalent", "reason": 3}}), encoding="utf-8")
    code, _, err = run(results, "--dispositions", str(rows))
    if code == 0 or "needs disposition and reason" not in err:
        fail("row without a text reason must be refused")
    rows.write_text("[]", encoding="utf-8")
    code, _, err = run(results, "--dispositions", str(rows))
    if code == 0 or "must map" not in err:
        fail("dispositions list instead of map must be refused")
    payload = json.loads(out)
    if payload["totals"]["survived"] != 1 or payload["survivors"][0]["consequence"] != "none":
        fail(f"survivor ledger: {payload['survivors']}")


def check_incomplete(base: Path) -> None:
    results = base / "incomplete"
    code, _, err = run(results)
    if code == 0 or SCOPE not in err:
        fail("missing meta must name the scope file")
    write_meta(results, {})
    code, _, err = run(results)
    if code == 0 or "no mutant results" not in err:
        fail("empty meta must be refused")
    write_meta(results, {KEY + "1": 1, KEY + "2": None})
    code, _, err = run(results)
    if code == 0 or "not checked" not in err:
        fail("pending mutant must be refused")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mutation-payload-") as directory:
        base = Path(directory)
        check_statuses(base)
        check_survivors(base)
        check_incomplete(base)
    print("mutation-payload regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
