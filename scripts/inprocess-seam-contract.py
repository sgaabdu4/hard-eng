#!/usr/bin/env python3
"""Every regression starts repository scripts through script_runner.run_script, so mutation testing can see them."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECT_SPAWN = re.compile(r"sys\.executable,\s*str\(")
ALLOWED = {
    "skills/deterministic-checks/scripts/script_runner_regression_check.py": "proves the guard by spawning directly",
    "skills/adversarial-review/scripts/run_review_regression.py": "runner lives outside the measured script directories",
    "skills/he-learn/scripts/learning_state_regression.py": "tool lives outside the measured script directories",
}


def regressions() -> list[Path]:
    found = []
    for base in (ROOT / "skills", ROOT / "scripts"):
        found += [path for path in base.rglob("*.py") if "regression" in path.name and "node_modules" not in path.parts]
    return sorted(found)


def main() -> int:
    offenders = []
    for path in regressions():
        relative = path.relative_to(ROOT).as_posix()
        if relative in ALLOWED:
            continue
        if DIRECT_SPAWN.search(path.read_text(encoding="utf-8")):
            offenders.append(relative)
    if offenders:
        print(
            "inprocess-seam-contract: FAIL: regressions start a repository script directly; use run_script or spawn_script:"
        )
        for relative in offenders:
            print(f"  {relative}")
        return 1
    print(f"inprocess-seam-contract: PASS ({len(regressions())} regressions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
