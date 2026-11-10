import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import SOURCE, gate, gone

LAUNCHER = """
import importlib.util, sys
from pathlib import Path
hooks = Path(sys.argv[1])
sys.path.insert(0, str(hooks))
import gate_config
gate_config.validate_required_checks = lambda *arguments: None
spec = importlib.util.spec_from_file_location("runner", hooks / "hard-eng.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.ROOT = hooks.parent
sys.argv = ["hard-eng.py", "check"]
raise SystemExit(module.main())
"""

SLOW_GATE = """
import os, pathlib, time
pathlib.Path(os.environ["MARKER"]).write_text(str(os.getpid()))
time.sleep(60)
"""


@pytest.mark.parametrize("signal_number", [signal.SIGTERM, signal.SIGHUP])
def test_a_stopped_check_stops_its_gates(
    tmp_path: Path, completed_plan: str, signal_number: int
) -> None:
    marker, project = tmp_path / "gate.pid", tmp_path / "project"
    hooks = project / ".hooks"
    hooks.mkdir(parents=True)
    for source in (SOURCE / ".hooks").glob("*.py"):
        (hooks / source.name).write_bytes(source.read_bytes())
    (tmp_path / "launcher.py").write_text(LAUNCHER)
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "PLAN.md").write_text(completed_plan)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (project / name).write_text((SOURCE / name).read_text())
    slow = gate("slow", SLOW_GATE, role="custom", parallel=True)
    (project / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [slow]})
    )
    check = subprocess.Popen(
        [sys.executable, str(tmp_path / "launcher.py"), str(hooks)],
        cwd=project,
        env={**os.environ, "MARKER": str(marker)},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 60
    while not (marker.exists() and marker.read_text()):
        assert time.monotonic() < deadline, "gate did not start"
        time.sleep(0.05)
    check.send_signal(signal_number)
    check.wait(timeout=30)
    stopped = gone(marker)
    if not stopped:
        os.kill(int(marker.read_text()), signal.SIGKILL)
    assert stopped, "the gate kept running after the check was stopped"
