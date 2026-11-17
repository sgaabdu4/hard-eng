"""A reported vulnerability passes only when public data proves that no fixed release exists."""

import json
import subprocess
import sys
import urllib.error
from collections.abc import Callable
from contextlib import nullcontext
from email.message import Message
from pathlib import Path
from types import ModuleType, SimpleNamespace

import freshness
import osv_report
import pytest
import reports
from gate_config import Gate, Group
from test_freshness import Registry

ID = "GHSA-aaaa-bbbb-cccc"
NPM = "https://registry.npmjs.org/picomatch"
PYPI = "https://pypi.org/pypi/ex-ample/json"
BOUNDED = [{"introduced": "0"}, {"last_affected": "4.0.7"}]


def npm(*versions: str) -> Registry:
    return Registry({NPM: json.dumps({"versions": {key: {} for key in versions}})})


Events = list[dict[str, str]]
Item = dict[str, object]


def affected(events: Events, ecosystem: str, name: str) -> Item:
    return {
        "package": {"ecosystem": ecosystem, "name": name},
        "ranges": [{"type": "SEMVER", "events": events}],
    }


def package_item(
    events: Events,
    version: str = "4.0.7",
    ecosystem: str = "npm",
    name: str = "picomatch",
    record: str | None = None,
    more: dict[str, Events] | None = None,
    group: list[str] | None = None,
) -> Item:
    found = {ID: events, **(more or {})}
    return {
        "package": {"name": name, "version": version, "ecosystem": ecosystem},
        "groups": [{"ids": group or list(found)}],
        "vulnerabilities": [
            {"id": key, "affected": [affected(value, ecosystem, record or name)]}
            for key, value in found.items()
        ],
    }


def report_of(tmp_path: Path, *items: Item) -> Path:
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


def test_an_advisory_with_a_fixed_event_fails_without_a_registry_read(
    tmp_path: Path,
) -> None:
    registry = npm("4.0.7", "4.0.8")
    with pytest.raises(ValueError, match="vulnerable packages: picomatch@4.0.7"):
        accepted(report_of(tmp_path, package_item(FIXED)), registry)
    assert registry.requests == []


def test_a_fixed_event_in_a_second_range_fails(tmp_path: Path) -> None:
    item = package_item(BOUNDED)
    second: Events = [{"introduced": "5"}, {"fixed": "6"}]
    item["vulnerabilities"] = [
        {
            "id": ID,
            "affected": [
                affected(BOUNDED, "npm", "picomatch"),
                affected(second, "npm", "picomatch"),
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
def test_any_doubt_about_the_proof_fails(tmp_path: Path, item: Item) -> None:
    with pytest.raises(ValueError, match="vulnerable packages"):
        accepted(report_of(tmp_path, item), npm("4.0.7"))


def test_a_report_with_no_advisory_records_fails(tmp_path: Path) -> None:
    item = package_item(BOUNDED)
    item["vulnerabilities"] = list[Item]()
    with pytest.raises(ValueError, match="vulnerable packages"):
        accepted(report_of(tmp_path, item), npm("4.0.7"))


def test_a_vulnerability_with_no_unfixed_mode_fails_as_before(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=f"vulnerable packages: picomatch@4.0.7: {ID}"):
        reports.validate_osv(report_of(tmp_path, package_item(BOUNDED)))


def test_a_registry_that_cannot_be_read_fails_and_says_so(tmp_path: Path) -> None:
    path = report_of(tmp_path, package_item(BOUNDED))
    with pytest.raises(ValueError, match="registry.*no recorded response"):
        accepted(path, Registry({}))
    broken = Registry({NPM: '{"dist-tags": {}}'})
    with pytest.raises(ValueError, match="registry"):
        accepted(path, broken)


def test_a_clean_report_reads_no_registry(tmp_path: Path) -> None:
    clean: Item = {"package": {"name": "a", "version": "1", "ecosystem": "npm"}}
    registry = npm("1")
    accepted(report_of(tmp_path, clean), registry)
    assert registry.requests == []


def pypi(*releases: str) -> Registry:
    files = [{"filename": "f"}]
    return Registry({PYPI: json.dumps({"releases": dict.fromkeys(releases, files)})})


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


@pytest.mark.parametrize("release", ["2.1.post1", "2.1-1", "1!2.0", "2.1.1"])
def test_a_python_release_that_may_sort_above_the_bound_fails(
    tmp_path: Path, release: str
) -> None:
    item = package_item(
        [{"introduced": "0"}, {"last_affected": "2.1"}],
        version="2.1",
        ecosystem="PyPI",
        name="ex-ample",
    )
    with pytest.raises(ValueError, match="above"):
        accepted(report_of(tmp_path, item), pypi("2.1", release))


@pytest.mark.parametrize(
    ("release", "passes"), [("4.0.7+1", False), ("4.0.7-rc.1", True)]
)
def test_a_pub_build_suffix_sorts_above_its_release_and_a_pre_release_below(
    tmp_path: Path, release: str, passes: bool
) -> None:
    item = package_item(BOUNDED, ecosystem="Pub", name="ex")
    registry = Registry(
        {
            "https://pub.dev/api/packages/ex": json.dumps(
                {"versions": [{"version": "4.0.7"}, {"version": release}]}
            )
        }
    )
    if passes:
        accepted(report_of(tmp_path, item), registry)
    else:
        with pytest.raises(ValueError, match="above"):
            accepted(report_of(tmp_path, item), registry)


def test_a_range_with_no_end_that_starts_after_zero_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not start at 0"):
        accepted(
            report_of(tmp_path, package_item([{"introduced": "3.0.0"}])), npm("2.0.0")
        )


def test_a_report_the_scanner_wrote_with_no_results_is_not_accepted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "osv.json"
    path.write_text("{}")
    assert not osv_report.osv_unfixed_only(path)


def test_an_ecosystem_with_no_registry_reader_fails(tmp_path: Path) -> None:
    item = package_item(BOUNDED, ecosystem="Go", name="example.com/x")
    with pytest.raises(ValueError, match="Go"):
        accepted(report_of(tmp_path, item), Registry({}))


def run_gate(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    code: int,
    item: Item,
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
    clean: Item = {"package": {"name": "a", "version": "1", "ecosystem": "npm"}}
    assert run_gate(runner, tmp_path, monkeypatch, 1, clean)


MALICIOUS = Path(__file__).parent / "fixtures/osv/malicious-osv.json"
FLATMAP = "https://registry.npmjs.org/flatmap-stream"


def real_malware_report(tmp_path: Path, keep: str, open_range: bool = False) -> Path:
    report = json.loads(MALICIOUS.read_text())
    package = report["results"][0]["packages"][0]
    package["vulnerabilities"] = [
        found for found in package["vulnerabilities"] if found["id"] == keep
    ]
    package["groups"] = [{"ids": [keep]}]
    if open_range:
        entry = package["vulnerabilities"][0]["affected"][0]
        entry["ranges"] = [{"type": "SEMVER", "events": [{"introduced": "0"}]}]
    path = tmp_path / "osv.json"
    path.write_text(json.dumps(report))
    return path


def flatmap() -> Registry:
    return Registry({FLATMAP: json.dumps({"versions": {"0.1.1": {}}})})


@pytest.mark.parametrize(
    ("keep", "open_range"),
    [("MAL-2025-20690", False), ("GHSA-9x64-5r7x-2q53", True)],
    ids=["osv-malicious-package-record", "reviewed-advisory-for-embedded-malware"],
)
def test_a_malicious_package_record_never_passes_as_having_no_fix(
    tmp_path: Path, keep: str, open_range: bool
) -> None:
    path = real_malware_report(tmp_path, keep, open_range)
    with pytest.raises(ValueError, match="malicious"):
        accepted(path, flatmap())


def test_a_record_that_is_withdrawn_but_still_reported_fails(tmp_path: Path) -> None:
    item = package_item(BOUNDED)
    item["vulnerabilities"] = [
        {
            "id": ID,
            "withdrawn": "2026-01-01T00:00:00Z",
            "affected": [affected(BOUNDED, "npm", "picomatch")],
        }
    ]
    with pytest.raises(ValueError, match="withdrawn"):
        accepted(report_of(tmp_path, item), npm("4.0.7"))


def refuse_with(error: Exception) -> Callable[[str], object]:
    def fetch(_url: str) -> object:
        raise error

    return fetch


def answer(body: object) -> Callable[[str], object]:
    return lambda _url: body


NOT_FOUND = urllib.error.HTTPError("https://r", 404, "Not Found", Message(), None)


@pytest.mark.parametrize(
    ("ecosystem", "fetch"),
    [
        ("npm", refuse_with(TimeoutError("timed out"))),
        ("npm", refuse_with(json.JSONDecodeError("bad", "{", 1))),
        ("npm", refuse_with(NOT_FOUND)),
        ("npm", answer({"error": "Not found"})),
        ("npm", answer(["4.0.7"])),
        ("PyPI", refuse_with(NOT_FOUND)),
        ("PyPI", answer({"message": "Not Found"})),
        ("Pub", refuse_with(NOT_FOUND)),
        ("Pub", answer({"error": {"code": "NotFound"}})),
    ],
    ids=[
        "npm-timeout",
        "npm-bad-json",
        "npm-404",
        "npm-missing-package-body",
        "npm-wrong-shape",
        "pypi-404",
        "pypi-missing-package-body",
        "pub-404",
        "pub-missing-package-body",
    ],
)
def test_a_registry_that_fails_or_lacks_the_package_fails_the_gate(
    tmp_path: Path, ecosystem: str, fetch: Callable[[str], object]
) -> None:
    item = package_item(BOUNDED, ecosystem=ecosystem, name="ex")
    with pytest.raises(ValueError, match="registry could not be read"):
        reports.validate_osv(report_of(tmp_path, item), unfixed=fetch)


def test_loading_the_hook_and_gate_modules_loads_no_osv_module() -> None:
    hooks = Path(reports.__file__).parent
    program = (
        f"import sys; sys.path.insert(0, {str(hooks)!r}); "
        "import reports, gate_runner, agent_hooks, polling, failures; "
        "print([m for m in ('osv_report', 'osv_unfixed', 'freshness') if m in sys.modules])"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", program],
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout.strip() == "[]"


FOLDER = Path(__file__).parent / "fixtures/osv"


def real_report(tmp_path: Path, name: str) -> Path:
    path = tmp_path / "osv.json"
    path.write_text((FOLDER / name).read_text())
    return path


def registry(url: str, *versions: str) -> Registry:
    return Registry({url: json.dumps({"versions": {key: {} for key in versions}})})


def releases(url: str, *versions: str) -> Registry:
    files = [{"filename": "f"}]
    return Registry({url: json.dumps({"releases": dict.fromkeys(versions, files)})})


@pytest.mark.parametrize(
    ("report", "fetch", "newer"),
    [
        (
            "grapesjs-osv.json",
            registry("https://registry.npmjs.org/grapesjs", "0.19.4", "0.19.5"),
            "0.19.5",
        ),
        (
            "ldapauth-osv.json",
            registry("https://registry.npmjs.org/ldapauth", "2.2.3", "2.2.4"),
            "2.2.4",
        ),
        (
            "vyper-osv.json",
            releases("https://pypi.org/pypi/vyper/json", "0.3.7", "0.4.0"),
            "0.4.0",
        ),
    ],
    ids=["grapesjs", "ldapauth", "vyper"],
)
def test_a_range_open_from_zero_fails_when_the_registry_has_a_newer_release(
    tmp_path: Path, report: str, fetch: Registry, newer: str
) -> None:
    with pytest.raises(ValueError, match=f"release {newer} is above"):
        accepted(real_report(tmp_path, report), fetch)


def test_a_range_open_from_zero_passes_when_the_installed_release_is_the_newest(
    tmp_path: Path,
) -> None:
    fetch = registry("https://registry.npmjs.org/grapesjs", "0.19.3", "0.19.4")
    accepted(real_report(tmp_path, "grapesjs-osv.json"), fetch)
    assert fetch.requests == ["https://registry.npmjs.org/grapesjs"]


def test_the_lowest_last_affected_of_several_advisories_sets_the_bound(
    tmp_path: Path,
) -> None:
    item = package_item(
        BOUNDED,
        more={"GHSA-dddd-eeee-ffff": [{"introduced": "0"}, {"last_affected": "4.0.9"}]},
    )
    with pytest.raises(ValueError, match="release 4.0.8 is above"):
        accepted(report_of(tmp_path, item), npm("4.0.7", "4.0.8"))


def test_a_pub_release_that_was_retracted_is_not_a_fix(tmp_path: Path) -> None:
    item = package_item(BOUNDED, ecosystem="Pub", name="ex")
    versions = [{"version": "4.0.7"}, {"version": "4.0.8", "retracted": True}]
    fetch = Registry(
        {"https://pub.dev/api/packages/ex": json.dumps({"versions": versions})}
    )
    accepted(report_of(tmp_path, item), fetch)


OPEN = [{"introduced": "0"}]


@pytest.mark.parametrize(
    ("ecosystem", "installed", "fetch", "newer"),
    [
        ("npm", "1.0.0-beta.1", npm("1.0.0-beta.1", "1.0.0"), "1.0.0"),
        ("npm", "1.0.0-beta.1", npm("1.0.0-beta.1", "1.0.0-beta.2"), "1.0.0-beta.2"),
        ("PyPI", "1.0rc1", pypi("1.0rc1", "1.0"), "1.0"),
    ],
    ids=["npm-release", "npm-later-pre-release", "pypi-release"],
)
def test_an_installed_pre_release_fails_when_a_later_release_exists(
    tmp_path: Path, ecosystem: str, installed: str, fetch: Registry, newer: str
) -> None:
    item = package_item(OPEN, version=installed, ecosystem=ecosystem, name="picomatch")
    if ecosystem == "PyPI":
        item = package_item(
            OPEN, version=installed, ecosystem=ecosystem, name="ex-ample"
        )
    with pytest.raises(ValueError, match=f"release {newer} is above"):
        accepted(report_of(tmp_path, item), fetch)


def test_an_installed_pre_release_passes_when_it_is_the_newest(tmp_path: Path) -> None:
    item = package_item(OPEN, version="1.0.0-beta.1")
    accepted(report_of(tmp_path, item), npm("0.9.0", "1.0.0-beta.1"))


def test_an_open_range_still_counts_when_the_same_advisory_has_a_closed_range(
    tmp_path: Path,
) -> None:
    ranges = [
        {"type": "SEMVER", "events": OPEN},
        {"type": "SEMVER", "events": [{"introduced": "0"}, {"last_affected": "1.0.2"}]},
    ]
    entry = {"package": {"ecosystem": "npm", "name": "picomatch"}, "ranges": ranges}
    item = package_item(OPEN, version="1.0.0")
    item["vulnerabilities"] = [{"id": ID, "affected": [entry]}]
    with pytest.raises(ValueError, match="release 1.0.1 is above"):
        accepted(report_of(tmp_path, item), npm("1.0.0", "1.0.1"))
