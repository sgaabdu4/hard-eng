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
from freshness import validate_freshness, validate_holds
from gate_config import Gate, Group, JsonObject, validate_gate
from gitleaks_scan import run_gate_command

FIXTURES = Path(__file__).parent / "fixtures/freshness"
PUB = "https://pub.dev/api/packages/"
PYPI = "https://pypi.org/pypi/"


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
        path, freshness_gate(tool, holds), registry or Registry({}), moment(now)
    )


def test_bun_fails_on_release_older_than_two_days(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"is-odd 2\.0\.0 → 3\.0\.1") as failure:
        check(tmp_path, "bun", fixture("bun-outdated.txt"))
    assert "left-pad 1.2.0 → 1.3.0" in str(failure.value)
    check(tmp_path, "bun", fixture("bun-current-with-star.txt"))
    check(tmp_path, "bun", fixture("bun-up-to-date.txt"))
    with pytest.raises(ValueError, match="bun output is unreadable"):
        check(tmp_path, "bun", "")


def dart_registry() -> Registry:
    return Registry(
        {
            PUB + "http": fixture("pub-http.json"),
            PUB + "lints": fixture("pub-lints.json"),
        }
    )


def test_dart_uses_pub_dates_for_direct_dependencies(tmp_path: Path) -> None:
    report = fixture("dart-outdated.json")
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
    with pytest.raises(ValueError, match="uv output is unreadable"):
        check(tmp_path, "uv", "error: failed to fetch", Registry(records))


def test_poetry_reads_outdated_with_wait(tmp_path: Path) -> None:
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
        ("bun", "bun-outdated.txt", "bun update --latest is-odd left-pad"),
        (
            "dart",
            "dart-outdated.json",
            "dart pub upgrade --major-versions http lints",
        ),
        (
            "flutter",
            "dart-outdated.json",
            "flutter pub upgrade --major-versions http lints",
        ),
        ("uv", "uv-tree.txt", "uv add httpx@latest pytest@latest"),
        ("poetry", "poetry-show.json", "poetry add httpx@latest pytest@latest"),
    ],
)
def test_failure_names_upgrade_route(
    tmp_path: Path, tool: str, report: str, command: str
) -> None:
    records = {
        PUB + "http": fixture("pub-http.json"),
        PUB + "lints": fixture("pub-lints.json"),
        PYPI + "httpx/json": fixture("pypi-httpx.json"),
        PYPI + "pytest/json": fixture("pypi-pytest.json"),
    }
    with pytest.raises(ValueError, match="baseline repair") as failure:
        check(
            tmp_path,
            tool,
            fixture(report),
            Registry(records),
            "2025-11-11T18:27:56+00:00"
            if "dart" in report
            else "2024-12-04T00:00:00+00:00",
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
    ],
    ids=["registry-down", "stale", "current"],
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
