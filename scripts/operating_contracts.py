#!/usr/bin/env python3
from pathlib import Path
import sys


REQUIRED = {
    "AGENTS.md": (
        "Explicit `fix all|everything|done/no regressions` scope = closure ledger",
        "`pre-existing` = provenance, never exclusion",
        "Workflow topology change = inventory last-green required stages",
        "Proof ladder = local/static + current primary contract",
        "Execution graph = dependency DAG",
        "Alignment latency = one dependency frontier per turn",
        "`done|no regressions` claim = closure ledger empty",
    ),
    "skills/question-me/SKILL.md": (
        "Question cadence = one dependency frontier per turn",
        "batch every mutually independent material decision",
    ),
    "skills/research/SKILL.md": (
        "First paid/native/external attempt = current primary-source receipt",
        "Contract-surprise failure = pause retry",
    ),
}


def validate(root: Path) -> list[str]:
    failures: list[str] = []
    for relative, anchors in REQUIRED.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"missing {relative}")
            continue
        text = path.read_text()
        for anchor in anchors:
            if anchor not in text:
                failures.append(f"{relative} missing: {anchor}")
    return failures


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    failures = validate(root)
    if failures:
        for failure in failures:
            print(f"operating-contracts: FAIL: {failure}", file=sys.stderr)
        return 1
    print("operating-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
