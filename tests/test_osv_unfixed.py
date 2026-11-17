"""A reported vulnerability passes only when public data proves that no fixed release exists."""

import json
import urllib.error
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace

import freshness
import pytest
import reports
from gate_config import Gate, Group, JsonObject

ID = "GHSA-aaaa-bbbb-cccc"
NPM = "https://registry.npmjs.org/picomatch"
PYPI = "https://pypi.org/pypi/ex-ample/json"
BOUNDED = [{"introduced": "0"}, {"last_affected": "4.0.7"}]


class Registry:
    def __init__(self, records: dict[str, object]) -> None:
        self.records = records
        self.requests: list[str] = []

    def __call__(self, url: str) -> object:
        self.requests.append(url)
        if url not in self.records:
            raise urllib.error.URLError(f"no recorded response for {url}")
        return self.records[url]


def npm(*versions: str) -> Registry:
    return Registry({NPM: {"versions": {version: {} for version in versions}}})


Events = list[dict[str, str]]


def advisory(events: Events, ecosystem: str, name: str) -> JsonObject:
    return {
        "affected": [
            {
                "package": {"ecosystem": ecosystem, "name": name},
                "ranges": [{"type": "SEMVER", "events": events}],
            }
        ]
    }


def package_item(
    events: Events,
    version: str = "4.0.7",
    ecosystem: str = "npm",
    name: str = "picomatch",
    record: str | None = None,
    more: dict[str, Events] | None = None,
    group: list[str] | None = None,
) -> JsonObject:
    found = {ID: events, **(more or {})}
    return {
        "package": {"name": name, "version": version, "ecosystem": ecosystem},
        "groups": [{"ids": group or list(found)}],
        "vulnerabilities": [
            {"id": key, **advisory(value, ecosystem, record or name)}
            for key, value in found.items()
        ],
    }


def report_of(tmp_path: Path, *items: JsonObject) -> Path:
    path = tmp_path / "osv.json"
    path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "source": {"path": "package-lock.json", "type": "lockfile"},
                        "packages": list(items),
                    }
                ]
            }
        )
    )
    return path


def accepted(path: Path, fetch: Registry) -> None:
    reports.validate_osv(path, unfixed=fetch)


def test_an_advisory_with_no_fix_and_no_newer_release_passes_and_is_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = report_of(tmp_path, package_item(BOUNDED))
    accepted(path, npm("4.0.6", "4.0.7"))
    printed = capsys.readouterr().out
    assert "picomatch@4.0.7" in printed
    assert ID in printed
    assert "will fail as soon as a fixed release exists" in printed
    assert "no reported vulnerabilities" not in printed


def test_an_open_range_with_no_fix_passes_with_no_registry_read(
    tmp_path: Path,
) -> None:
    registry = npm("9.9.9")
    accepted(report_of(tmp_path, package_item([{"introduced": "0"}])), registry)
    assert registry.requests == []


def test_an_advisory_with_a_fixed_event_fails_without_a_registry_read(
    tmp_path: Path,
) -> None:
    registry = npm("4.0.7", "4.0.8")
    with pytest.raises(ValueError, match="vulnerable packages: picomatch@4.0.7"):
        accepted(report_of(tmp_path, package_item(FIXED)), registry)
    assert registry.requests == []


def test_a_fixed_event_in_a_second_range_fails(tmp_path: Path) -> None:
    item = package_item(BOUNDED)
    second = [{"introduced": "5"}, {"fixed": "6"}]
    item["vulnerabilities"] = [
        {
            "id": ID,
            "affected": [
                *advisory(BOUNDED, "npm", "picomatch")["affected"],
                *advisory(second, "npm", "picomatch")["affected"],
            ],
        }
    ]
    with pytest.raises(ValueError, match="fixed"):
        accepted(report_of(tmp_path, item), npm("4.0.7"))


@pytest.mark.parametrize(
    "release", ["4.0.8", "4.1.0", "5.0.0", "4.1.0-beta.1", "4.0.7.1", "next"]
)
def test_a_release_above_the_affected_range_or_an_unreadable_one_fails(
    tmp_path: Path, release: str
) -> None:
    with pytest.raises(ValueError, match=release):
        accepted(report_of(tmp_path, package_item(BOUNDED)), npm("4.0.7", release))


@pytest.mark.parametrize("release", ["4.0.7-rc.1", "4.0.6", "3.0.0", "4.0.7+build"])
def test_a_release_inside_or_below_the_affected_range_does_not_fail(
    tmp_path: Path, release: str
) -> None:
    accepted(report_of(tmp_path, package_item(BOUNDED)), npm("4.0.7", release))


FIXED = [{"introduced": "0"}, {"fixed": "4.0.8"}]


@pytest.mark.parametrize(
    "item",
    [
        package_item([{"introduced": "0"}, {"last_affected": "4.0.7-rc.1"}]),
        package_item(BOUNDED, version="4.0.9"),
        package_item(BOUNDED, version="latest"),
        package_item([{"introduced": "0"}, {"limit": "5"}]),
        package_item(BOUNDED, more={"GHSA-dddd-eeee-ffff": FIXED}),
        package_item(BOUNDED, record="other"),
        package_item(BOUNDED, group=[ID, "GHSA-gone-gone-gone"]),
    ],
    ids=[
        "prerelease-bound",
        "installed-above-bound",
        "installed-unreadable",
        "limit-event",
        "second-advisory-has-a-fix",
        "record-of-another-package",
        "group-id-with-no-record",
    ],
)
def test_any_doubt_about_the_proof_fails(tmp_path: Path, item: JsonObject) -> None:
    with pytest.raises(ValueError, match="vulnerable packages"):
        accepted(report_of(tmp_path, item), npm("4.0.7"))


def test_a_report_with_no_advisory_records_fails(tmp_path: Path) -> None:
    item = package_item(BOUNDED)
    item["vulnerabilities"] = []
    with pytest.raises(ValueError, match="vulnerable packages"):
        accepted(report_of(tmp_path, item), npm("4.0.7"))


def test_a_vulnerability_with_no_unfixed_mode_fails_as_before(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=f"vulnerable packages: picomatch@4.0.7: {ID}"):
        reports.validate_osv(report_of(tmp_path, package_item(BOUNDED)))


def test_a_registry_that_cannot_be_read_fails_and_says_so(tmp_path: Path) -> None:
    path = report_of(tmp_path, package_item(BOUNDED))
    with pytest.raises(ValueError, match="registry.*no recorded response"):
        accepted(path, Registry({}))
    broken = Registry({NPM: {"dist-tags": {}}})
    with pytest.raises(ValueError, match="registry"):
        accepted(path, broken)


def test_a_clean_report_reads_no_registry(tmp_path: Path) -> None:
    clean = {"package": {"name": "a", "version": "1", "ecosystem": "npm"}}
    registry = npm("1")
    accepted(report_of(tmp_path, clean), registry)
    assert registry.requests == []


def pypi(*releases: str) -> Registry:
    return Registry(
        {PYPI: {"releases": {version: [{"filename": "f"}] for version in releases}}}
    )


def test_a_python_advisory_with_no_fix_passes_and_a_newer_release_fails(
    tmp_path: Path,
) -> None:
    item = package_item(
        [{"introduced": "0"}, {"last_affected": "2.1"}],
        version="2.1",
        ecosystem="PyPI",
        name="ex-ample",
        record="Ex_ample",
    )
    path = report_of(tmp_path, item)
    accepted(path, pypi("2.0", "2.1", "2.1rc1"))
    with pytest.raises(ValueError, match="2.1.post1"):
        accepted(path, pypi("2.1", "2.1.post1"))


def test_an_ecosystem_with_no_registry_reader_fails(tmp_path: Path) -> None:
    item = package_item(BOUNDED, ecosystem="Go", name="example.com/x")
    with pytest.raises(ValueError, match="Go"):
        accepted(report_of(tmp_path, item), Registry({}))


def run_gate(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    code: int,
    item: JsonObject,
) -> bool:
    (tmp_path / "bun.lock").write_text("{}")
    gate: Gate = {
        "name": "vulnerabilities",
        "role": "vulnerabilities",
        "command": [
            "osv-scanner",
            "--lockfile=bun.lock",
            "--output-file=coverage/osv.json",
        ],
        "report": {"type": "osv", "path": "coverage/osv.json"},
    }
    group: Group = {
        "path": ".",
        "language": "javascript",
        "sources": [],
        "depends_on": [],
        "checks": [gate],
    }

    def scan(_group: Group, _gate: Gate, _command: list[str], *_rest: object) -> object:
        report_of(tmp_path, item).replace(tmp_path / "coverage/osv.json")
        return SimpleNamespace(returncode=code)

    monkeypatch.setattr(runner, "run_projects", scan)
    monkeypatch.setattr(freshness, "fetch_json", npm("4.0.7"))
    return runner.run_limited_gate(group, gate, 60, nullcontext(), [group])


def test_the_gate_passes_when_the_scanner_found_only_advisories_with_no_fix(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert not run_gate(runner, tmp_path, monkeypatch, 1, package_item(BOUNDED))
    printed = capsys.readouterr().out
    assert "will fail as soon as a fixed release exists" in printed
    assert "PASS vulnerabilities" in printed
    assert "no reported vulnerabilities" not in printed


def test_the_gate_fails_when_one_advisory_has_a_fix(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert run_gate(runner, tmp_path, monkeypatch, 1, package_item(FIXED))


@pytest.mark.parametrize("code", [127, 128, 2])
def test_the_gate_fails_on_any_scanner_exit_other_than_found_vulnerabilities(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    assert run_gate(runner, tmp_path, monkeypatch, code, package_item(BOUNDED))


def test_the_gate_fails_when_the_scanner_exits_1_and_the_report_holds_no_finding(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clean = {"package": {"name": "a", "version": "1", "ecosystem": "npm"}}
    assert run_gate(runner, tmp_path, monkeypatch, 1, clean)
