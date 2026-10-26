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
from freshness import stale_dependencies, validate_freshness, validate_holds
from gate_config import Gate, Group, JsonObject, validate_gate, validate_required_checks
from gitleaks_scan import run_gate_command
from project_setup import add_freshness
from shipping import ShippingPolicy
from test_setup import repository

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
        (
            "uv",
            "uv-tree.txt",
            "uv add [--group <group>] 'httpx>=0.28.0' 'pytest>=8.3.4'",
        ),
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
