"""Checks avoid waiting: scans start early, hung gates stop early, proven changes skip setup."""

import json
import time
from concurrent.futures import Future
from pathlib import Path
from types import ModuleType

import pytest
from ci_setup import migrate_impact_token
from conftest import SOURCE, commit, configure, gate, load_module
from gate_config import Gate, Group
from reports import scan_blockers


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
    suite = gate(
        "suite",
        wait.format(mine="suite-running", other="scan-running"),
        role="complexity",
    )
    scan = gate(
        "scan",
        wait.format(mine="scan-running", other="suite-running"),
        role="shell",
        parallel=True,
    )
    configure(tmp_path, [suite, scan])
    assert runner.check() == 0


def test_scans_still_read_what_a_serial_generator_produced(
    runner: ModuleType, tmp_path: Path
) -> None:
    generator = gate(
        "generate",
        "from pathlib import Path;import time;time.sleep(0.5);Path('generated').touch()",
        role="codegen",
    )
    scan = gate(
        "scan",
        "from pathlib import Path;assert Path('generated').exists()",
        role="shell",
        parallel=True,
    )
    configure(tmp_path, [generator, scan])
    assert runner.check() == 0


def test_performance_suites_still_run_alone_after_early_scans(
    runner: ModuleType, tmp_path: Path
) -> None:
    scan = gate(
        "scan",
        "from pathlib import Path;import time;Path('scanning').touch();time.sleep(1);Path('scanning').unlink()",
        role="shell",
        parallel=True,
    )
    suite = gate(
        "performance",
        "from pathlib import Path;assert not Path('scanning').exists()\n"
        "Path('perf.xml').write_text('<testsuite tests=\"1\"><testcase name=\"t\"/></testsuite>')",
        role="performance",
        report={"type": "performance-junit", "path": "perf.xml"},
    )
    configure(tmp_path, [suite, scan])
    assert runner.check() == 0


def changed_project(repository: Path) -> ModuleType:
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [{"path": ".", "checks": []}], "shared": []})
    )
    commit(repository, "configure")
    (repository / "app.py").write_text("change\n")
    module = load_module("impact_runner", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = repository
    return module


def test_impact_takes_the_fast_path_when_the_change_is_already_proven(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = changed_project(repository)

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


def test_impact_keeps_the_normal_path_when_the_reuse_probe_cannot_run(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = changed_project(repository)

    def missing_uv(base: str | None) -> bool:
        raise FileNotFoundError(f"uv is not installed yet for {base}")

    module.__dict__["proven_elsewhere"] = missing_uv
    assert module.impact("HEAD") == 0
    assert capsys.readouterr().out.startswith("docs_only=false\ntools=")


def test_a_suite_waits_only_for_scans_its_cleanup_or_timing_could_disturb() -> None:
    root, web = Future[bool](), Future[bool]()
    scans = {root: ".", web: "web"}
    javascript: Group = {"path": ".", "language": "javascript", "checks": []}
    python: Group = {"path": ".", "language": "python", "checks": []}
    tests: Gate = {"name": "tests", "role": "tests", "command": ["x"]}
    performance: Gate = {"name": "performance", "role": "performance", "command": ["x"]}
    assert scan_blockers(javascript, tests, scans) == {root}
    assert scan_blockers(python, tests, scans) == set()
    assert scan_blockers(python, performance, scans) == {root, web}
