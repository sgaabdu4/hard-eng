"""Checks avoid waiting: packages and scans overlap, hung gates stop early, proven changes skip setup."""

import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import gate_config
import pytest
from ci_setup import migrate_impact_token
from conftest import SOURCE, commit, configure, gate, load_module, running, spawner
from gate_config import Gate, Group
from gate_schedule import gate_order, waits


def test_a_hung_gate_stops_at_three_times_its_last_passing_time(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import gate_times

    monkeypatch.setattr(gate_times, "GATE_FLOOR_SECONDS", 1)
    configure(tmp_path, [gate("suite", "pass")])
    assert runner.check(timeout=120) == 0
    times = json.loads((tmp_path / ".git/hard-eng-gate-times.json").read_text())
    assert set(times) == {"./suite"}
    configure(tmp_path, [gate("suite", "import time; time.sleep(60)")])
    started = time.monotonic()
    assert runner.check(timeout=120) == 1
    assert time.monotonic() - started < 30


PERFORMANCE = gate(
    "performance",
    "from pathlib import Path\n"
    "Path('perf.xml').write_text('<testsuite tests=\"1\"><testcase name=\"t\"/></testsuite>')",
    role="performance",
    report={"type": "performance-junit", "path": "perf.xml"},
)


@pytest.mark.parametrize("first", [[], [PERFORMANCE]])
def test_scans_start_beside_a_serial_suite_listed_before_them(
    runner: ModuleType, tmp_path: Path, first: list[dict[str, object]]
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
    configure(tmp_path, [*first, suite, scan])
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
    assert captured.out == "docs_only=true\nrunner=ubuntu-latest\napple=false\n"
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


def test_a_gate_waits_only_for_gates_that_can_disturb_it() -> None:
    javascript: Group = {"path": ".", "language": "javascript", "checks": []}
    python: Group = {"path": ".", "language": "python", "checks": []}
    web: Group = {"path": "web", "checks": []}
    api: Group = {"path": "api", "checks": []}
    lib: Group = {"path": "lib", "checks": []}
    shared: Group = {"path": ".", "checks": []}
    scan: Gate = {
        "name": "scan",
        "role": "security",
        "command": ["x"],
        "parallel": True,
    }
    lint: Gate = {"name": "lint", "role": "lint", "command": ["x"], "parallel": True}
    write: Gate = {"name": "generate", "role": "codegen", "command": ["x"]}
    build: Gate = {"name": "build", "role": "build", "command": ["x"], "parallel": True}
    tests: Gate = {"name": "tests", "role": "tests", "command": ["x"]}
    dead: Gate = {"name": "dead", "role": "dead-code", "command": ["x"]}
    fallow: Gate = {
        "name": "fallow",
        "role": "dead-code-duplicates",
        "command": ["bun", "run", "fallow"],
        "report": {"type": "fallow", "path": "coverage/fallow.json"},
    }
    performance: Gate = {"name": "performance", "role": "performance", "command": ["x"]}
    reach = {"api": {"lib"}}
    assert waits((web, write), (web, scan), reach)
    assert waits((python, write), (web, scan), reach)
    assert waits((lib, write), (api, tests), reach)
    assert waits((lib, tests), (api, fallow), reach)
    assert not waits((web, tests), (api, fallow), reach)
    assert not waits((web, write), (api, scan), reach)
    assert waits((web, build), (web, scan), reach)
    assert not waits((web, build), (web, lint), reach)
    assert waits((javascript, scan), (javascript, tests), reach)
    assert waits((javascript, tests), (javascript, scan), reach)
    assert not waits((python, scan), (python, tests), reach)
    assert not waits((web, scan), (javascript, tests), reach)
    assert waits((javascript, tests), (shared, lint), reach)
    assert waits((shared, lint), (javascript, tests), reach)
    assert waits((web, scan), (python, performance), reach)
    assert waits((web, tests), (web, dead), reach)
    assert not waits((web, tests), (web, lint), reach)
    assert not waits((web, lint), (web, scan), reach)
    assert not waits((web, tests), (api, tests), reach)


def test_performance_still_follows_a_parallel_build() -> None:
    build: Gate = {"name": "build", "role": "build", "command": ["x"], "parallel": True}
    performance: Gate = {"name": "perf", "role": "performance", "command": ["x"]}
    group: Group = {"path": ".", "checks": []}
    order = gate_order([(group, build), (group, performance)])
    assert [gate["name"] for _, gate in order] == ["build", "perf"]


def test_scans_wait_for_a_parallel_generator_still_running(
    runner: ModuleType, tmp_path: Path
) -> None:
    generator = gate(
        "generate",
        "from pathlib import Path;import time;time.sleep(1);Path('generated').touch()",
        role="codegen",
        parallel=True,
    )
    scan = gate(
        "scan",
        "from pathlib import Path;assert Path('generated').exists()",
        role="shell",
        parallel=True,
    )
    configure(tmp_path, [generator, scan])
    assert runner.check() == 0


def no_requirements(_root: Path, _config: object) -> None:
    return None


def packages(
    root: Path, monkeypatch: pytest.MonkeyPatch, *groups: dict[str, object]
) -> None:
    monkeypatch.setattr(gate_config, "validate_required_checks", no_requirements)
    for group in groups:
        (root / str(group["path"])).mkdir(parents=True, exist_ok=True)
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": list(groups), "shared": []})
    )


def meeting(
    tmp_path: Path, name: str, mine: str, other: str, then: str = ""
) -> dict[str, object]:
    """A serial gate that passes only if the other one starts within 10 s of it."""
    code = (
        "from pathlib import Path;import time;end = time.monotonic() + 10\n"
        f"Path({str(tmp_path / mine)!r}).touch()\n"
        f"while not Path({str(tmp_path / other)!r}).exists():\n"
        "    assert time.monotonic() < end; time.sleep(0.02)\n"
    )
    return gate(name, code + then, role="complexity")


def test_serial_gates_of_two_packages_run_at_the_same_time(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = meeting(tmp_path, "suite", "app-running", "ios-running")
    ios = meeting(tmp_path, "suite", "ios-running", "app-running")
    packages(
        tmp_path,
        monkeypatch,
        {"path": "app", "depends_on": [], "checks": [app]},
        {"path": "app/ios", "depends_on": [], "checks": [ios]},
    )
    assert runner.check() == 0


def test_every_failure_is_reported_when_one_package_fails_first(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first = gate("first", "raise SystemExit(1)", role="complexity")
    second = meeting(tmp_path, "second", "second", "slow", "raise SystemExit(2)")
    slow = meeting(tmp_path, "slow", "slow", "second", "raise SystemExit(3)")
    packages(
        tmp_path,
        monkeypatch,
        {"path": "app", "depends_on": [], "checks": [first, second]},
        {"path": "ios", "depends_on": [], "checks": [slow]},
    )
    assert runner.check() == 1
    output = capsys.readouterr().out
    for line in ("FAIL first (exit 1", "FAIL second (exit 2", "FAIL slow (exit 3"):
        assert line in output
    assert set(runner.FAILED_GATES) == {"app/first", "app/second", "ios/slow"}


def test_performance_suites_run_alone_beside_other_packages(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timing = tmp_path / "timing"
    suite = gate(
        "performance",
        f"from pathlib import Path;import time;Path({str(timing)!r}).touch()\n"
        f"time.sleep(1);assert not list(Path({str(tmp_path)!r}).glob('busy-*'))\n"
        f"Path({str(timing)!r}).unlink()\n"
        "Path('perf.xml').write_text('<testsuite tests=\"1\"><testcase name=\"t\"/></testsuite>')",
        role="performance",
        report={"type": "performance-junit", "path": "perf.xml"},
    )

    def other(name: str) -> str:
        marker = str(tmp_path / f"busy-{name}")
        return (
            f"from pathlib import Path;import time;assert not Path({str(timing)!r}).exists()\n"
            f"Path({marker!r}).touch();time.sleep(0.5);Path({marker!r}).unlink()"
        )

    packages(
        tmp_path,
        monkeypatch,
        {"path": "app", "depends_on": [], "checks": [suite]},
        {
            "path": "ios",
            "depends_on": [],
            "checks": [
                gate("suite", other("suite"), role="complexity"),
                gate("lint", other("lint"), role="lint", parallel=True),
            ],
        },
    )
    assert runner.check() == 0


def test_writers_move_ahead_only_of_readers_they_cannot_consume() -> None:
    parent: Group = {"path": "app", "checks": []}
    child: Group = {"path": "app/ios", "checks": []}
    read: Gate = {"name": "tests", "role": "tests", "command": ["x"]}
    write: Gate = {"name": "generate", "role": "generated-sources", "command": ["x"]}
    order = gate_order([(parent, read), (child, write), (child, read)])
    assert order == [(child, write), (parent, read), (child, read)]
    order = gate_order([(child, read), (parent, write)])
    assert order == [(child, read), (parent, write)]


def test_an_interrupt_stops_gates_running_in_worker_threads(tmp_path: Path) -> None:
    marker, second = tmp_path / "child.pid", tmp_path / "second"
    then = [
        sys.executable,
        "-c",
        f"open({str(second)!r}, 'w');import time;time.sleep(60)",
    ]
    script = (
        "import signal, sys\n"
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
        "from gate_schedule import run_checks\n"
        "from process_group import run_in_group\n"
        "signal.signal(signal.SIGINT, signal.default_int_handler)\n"
        "group = {'path': '.', 'checks': []}\n"
        "gate = {'name': 'suite', 'role': 'tests', 'command': []}\n"
        "def run(*_):\n"
        f"    run_in_group({spawner(marker)!r}, timeout=60)\n"
        f"    return run_in_group({then!r}, timeout=60).returncode != 0\n"
        "run_checks([(group, gate)], run, [])\n"
    )
    check = subprocess.Popen([sys.executable, "-c", script])
    deadline = time.monotonic() + 30
    while not marker.exists() or not marker.read_text():
        assert time.monotonic() < deadline and check.poll() is None
        time.sleep(0.05)
    check.send_signal(signal.SIGINT)
    assert check.wait(timeout=10) != 0
    deadline = time.monotonic() + 10
    while running(marker):
        assert time.monotonic() < deadline
        time.sleep(0.05)
    assert not second.exists()


def test_parallel_gates_run_beside_the_serial_gates_of_their_package(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    suite = meeting(tmp_path, "suite", "suite-running", "lint-running")
    lint = {
        **meeting(tmp_path, "lint", "lint-running", "suite-running"),
        "role": "lint",
        "parallel": True,
    }
    packages(
        tmp_path,
        monkeypatch,
        {"path": "app", "depends_on": [], "checks": [suite, lint]},
    )
    assert runner.check() == 0
