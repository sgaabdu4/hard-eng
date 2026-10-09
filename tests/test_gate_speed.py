"""Checks avoid waiting: scans start early, hung gates stop early, proven changes skip setup."""

import json
import time
from pathlib import Path
from types import ModuleType

import pytest
from ci_setup import migrate_impact_token
from conftest import SOURCE, commit, configure, gate, load_module


def test_a_hung_gate_stops_at_three_times_its_last_passing_time(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shipping

    monkeypatch.setattr(shipping, "GATE_FLOOR_SECONDS", 1)
    configure(tmp_path, [gate("suite", "pass")])
    assert runner.check(timeout=120) == 0
    times = json.loads((tmp_path / ".git/hard-eng-gate-times.json").read_text())
    assert set(times) == {"./suite"}
    configure(tmp_path, [gate("suite", "import time; time.sleep(60)")])
    started = time.monotonic()
    assert runner.check(timeout=120) == 1
    assert time.monotonic() - started < 30


def test_scans_start_beside_a_serial_suite_listed_before_them(
    runner: ModuleType, tmp_path: Path
) -> None:
    wait = (
        "from pathlib import Path;import time;end = time.monotonic() + 10\n"
        "Path('{mine}').touch()\n"
        "while not Path('{other}').exists(): assert time.monotonic() < end; time.sleep(0.02)"
    )
    suite = gate("suite", wait.format(mine="suite-running", other="scan-running"))
    scan = gate(
        "scan",
        wait.format(mine="scan-running", other="suite-running"),
        role="shell",
        parallel=True,
    )
    configure(tmp_path, [suite, scan])
    assert runner.check() == 0


def test_impact_takes_the_fast_path_when_the_change_is_already_proven(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [{"path": ".", "checks": []}], "shared": []})
    )
    commit(repository, "configure")
    (repository / "app.py").write_text("change\n")
    module = load_module("impact_runner", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = repository

    def proven(base: str | None) -> bool:
        print(f"proven against {base}")
        return True

    module.__dict__["proven_elsewhere"] = proven
    assert module.impact("HEAD") == 0
    captured = capsys.readouterr()
    assert captured.out == "docs_only=true\n"
    assert "proven against HEAD" in captured.err


def test_old_impact_step_gains_the_token_its_reuse_lookup_needs() -> None:
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    token = "          GH_TOKEN: ${{ github.token }}\n"
    start = template.index("id: impact")
    old = template[:start] + template[start:].replace(token, "", 1)
    assert old != template
    assert migrate_impact_token(old) == template
    assert migrate_impact_token(template) == template
