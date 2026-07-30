#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

from operating_contracts import REQUIRED


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/operating_contracts.py"
FIXTURES = ROOT / "scripts/test_fixtures/operating-contracts"


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (sys.executable, str(CHECKER), str(root)),
        capture_output=True,
        text=True,
        check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"operating-contracts-regression: {message}")


require(run(ROOT).returncode == 0, "canonical repository failed")
require(run(FIXTURES / "valid").returncode == 0, "valid fixture failed")
require(run(FIXTURES / "violation").returncode != 0, "violation fixture passed")

for relative, anchors in REQUIRED.items():
    text = (FIXTURES / "valid" / relative).read_text()
    for index, anchor in enumerate(anchors):
        mutated = text.replace(anchor, f"removed-anchor-{index}", 1)
        temporary = FIXTURES / ".mutant"
        target = temporary / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(mutated)
        for other_relative in REQUIRED:
            if other_relative == relative:
                continue
            other_target = temporary / other_relative
            other_target.parent.mkdir(parents=True, exist_ok=True)
            other_target.write_text((FIXTURES / "valid" / other_relative).read_text())
        require(run(temporary).returncode != 0, f"missing anchor passed: {anchor}")

for path in sorted((FIXTURES / ".mutant").rglob("*"), reverse=True):
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        path.rmdir()
(FIXTURES / ".mutant").rmdir()

print("operating-contracts-regression: PASS")
