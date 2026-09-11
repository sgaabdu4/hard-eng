"""Load the actual installed-script entry points without invoking their CLI."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from shipping import ShippingPolicy

SOURCE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SOURCE / ".hooks"))


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def installer() -> ModuleType:
    return load_module("installer", SOURCE / "setup.py")


@pytest.fixture
def completed_plan() -> str:
    return """# Fixture command behavior
Status: Complete
## Outcome + scope
Verify fixture command exits; no product release.
## Repository context
The test creates commands in a temporary Git repository.
## Decisions + authorization
Blockers: None
Authorized test fixture; no external actions.
## Acceptance + steps
- [x] Observe the configured command exit.
## Baseline + execution
Result: Passed
Evidence: Controlled fixture baseline; not production acceptance.
One test actor.
## Risks + recovery
N/A — temporary fixture is removed by pytest.
## ux_reference
N/A — fixture commands have no visual interface.
## Verification
Result: Passed
Evidence: The test asserts the observed command exit; this is fixture data.
"""


@pytest.fixture
def runner(tmp_path: Path, completed_plan: str) -> ModuleType:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    module = load_module("runner", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = tmp_path
    (tmp_path / "PLAN.md").write_text(completed_plan)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (tmp_path / name).write_text((SOURCE / name).read_text())
    return module


@pytest.fixture
def shipping_policy() -> "ShippingPolicy":
    return {
        "base": "main",
        "checks": ["hard-eng"],
        "ui_paths": [],
        "ci_seconds": 180.0,
        "pre_push_seconds": 180.0,
        "delivery": [],
    }
