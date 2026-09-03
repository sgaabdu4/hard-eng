import importlib.util
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regressions import ROOT

RUNNER_DIR = ROOT / "skills" / "deterministic-checks" / "scripts"
if str(RUNNER_DIR) not in sys.path:
    sys.path.insert(0, str(RUNNER_DIR))


def load_runner():
    name = "skills.deterministic-checks.scripts.script_runner"
    spec = importlib.util.spec_from_file_location(name, RUNNER_DIR / "script_runner.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    sys.modules["script_runner"] = module
    spec.loader.exec_module(module)
    return module


script_runner = load_runner()


@pytest.fixture(autouse=True, scope="session")
def in_process_seam():
    os.environ[script_runner.INPROCESS_FLAG] = "1"
    script_runner.install_finder()
    script_runner.install_child_guard()
