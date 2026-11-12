"""The freshness gate fails on direct dependencies that trail a release two days old."""

import json
import os
import re
import shutil
import sys
import threading
import urllib.error
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from freshness import (
    freshness_waiting,
    pub_waiting,
    stale_dependencies,
    validate_freshness,
    validate_holds,
)
from gate_config import Gate, Group, JsonObject, validate_gate, validate_required_checks
from gitleaks_scan import run_gate_command
from project_setup import add_freshness
from reports import validate_scanner_report
from shipping import ShippingPolicy
from test_setup import repository

FIXTURES = Path(__file__).parent / "fixtures/freshness"
PUB = "https://pub.dev/api/packages/"
PYPI = "https://pypi.org/pypi/"
POETRY_ADD = "POETRY_SOLVER_MIN_RELEASE_AGE=2 uvx poetry add "


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text()


def moment(stamp: str) -> datetime:
    return datetime.fromisoformat(stamp)


class Registry:
    """Serves recorded registry responses and remembers which were asked for."""

    def __init__(self, records: dict[str, str]) -> None:
        self.records = records
        self.requests: list[str] = []

    def __call__(self, url: str) -> object:
        self.requests.append(url)
        if url not in self.records:
            raise urllib.error.URLError(f"no recorded response for {url}")
        return json.loads(self.records[url])


def freshness_gate(tool: str, holds: list[JsonObject] | None = None) -> Gate:
    gate: Gate = {
        "name": "freshness",
        "role": "freshness",
        "command": [tool, "outdated"],
    }
    if holds is not None:
        gate["holds"] = holds
    return gate


def check(
    tmp_path: Path,
    tool: str,
    report: str,
    registry: Registry | None = None,
    now: str = "2026-10-26T00:00:00+00:00",
    holds: list[JsonObject] | None = None,
) -> None:
    path = tmp_path / "freshness.report"
    path.write_text(report)
    validate_freshness(
        path,
        freshness_gate(tool, holds),
        registry or Registry({}),
        moment(now),
        directory=tmp_path,
    )


def test_bun_fails_on_release_older_than_two_days(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"is-odd 2\.0\.0 → 3\.0\.1") as failure:
        check(tmp_path, "bun", fixture("bun-outdated.txt"))
    assert "left-pad 1.2.0 → 1.3.0" in str(failure.value)
    check(tmp_path, "bun", fixture("bun-current-with-star.txt"))
    check(tmp_path, "bun", fixture("bun-up-to-date.txt"))
    with pytest.raises(ValueError, match="bun output is unreadable"):
        check(tmp_path, "bun", "")


def test_bun_skips_peer_rows_and_keeps_the_dev_row_of_the_same_name() -> None:
    stale = stale_dependencies(
        "bun",
        fixture("bun-outdated-peers.txt"),
        Registry({}),
        moment("2026-10-26T00:00:00+00:00"),
    )
    assert stale == [
        ("exact-mirror", "0.2.9", "1.2.7"),
        ("typescript", "5.9.3", "7.0.2"),
    ]


def test_the_gate_passes_on_the_report_its_bun_step_leaves(tmp_path: Path) -> None:
    check(tmp_path, "bun", fixture("bun-after-update.txt"))


def dart_registry() -> Registry:
    return Registry(
        {
            PUB + "http": fixture("pub-http.json"),
            PUB + "lints": fixture("pub-lints.json"),
        }
    )


def test_dart_uses_pub_dates_for_direct_dependencies(tmp_path: Path) -> None:
    git_dependency = {"package": "local", "kind": "direct"}
    git_dependency |= {"current": {"version": "1.0.0"}, "latest": {"version": "1.0.0"}}
    parsed = json.loads(fixture("dart-outdated.json"))
    parsed["packages"].append(git_dependency)
    report = json.dumps(parsed)
    registry = dart_registry()
    with pytest.raises(ValueError, match=r"http 0\.13\.6 → 1\.5\.0") as failure:
        check(tmp_path, "dart", report, registry, "2025-11-11T18:27:56+00:00")
    assert "lints 2.1.1 → 6.0.0" in str(failure.value)
    assert "web" not in str(failure.value)
    assert registry.requests == [PUB + "http", PUB + "lints"]
    with pytest.raises(ValueError, match=r"http 0\.13\.6 → 1\.6\.0"):
        check(tmp_path, "dart", report, dart_registry(), "2025-11-12T18:27:57+00:00")
    retracted = json.loads(fixture("pub-http.json"))
    retracted["versions"][-2]["retracted"] = True
    records = {PUB + "http": json.dumps(retracted)}
    records[PUB + "lints"] = fixture("pub-lints.json")
    with pytest.raises(ValueError, match=r"http 0\.13\.6 → 1\.4\.0"):
        check(tmp_path, "dart", report, Registry(records), "2025-11-11T18:27:56+00:00")


def test_dart_stops_at_the_version_pub_can_resolve(tmp_path: Path) -> None:
    parsed = json.loads(fixture("dart-outdated.json"))
    http = next(p for p in parsed["packages"] if p["package"] == "http")
    http["resolvable"] = {"version": "1.4.0"}
    blocked = {"package": "build_runner", "kind": "dev"}
    blocked |= {"current": {"version": "2.16.2"}, "resolvable": {"version": "2.16.2"}}
    parsed["packages"].append(blocked | {"latest": {"version": "2.17.1"}})
    registry = dart_registry()
    with pytest.raises(ValueError, match=r"http 0\.13\.6 → 1\.4\.0") as failure:
        check(
            tmp_path, "dart", json.dumps(parsed), registry, "2025-11-11T18:27:56+00:00"
        )
    assert "build_runner" not in str(failure.value)
    assert PUB + "build_runner" not in registry.requests


PUB_UPGRADE = "pub upgrade --major-versions --unlock-transitive"


@pytest.mark.parametrize(
    ("dry_run", "now", "message"),
    [
        ("blocked", "2026-11-07T21:00:00+00:00", "waits"),
        ("blocked", "2026-11-08T13:00:00+00:00", "fails"),
        ("resolves", "2026-11-07T21:00:00+00:00", "fails"),
    ],
    ids=["pin-has-only-a-young-fix", "pin-fix-is-due", "upgrade-resolves"],
)
def test_flutter_waits_while_only_a_young_release_unblocks_the_upgrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    dry_run: str,
    now: str,
    message: str,
) -> None:
    tool = tmp_path / "bin/flutter"
    tool.parent.mkdir()
    blocked = FIXTURES / "flutter-upgrade-blocked.txt"
    body = f"cat '{blocked}'; exit 1" if dry_run == "blocked" else "exit 0"
    tool.write_text(
        f'#!/bin/sh\n[ "$*" = "{PUB_UPGRADE} build_runner --dry-run" ]'
        f" || exit 2\n{body}\n"
    )
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tool.parent}:{os.environ['PATH']}")
    stale = {"package": "build_runner", "kind": "dev"}
    stale |= {"current": {"version": "2.16.2"}, "resolvable": {"version": "2.17.1"}}
    path = tmp_path / "freshness.report"
    path.write_text(json.dumps({"packages": [stale]}))
    registry = Registry(
        {
            PUB + "build_runner": fixture("pub-build_runner.json"),
            PUB + "riverpod_generator": fixture("pub-riverpod_generator.json"),
        }
    )
    waiting = pub_waiting("flutter", tmp_path, registry, moment(now))
    gate = freshness_gate("flutter")
    if message == "waits":
        validate_freshness(path, gate, registry, moment(now), waiting)
        out = capsys.readouterr().out
        assert (
            "build_runner 2.17.1 needs a dependency that is not 2 days old yet" in out
        )
    else:
        with pytest.raises(ValueError, match="build_runner 2.16.2 → 2.17.1") as failure:
            validate_freshness(path, gate, registry, moment(now), waiting)
        assert f"Run `flutter {PUB_UPGRADE} build_runner` in" in str(failure.value)


def test_uv_uses_pypi_upload_dates(tmp_path: Path) -> None:
    report = fixture("uv-tree.txt")
    records = {
        PYPI + "httpx/json": fixture("pypi-httpx.json"),
        PYPI + "pytest/json": fixture("pypi-pytest.json"),
    }
    with pytest.raises(ValueError, match=r"httpx 0\.27\.0 → 0\.28\.0") as failure:
        check(tmp_path, "uv", report, Registry(records), "2024-12-04T00:00:00+00:00")
    assert "pytest 8.0.0 → 8.3.4" in str(failure.value)
    with pytest.raises(ValueError, match=r"httpx 0\.27\.0 → 0\.28\.1"):
        check(tmp_path, "uv", report, Registry(records), "2024-12-08T15:37:22+00:00")
    check(tmp_path, "uv", report, Registry(records), "2024-03-04T00:00:00+00:00")
    check(tmp_path, "uv", report, Registry(records), "2024-03-06T00:00:00+00:00")
    with pytest.raises(ValueError, match="uv output is unreadable"):
        check(tmp_path, "uv", "error: failed to fetch", Registry(records))


def test_uv_counts_a_post_release_as_newer() -> None:
    report = "app v0.1.0\n└── python-dateutil v2.9.0 (latest: v2.9.0.post0)\n"
    records = {PYPI + "python-dateutil/json": fixture("pypi-dateutil.json")}
    stale = stale_dependencies(
        "uv", report, Registry(records), moment("2024-03-04T00:00:00+00:00")
    )
    assert stale == [("python-dateutil", "2.9.0", "2.9.0.post0")]
    assert not stale_dependencies(
        "uv", report, Registry(records), moment("2024-03-02T00:00:00+00:00")
    )


def test_uv_reads_a_dependency_with_an_extra_once() -> None:
    report = (
        "app v0.1.0\n"
        "├── httpx[http2] v0.27.0 (latest: v0.28.1)\n"
        "└── httpx v0.27.0 (group: dev) (latest: v0.28.1)\n"
    )
    records = {PYPI + "httpx/json": fixture("pypi-httpx.json")}
    stale = stale_dependencies(
        "uv", report, Registry(records), moment("2024-12-08T15:37:22+00:00")
    )
    assert stale == [("httpx", "0.27.0", "0.28.1")]


POETRY_SECTIONS = [
    pytest.param(
        '[project]\ndependencies = ["httpx>=0.27"]\n',
        ["httpx"],
        ["'httpx>=0.27.0'"],
        id="project-dependency",
    ),
    pytest.param(
        '[project.optional-dependencies]\ncli = ["httpx>=0.27"]\n',
        ["httpx"],
        ["--optional cli 'httpx>=0.27.0'"],
        id="optional-extra",
    ),
    pytest.param(
        '[dependency-groups]\ntest = ["coverage>=7"]\n'
        'dev = [{include-group = "test"}, "httpx>=0.27", "pytest>=7"]\n',
        ["httpx", "pytest"],
        ["--group dev 'httpx>=0.27.0' 'pytest>=7.4.4'"],
        id="dependency-group-beside-include-group",
    ),
    pytest.param(
        '[tool.poetry.dependencies]\npython = "^3.9"\nhttpx = "^0.27"\n',
        ["httpx"],
        ["'httpx>=0.27.0'"],
        id="poetry-string",
    ),
    pytest.param(
        '[tool.poetry.group.test.dependencies]\npytest = "^7.2"\n',
        ["pytest"],
        ["--group test 'pytest>=7.4.4'"],
        id="poetry-group-table",
    ),
    pytest.param(
        '[tool.poetry.dependencies]\nhttpx = {version = "^0.27", python = "<3.11"}\n'
        'pytest = "^7.2"\n',
        ["httpx", "pytest"],
        ["--python '<3.11' 'httpx>=0.27.0'", "'pytest>=7.4.4'"],
        id="poetry-table-with-python",
    ),
    pytest.param(
        "[project]\ndependencies = ['httpx[http2]>=0.27; python_version < \"3.13\"']\n",
        ["httpx"],
        ["'httpx[http2]>=0.27.0; python_version < \"3.13\"'"],
        id="pep508-marker-and-extras",
    ),
    pytest.param(
        '[project]\ndependencies = ["HTTPX>=0.27"]\n',
        ["httpx"],
        ["'HTTPX>=0.27.0'"],
        id="canonical-name",
    ),
    pytest.param(
        '[project]\ndependencies = ["httpx>=0.27"]\n'
        '[dependency-groups]\ndev = ["httpx>=0.27"]\n',
        ["httpx"],
        ["'httpx>=0.27.0'", "--group dev 'httpx>=0.27.0'"],
        id="two-sections",
    ),
]


@pytest.mark.parametrize(("pyproject", "names", "lines"), POETRY_SECTIONS)
def test_the_poetry_step_raises_each_entry_where_the_project_declares_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pyproject: str,
    names: list[str],
    lines: list[str],
) -> None:
    (tmp_path / "pyproject.toml").write_text(pyproject)
    latest = {"httpx": ("0.27.0", "0.28.1"), "pytest": ("7.4.4", "9.1.1")}
    poetry_dry_run(tmp_path, monkeypatch, moves(*((n, *latest[n]) for n in names)))
    report = [
        {"name": name, "version": latest[name][0], "latest_version": latest[name][1]}
        for name in names
    ]
    with pytest.raises(ValueError, match="baseline repair") as failure:
        check(tmp_path, "poetry", json.dumps(report))
    route = "`, then `".join(POETRY_ADD + line for line in lines)
    assert f"Run `{route}` in a separate PR first" in str(failure.value)


def poetry_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str, status: int = 0
) -> Path:
    log = tmp_path / "uvx.log"
    answer = tmp_path / "dry-run.txt"
    answer.write_text(output)
    tool = tmp_path / "bin/uvx"
    tool.parent.mkdir(exist_ok=True)
    tool.write_text(
        f"#!/bin/sh\necho \"$* age=$POETRY_SOLVER_MIN_RELEASE_AGE cwd=$(pwd)\" >> '{log}'\n"
        f"cat '{answer}'\nexit {status}\n"
    )
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tool.parent}:{os.environ['PATH']}")
    return log


def moves(*rows: tuple[str, str, str]) -> str:
    return "\n".join(f"  - Updating {n} ({c} -> {t})" for n, c, t in rows)


DEV_GROUP = (
    '[dependency-groups]\ndev = ["pytest~=7.2", "pytest-cov~=4.0", "mypy>=1.0"]\n'
)


def stale_poetry_project(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(DEV_GROUP)


def pytest_rows() -> str:
    rows = json.loads(fixture("poetry-show-python-bound.json"))
    return json.dumps([row for row in rows if row["name"] != "mypy"])


def test_poetry_names_the_newest_release_its_solver_can_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stale_poetry_project(tmp_path)
    poetry_dry_run(tmp_path, monkeypatch, fixture("poetry-add-dry-run.txt"))
    with pytest.raises(ValueError, match=r"pytest-cov 4\.1\.0 → 7\.1\.0") as failure:
        check(tmp_path, "poetry", fixture("poetry-show-python-bound.json"))
    assert "pytest 7.4.4 → 9.2.0" not in str(failure.value)
    assert "mypy 1.19.1 → 2.4.1" not in str(failure.value)
    assert f"`{POETRY_ADD}--group dev 'pytest-cov>=4.1.0'`" in str(failure.value)
    out = capsys.readouterr().out
    assert "pytest stays at 7.4.4: 9.2.0 does not install" in out
    assert "`uvx poetry add --dry-run --group dev 'mypy==2.4.1'` shows why" in out


def test_poetry_names_a_target_between_the_current_and_the_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_poetry_project(tmp_path)
    poetry_dry_run(
        tmp_path, monkeypatch, fixture("poetry-add-dry-run-stepped-back.txt")
    )
    with pytest.raises(ValueError, match=r"pytest 7\.4\.4 → 8\.4\.2") as failure:
        check(tmp_path, "poetry", pytest_rows())
    assert "pytest-cov 4.1.0 → 7.1.0" in str(failure.value)
    assert "9.2.0" not in str(failure.value)


def test_poetry_passes_when_no_dependency_can_move(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stale_poetry_project(tmp_path)
    moving = "Updating pytest-cov (4.1.0 -> 7.1.0)"
    still = "Installing pytest-cov (4.1.0): Skipped for the following reason: Already installed"
    poetry_dry_run(
        tmp_path, monkeypatch, fixture("poetry-add-dry-run.txt").replace(moving, still)
    )
    check(tmp_path, "poetry", fixture("poetry-show-python-bound.json"))
    out = capsys.readouterr().out
    assert "pytest-cov stays at 4.1.0: 7.1.0 does not install" in out
    assert "Every direct dependency is on its newest release" in out


def test_the_poetry_dry_run_carries_the_release_wait_and_the_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_poetry_project(tmp_path)
    log = poetry_dry_run(tmp_path, monkeypatch, fixture("poetry-add-dry-run.txt"))
    with pytest.raises(ValueError, match="baseline repair"):
        check(tmp_path, "poetry", fixture("poetry-show-python-bound.json"))
    call = log.read_text().splitlines()
    assert len(call) == 1
    assert "add --dry-run --no-ansi -n --group dev" in call[0]
    assert "mypy>=1.19.1 pytest>=7.4.4 pytest-cov>=4.1.0" in call[0]
    assert " age=2 " in call[0]


def test_the_poetry_dry_run_runs_in_the_directory_of_the_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "service"
    package.mkdir()
    stale_poetry_project(package)
    log = poetry_dry_run(tmp_path, monkeypatch, fixture("poetry-add-dry-run.txt"))
    report = tmp_path / "freshness.report"
    report.write_text(fixture("poetry-show-python-bound.json"))
    gate = freshness_gate("poetry")
    with pytest.raises(ValueError, match="baseline repair"):
        validate_scanner_report("freshness", gate, report, gate["command"], package, 60)
    assert log.read_text().strip().endswith(f"cwd={package.resolve()}")


def test_a_failed_poetry_dry_run_names_its_command_and_the_tool_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_poetry_project(tmp_path)
    reason = (
        "pyproject.toml changed significantly since poetry.lock was last generated."
    )
    poetry_dry_run(tmp_path, monkeypatch, reason, status=1)
    with pytest.raises(ValueError, match="uvx poetry add --dry-run") as failure:
        check(tmp_path, "poetry", fixture("poetry-show-python-bound.json"))
    assert reason in str(failure.value)


def test_a_poetry_git_entry_is_named_and_not_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\nhttpx = {git = "https://example.com/httpx.git"}\n'
    )
    log = poetry_dry_run(tmp_path, monkeypatch, "")
    row = {"name": "httpx", "version": "0.27.0", "latest_version": "0.28.1"}
    check(tmp_path, "poetry", json.dumps([row]))
    assert "httpx 0.28.1: Hard Eng cannot raise a git entry; update it by hand" in (
        capsys.readouterr().out
    )
    assert not log.exists()


def test_a_hold_matches_the_version_the_solver_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_poetry_project(tmp_path)
    poetry_dry_run(
        tmp_path, monkeypatch, fixture("poetry-add-dry-run-stepped-back.txt")
    )
    report = pytest_rows()
    with pytest.raises(ValueError, match=r"pytest 7\.4\.4 → 8\.4\.2"):
        check(
            tmp_path, "poetry", report, holds=[hold(package="pytest", version="9.2.0")]
        )
    with pytest.raises(ValueError, match=r"pytest-cov 4\.1\.0 → 7\.1\.0") as failure:
        check(
            tmp_path, "poetry", report, holds=[hold(package="pytest", version="8.4.2")]
        )
    assert "pytest 7.4.4" not in str(failure.value)


def test_a_poetry_dev_dependencies_entry_fails_with_the_move_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old = '[tool.poetry.dev-dependencies]\npytest = "^7.2"\n'
    (tmp_path / "pyproject.toml").write_text(old)
    log = poetry_dry_run(tmp_path, monkeypatch, moves(("pytest", "7.4.4", "8.4.2")))
    with pytest.raises(ValueError, match=r"pytest 7\.4\.4 → 9\.2\.0") as failure:
        check(tmp_path, "poetry", pytest_rows())
    assert "Move the entries of [tool.poetry.dev-dependencies] to " in str(
        failure.value
    )
    assert "[tool.poetry.group.dev.dependencies]" in str(failure.value)
    assert (
        "then run `POETRY_SOLVER_MIN_RELEASE_AGE=2 uvx poetry lock` and the check again."
        in str(failure.value)
    )
    assert not log.exists()
    moved = old.replace("dev-dependencies", "group.dev.dependencies")
    (tmp_path / "pyproject.toml").write_text(moved)
    with pytest.raises(ValueError, match=r"pytest 7\.4\.4 → 8\.4\.2") as failure:
        check(tmp_path, "poetry", pytest_rows())
    assert f"`{POETRY_ADD}--group dev 'pytest>=7.4.4'`" in str(failure.value)


def test_a_stale_name_without_a_declaration_fails_with_the_hand_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies = ["httpx"]\n')
    log = poetry_dry_run(tmp_path, monkeypatch, "")
    with pytest.raises(ValueError, match=r"pytest 7\.4\.4 → 9\.2\.0") as failure:
        check(tmp_path, "poetry", json.dumps(json.loads(pytest_rows())[:1]))
    assert "Raise pytest by hand in pyproject.toml" in str(failure.value)
    assert "stays at" not in str(failure.value)
    assert not log.exists()


def test_a_dry_run_with_no_line_for_a_name_falls_back_to_the_latest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stale_poetry_project(tmp_path)
    poetry_dry_run(tmp_path, monkeypatch, moves(("pytest-cov", "4.1.0", "7.1.0")))
    with pytest.raises(ValueError, match=r"pytest 7\.4\.4 → 9\.2\.0") as failure:
        check(tmp_path, "poetry", pytest_rows())
    assert "named no version" not in str(failure.value)
    assert f"{POETRY_ADD}--group dev 'pytest>=7.4.4' 'pytest-cov>=4.1.0'" in str(
        failure.value
    )
    holds = [
        hold(package="pytest", version="9.2.0"),
        hold(package="pytest-cov", version="7.1.0"),
    ]
    check(tmp_path, "poetry", pytest_rows(), holds=holds)


def test_an_entry_poetry_cannot_raise_is_not_named_beside_one_it_can(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["httpx>=0.27"]\n'
        '[tool.poetry.dependencies]\nhttpx = {source = "internal"}\n'
    )
    poetry_dry_run(tmp_path, monkeypatch, moves(("httpx", "0.27.0", "0.28.1")))
    row = {"name": "httpx", "version": "0.27.0", "latest_version": "0.28.1"}
    with pytest.raises(ValueError, match=r"httpx 0\.27\.0 → 0\.28\.1"):
        check(tmp_path, "poetry", json.dumps([row]))
    assert "cannot raise" not in capsys.readouterr().out


def test_poetry_reads_outdated_with_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    poetry_dry_run(
        tmp_path,
        monkeypatch,
        moves(("httpx", "0.27.0", "0.28.1"), ("pytest", "8.0.0", "9.1.1")),
    )
    with pytest.raises(ValueError, match=r"httpx 0\.27\.0 → 0\.28\.1") as failure:
        check(tmp_path, "poetry", fixture("poetry-show.json"))
    assert "pytest 8.0.0 → 9.1.1" in str(failure.value)
    check(tmp_path, "poetry", "[]")
    code = "import os; print(os.environ['POETRY_SOLVER_MIN_RELEASE_AGE'])"
    with (tmp_path / "out").open("w+") as out, (tmp_path / "err").open("w") as err:
        result = run_gate_command(
            "freshness", [sys.executable, "-c", code], tmp_path, 60, out, err
        )
        out.seek(0)
        assert (result.returncode, out.read()) == (0, "2\n")


def test_unreachable_registry_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Registry unreachable"):
        check(tmp_path, "dart", fixture("dart-outdated.json"), Registry({}))
    with pytest.raises(ValueError, match="Registry unreachable"):
        check(tmp_path, "uv", fixture("uv-tree.txt"), Registry({}))
    with pytest.raises(ValueError, match="dart output is unreadable"):
        check(tmp_path, "dart", "Failed to fetch https://pub.dev", dart_registry())
    with pytest.raises(ValueError, match="poetry output is unreadable"):
        check(tmp_path, "poetry", "Connection refused")


def hold(**changes: str) -> JsonObject:
    return {
        "package": "is-odd",
        "version": "3.0.1",
        "reason": "3.0.1 crashes on start",
        "until": "2026-10-30",
        **changes,
    }


def test_hold_expires_and_needs_reason(tmp_path: Path) -> None:
    report = fixture("bun-outdated.txt")
    holds = [hold(), hold(package="left-pad", version="1.3.0")]
    check(tmp_path, "bun", report, now="2026-10-30T23:00:00+00:00", holds=holds)
    with pytest.raises(ValueError, match=r"is-odd 2\.0\.0 → 3\.0\.1"):
        check(tmp_path, "bun", report, now="2026-10-31T00:00:00+00:00", holds=holds)
    with pytest.raises(ValueError, match=r"left-pad 1\.2\.0 → 1\.3\.0") as failure:
        check(tmp_path, "bun", report, now="2026-10-28T00:00:00+00:00", holds=[hold()])
    assert "is-odd" not in str(failure.value)
    with pytest.raises(ValueError, match=r"is-odd 2\.0\.0 → 3\.0\.1"):
        check(
            tmp_path,
            "bun",
            report,
            now="2026-10-28T00:00:00+00:00",
            holds=[hold(version="3.0.0"), holds[1]],
        )
    today = date(2026, 10, 26)
    validate_holds([hold(until="2026-11-09")], today)
    for bad in (
        hold(reason="  "),
        hold(until="30 October"),
        hold(until="2026-11-10"),
    ):
        with pytest.raises(ValueError, match="hold"):
            validate_holds([bad], today)
    with pytest.raises(ValueError, match="hold"):
        validate_holds([{"package": "is-odd"}], today)
    expiry = (datetime.now(UTC) + timedelta(days=15)).date().isoformat()
    gate = freshness_gate("bun", holds=[hold(until=expiry)])
    with pytest.raises(ValueError, match="within 14 days"):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize(
    ("tool", "report", "command"),
    [
        (
            "bun",
            "bun-outdated.txt",
            "bun update --latest --minimum-release-age=172800 is-odd left-pad",
        ),
        (
            "uv",
            "uv-tree.txt",
            "uv add 'httpx>=0.28.0'`, then `uv add --group dev 'pytest>=8.3.4'",
        ),
        (
            "poetry",
            "poetry-show.json",
            POETRY_ADD + "'httpx>=0.27.0' 'pytest>=8.0.0'",
        ),
    ],
)
def test_failure_names_upgrade_route(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    report: str,
    command: str,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["httpx>=0.27", "pytest>=8"]\n'
    )
    poetry_dry_run(
        tmp_path,
        monkeypatch,
        moves(("httpx", "0.27.0", "0.28.1"), ("pytest", "8.0.0", "9.1.1")),
    )
    records = {
        PYPI + "httpx/json": fixture("pypi-httpx.json"),
        PYPI + "pytest/json": fixture("pypi-pytest.json"),
    }
    with pytest.raises(ValueError, match="baseline repair") as failure:
        check(
            tmp_path,
            tool,
            fixture(report),
            Registry(records),
            "2024-12-04T00:00:00+00:00",
        )
    assert f"`{command}`" in str(failure.value)
    assert re.search(r"separate PR first", str(failure.value))


@pytest.mark.parametrize(
    ("script", "failed", "message"),
    [
        (
            "echo 'error: ConnectionRefused downloading package manifest' >&2; exit 1",
            True,
            "ConnectionRefused",
        ),
        ("cat bun-outdated.txt", True, "is-odd 2.0.0 → 3.0.1"),
        ("cat bun-up-to-date.txt", False, "Every direct dependency"),
        (
            (
                'case "$1 $3" in "outdated "*) cat bun-outdated.txt;; "update is-odd")'
                ' echo \'error: No version matching "odd-core" found for specifier'
                ' "3.0.1" (blocked by minimum-release-age: 172800 seconds)\' >&2; exit 1;;'
                " esac"
            ),
            True,
            "is-odd 3.0.1 needs a dependency that is not 2 days old yet",
        ),
        (
            (
                'case "$1" in outdated) cat bun-outdated.txt;; update)'
                " echo '(blocked by minimum-release-age: 172800 seconds)' >&2; exit 1;; esac"
            ),
            False,
            "left-pad 1.3.0 needs a dependency that is not 2 days old yet",
        ),
        (
            (
                'case "$1" in outdated) cat bun-outdated.txt;; update)'
                " echo 'error: ConnectionRefused' >&2; exit 1;; esac"
            ),
            True,
            "left-pad 1.2.0 → 1.3.0",
        ),
    ],
    ids=["registry-down", "stale", "current", "one-waits", "all-wait", "dry-run-down"],
)
def test_gate_run_shows_the_tool_message_and_the_stale_package(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    script: str,
    failed: bool,
    message: str,
) -> None:
    tool = tmp_path / "bin/bun"
    tool.parent.mkdir()
    tool.write_text(f"#!/bin/sh\n{script}\n")
    tool.chmod(0o755)
    for name in ("bun-outdated.txt", "bun-up-to-date.txt"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    monkeypatch.setenv("PATH", f"{tool.parent}:{os.environ['PATH']}")
    gate: Gate = {
        "name": "freshness",
        "role": "freshness",
        "command": ["bun", "outdated", "--minimum-release-age=172800"],
        "report": {
            "type": "freshness",
            "path": "coverage/freshness.txt",
            "stdout": True,
        },
    }
    group: Group = {"path": ".", "checks": [gate]}
    assert runner.run_gate(group, gate, 30, threading.Lock()) is failed
    assert message in capsys.readouterr().out


FRESHNESS_COMMANDS = {
    "bun": ["bun", "outdated", "--minimum-release-age=172800"],
    "dart": ["dart", "pub", "outdated", "--json"],
    "flutter": ["flutter", "pub", "outdated", "--json"],
    "uv": ["uv", "tree", "--frozen", "--outdated", "--all-groups", "--depth", "1"],
    "poetry": ["poetry", "show", "--outdated", "--top-level", "--format", "json"],
}


@pytest.mark.parametrize("tool", sorted(FRESHNESS_COMMANDS))
def test_groups_require_freshness_role(
    installer: ModuleType, tmp_path: Path, tool: str
) -> None:
    repository(tmp_path)
    if tool != "bun":
        (tmp_path / "package.json").unlink()
        (tmp_path / "bun.lock").unlink()
    if tool in {"uv", "poetry"}:
        (tmp_path / "pyproject.toml").write_text('[project]\nname="app"\nversion="1"\n')
        (tmp_path / f"{tool}.lock").touch()
    if tool in {"dart", "flutter"}:
        sdk = "dependencies:\n  flutter:\n    sdk: flutter\n" * (tool == "flutter")
        (tmp_path / "pubspec.yaml").write_text(f"name: app\n{sdk}")
        (tmp_path / "pubspec.lock").touch()
        (tmp_path / "lib").mkdir()
        (tmp_path / "lib/app.dart").write_text("int one() => 1;\n")
    config = installer.gate_config(tmp_path)
    package = config["packages"][0]
    gate = next(g for g in package["checks"] if g.get("role") == "freshness")
    assert gate["command"] == FRESHNESS_COMMANDS[tool]
    assert gate["report"]["type"] == "freshness"
    assert gate["report"]["stdout"] is True
    validate_required_checks(tmp_path, config)
    package["checks"].remove(gate)
    with pytest.raises(ValueError, match="missing mandatory checks: freshness"):
        validate_required_checks(tmp_path, config)
    add_freshness(tmp_path, installer.SOURCE, package)
    assert next(g for g in package["checks"] if g.get("role") == "freshness") == gate
    add_freshness(tmp_path, installer.SOURCE, package)
    assert [g.get("role") for g in package["checks"]].count("freshness") == 1
    validate_required_checks(tmp_path, config)


def test_languages_sharing_a_folder_each_get_their_own_freshness(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\nname="app"\nversion="1"\n')
    (tmp_path / "uv.lock").touch()
    packages = installer.gate_config(tmp_path)["packages"]
    for package in packages:
        package["checks"] = [
            g for g in package["checks"] if g.get("role") != "freshness"
        ]
        add_freshness(tmp_path, installer.SOURCE, package)
    added = {
        package["language"]: next(
            g for g in package["checks"] if g.get("role") == "freshness"
        )
        for package in packages
    }
    assert added["python"]["command"][:2] == ["uv", "tree"]
    assert added["javascript"]["command"][:2] == ["bun", "outdated"]
    paths = {gate["report"]["path"] for gate in added.values()}
    assert len(paths) == len(added)


def test_javascript_workspace_checks_freshness_from_its_root(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").write_text('{"private":true,"workspaces":["apps/*"]}')
    member = tmp_path / "apps/web"
    member.mkdir(parents=True)
    (member / "package.json").write_text('{"name":"web"}')
    packages = {
        package["path"]: package
        for package in installer.gate_config(tmp_path)["packages"]
    }
    root = [g for g in packages["."]["checks"] if g.get("role") == "freshness"]
    assert [g["command"] for g in root] == [[*FRESHNESS_COMMANDS["bun"], "-r"]]
    assert "freshness" not in {g.get("role") for g in packages["apps/web"]["checks"]}


def test_workspace_root_without_a_language_still_gets_freshness(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").write_text('{"private":true,"workspaces":["apps/*"]}')
    (tmp_path / "apps/web").mkdir(parents=True)
    (tmp_path / "apps/web/package.json").write_text('{"name":"web"}')
    root = installer.gate_config(tmp_path)["packages"][0]
    root.pop("language", None)
    root["checks"] = [g for g in root["checks"] if g.get("role") != "freshness"]
    add_freshness(tmp_path, installer.SOURCE, root)
    added = [g["command"] for g in root["checks"] if g.get("role") == "freshness"]
    assert added == [[*FRESHNESS_COMMANDS["bun"], "-r"]]


def test_workspace_root_beside_a_python_package_keeps_bun(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").write_text('{"private":true,"workspaces":["apps/*"]}')
    (tmp_path / "apps/web").mkdir(parents=True)
    (tmp_path / "apps/web/package.json").write_text('{"name":"web"}')
    (tmp_path / "pyproject.toml").write_text('[project]\nname="app"\nversion="1"\n')
    (tmp_path / "uv.lock").touch()
    packages = [
        p for p in installer.gate_config(tmp_path)["packages"] if p["path"] == "."
    ]
    for package in packages:
        package["checks"] = [
            g for g in package["checks"] if g.get("role") != "freshness"
        ]
        add_freshness(tmp_path, installer.SOURCE, package)
    added = sorted(
        g["command"][0]
        for package in packages
        for g in package["checks"]
        if g.get("role") == "freshness"
    )
    assert added == ["bun", "uv"]


def test_install_adds_freshness_to_an_existing_gate_file(
    installer: ModuleType, tmp_path: Path, shipping_policy: ShippingPolicy
) -> None:
    repository(tmp_path)
    config = installer.gate_config(tmp_path)
    config["shipping"] = shipping_policy
    checks = config["packages"][0]["checks"]
    checks[:] = [gate for gate in checks if gate.get("role") != "freshness"]
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    installer.install(tmp_path)
    installed = json.loads((tmp_path / "hard-eng.gates.json").read_text())
    roles = [gate.get("role") for gate in installed["packages"][0]["checks"]]
    assert roles.count("freshness") == 1


WORKSPACE_REPORT = """bun outdated v1.4.3 (c6da4a4d3)
|-------------------------------------|
| Package     | Current | Update | Latest |
|-------------|---------|--------|--------|
| typescript  | 5.9.3   | 5.9.3  | 7.0.2  |
|-------------|---------|--------|--------|
| typescript  | 5.9.3   | 5.9.3  | 7.0.2  |
|-------------|---------|--------|--------|
| left-pad    | 1.2.0   | 1.2.0  | 1.3.0  |
|-------------------------------------|
"""


def test_the_bun_repair_command_covers_a_workspace_once(tmp_path: Path) -> None:
    path = tmp_path / "freshness.report"
    path.write_text(WORKSPACE_REPORT)
    gate = freshness_gate("bun")
    gate["command"] = ["bun", "outdated", "-r"]
    with pytest.raises(ValueError, match="baseline repair") as failure:
        validate_freshness(
            path, gate, Registry({}), moment("2026-10-26T00:00:00+00:00")
        )
    assert (
        "`bun update -r --latest --minimum-release-age=172800 typescript left-pad`"
        in str(failure.value)
    )


def test_the_bun_release_age_check_runs_in_the_gates_workspace_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = tmp_path / "bin/bun"
    tool.parent.mkdir()
    seen = tmp_path / "seen.txt"
    tool.write_text(f'#!/bin/sh\necho "$@" >> {seen}\nexit 1\n')
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tool.parent}:{os.environ['PATH']}")
    gate = freshness_gate("bun")
    gate["command"] = ["bun", "outdated", "-r"]
    waiting = freshness_waiting(gate, tmp_path)
    assert waiting is not None
    waiting("typescript")
    assert seen.read_text().startswith("update -r --latest typescript")


def test_a_root_line_with_no_version_is_read() -> None:
    report = "dynv\n└── httpx v0.27.0 (latest: v0.28.1)\n"
    records = {PYPI + "httpx/json": fixture("pypi-httpx.json")}
    stale = stale_dependencies(
        "uv", report, Registry(records), moment("2024-12-08T15:37:22+00:00")
    )
    assert stale == [("httpx", "0.27.0", "0.28.1")]
    with pytest.raises(ValueError, match="no dependency tree"):
        stale_dependencies(
            "uv", "", Registry(records), moment("2024-12-08T00:00:00+00:00")
        )


def test_the_target_is_a_version_that_the_python_range_can_install() -> None:
    releases = {
        version: [{"upload_time_iso_8601": "2024-01-01T00:00:00+00:00"}]
        for version in ("4.26.0", "4.65.0", "4.67.13")
    }
    records = {PYPI + "tqdm/json": json.dumps({"releases": releases})}
    now = moment("2024-12-08T00:00:00+00:00")
    report = "app v0.1.0\n└── tqdm v4.26.0 (latest: v4.65.0)\n"
    assert stale_dependencies("uv", report, Registry(records), now) == [
        ("tqdm", "4.26.0", "4.65.0")
    ]
    newest = "app v0.1.0\n└── tqdm v4.26.0 (latest: v4.70.0)\n"
    assert stale_dependencies("uv", newest, Registry(records), now) == [
        ("tqdm", "4.26.0", "4.67.13")
    ]


def test_the_target_has_passed_the_wait_when_a_newer_release_cannot_install() -> None:
    old, young = "2024-01-01T00:00:00+00:00", "2024-12-07T00:00:00+00:00"
    now = moment("2024-12-08T00:00:00+00:00")
    report = "app v0.1.0\n└── tqdm v1.0.0 (latest: v2.0.0)\n"

    def registry(dates: dict[str, str]) -> Registry:
        releases = {
            version: [{"upload_time_iso_8601": stamp}]
            for version, stamp in dates.items()
        }
        return Registry({PYPI + "tqdm/json": json.dumps({"releases": releases})})

    waiting = registry({"1.0.0": old, "2.0.0": young, "3.0.0": old})
    assert stale_dependencies("uv", report, waiting, now) == []
    between = registry({"1.0.0": old, "1.5.0": old, "2.0.0": young, "3.0.0": old})
    assert stale_dependencies("uv", report, between, now) == [
        ("tqdm", "1.0.0", "1.5.0")
    ]
