#!/usr/bin/env python3
import sys
import tempfile
from pathlib import Path

from operating_contracts import FORBIDDEN, REQUIRED

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/operating_contracts.py"
sys.path[:0] = [str(ROOT / "skills/deterministic-checks/scripts")]

from script_runner import ScriptResult, run_script

FIXTURES = ROOT / "scripts/test_fixtures/operating-contracts"


def run(root: Path) -> ScriptResult:
    return run_script(CHECKER, [str(root)])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"operating-contracts-regression: {message}")


require(run(ROOT).returncode == 0, "canonical repository failed")
require(run(FIXTURES / "valid").returncode == 0, "valid fixture failed")
require(run(FIXTURES / "violation").returncode != 0, "violation fixture passed")

owners = sorted(set(REQUIRED) | set(FORBIDDEN))


def copy_valid(root: Path) -> None:
    for relative in owners:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((FIXTURES / "valid" / relative).read_text())


for relative, anchors in REQUIRED.items():
    text = (FIXTURES / "valid" / relative).read_text()
    for index, anchor in enumerate(anchors):
        mutated = text.replace(anchor, f"removed-anchor-{index}", 1)
        with tempfile.TemporaryDirectory(prefix="operating-contracts-mutant-") as directory:
            temporary = Path(directory)
            copy_valid(temporary)
            (temporary / relative).write_text(mutated)
            require(run(temporary).returncode != 0, f"missing anchor passed: {anchor}")

for relative, forbidden_terms in FORBIDDEN.items():
    for forbidden in forbidden_terms:
        with tempfile.TemporaryDirectory(prefix="operating-contracts-mutant-") as directory:
            temporary = Path(directory)
            copy_valid(temporary)
            target = temporary / relative
            target.write_text(target.read_text() + f"\n{forbidden}\n")
            require(run(temporary).returncode != 0, f"forbidden term passed: {forbidden}")

print("operating-contracts-regression: PASS")
