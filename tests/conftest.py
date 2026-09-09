"""Load the actual installed-script entry points without invoking their CLI."""

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

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
def runner(tmp_path: Path) -> ModuleType:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    module = load_module("runner", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = tmp_path
    for name in ("PRODUCT.md", "DESIGN.md"):
        (tmp_path / name).write_text((SOURCE / name).read_text())
    return module
