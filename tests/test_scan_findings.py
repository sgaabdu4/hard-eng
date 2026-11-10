"""A failed scanner gate prints what its report found; every report type is accounted for."""

import json
from pathlib import Path

import pytest
import reports
import scan_findings
from test_report_findings import failed

IMPORT_LINTER_BROKEN = """
---------
Contracts
---------

Analyzed 3 files, 2 dependencies.
---------------------------------

No sibling dependency cycles BROKEN

Contracts: 0 kept, 1 broken.


----------------
Broken contracts
----------------

No sibling dependency cycles
----------------------------

No cycles are allowed in greeter.
It could be made acyclic by removing 1 dependency:

- .quiet -> .loud (1 import)

"""


def report_file(tmp_path: Path, name: str, content: object) -> Path:
    path = tmp_path / name
    path.write_text(content if isinstance(content, str) else json.dumps(content))
    return path


def test_a_failed_semgrep_gate_prints_rule_place_and_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def finding(rule: str, line: int, message: str) -> dict[str, object]:
        return {
            "check_id": f"generic.secrets.security.{rule}.{rule}",
            "path": "creds.go",
            "start": {"line": line, "col": 17, "offset": 30},
            "end": {"line": line, "col": 37, "offset": 50},
            "extra": {
                "message": message,
                "severity": "ERROR",
                "fingerprint": "requires login",
                "lines": "requires login",
            },
        }

    results = [
        finding("detected-aws-access-key-id-value", 3, "AWS Access Key ID detected."),
        finding("detected-aws-secret-access-key", 4, "AWS Secret Access Key detected"),
    ]
    path = report_file(tmp_path, "semgrep.json", {"version": "1.0", "results": results})
    first = "detected-aws-access-key-id-value"
    second = "detected-aws-secret-access-key"
    assert failed("semgrep", path, tmp_path, capsys).splitlines() == [
        f"scan: creds.go:3 generic.secrets.security.{first}.{first} AWS Access Key ID detected.",
        f"scan: creds.go:4 generic.secrets.security.{second}.{second} AWS Secret Access Key detected",
    ]


def test_a_failed_trivy_gate_prints_id_title_and_place(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def misconfiguration(
        identifier: str, title: str, cause: dict[str, object]
    ) -> dict[str, object]:
        return {
            "Type": "Dockerfile Security Check",
            "ID": identifier,
            "Title": title,
            "Message": "Specify a tag in the 'FROM' statement for image 'node'",
            "Severity": "MEDIUM",
            "Status": "FAIL",
            "CauseMetadata": {"Provider": "Dockerfile", "Service": "general", **cause},
        }

    found = [
        misconfiguration("DS-0001", "':latest' tag used", {"StartLine": 1}),
        misconfiguration("DS-0002", "Image user should not be 'root'", {}),
    ]
    result = {
        "Target": "Dockerfile",
        "Class": "config",
        "Type": "dockerfile",
        "MisconfSummary": {"Successes": 24, "Failures": 2},
        "Misconfigurations": found,
    }
    path = report_file(
        tmp_path, "trivy.json", {"SchemaVersion": 2, "Results": [result]}
    )
    assert failed("trivy", path, tmp_path, capsys).splitlines() == [
        "scan: Dockerfile:1 DS-0001 ':latest' tag used",
        "scan: Dockerfile DS-0002 Image user should not be 'root'",
    ]


def test_a_failed_dart_decimate_gate_prints_its_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    finding = {
        "rule_id": "dart-decimate/unlisted-dependency",
        "fingerprint": None,
        "kind": "unlisted-dependency",
        "severity": "error",
        "message": "app imports test but does not declare it in pubspec.yaml",
        "path": "test/tool/build_test.dart",
        "line": 1,
        "column": 0,
        "edge": {"from": "test/tool/build_test.dart", "to": "test"},
    }
    report = {
        "schema_version": "dart-decimate.report.v1",
        "command": "check",
        "verdict": "fail",
        "findings": [finding],
    }
    path = report_file(tmp_path, "dart-decimate.json", report)
    rule = "dart-decimate/unlisted-dependency"
    message = "app imports test but does not declare it in pubspec.yaml"
    assert failed("dart-decimate", path, tmp_path, capsys).splitlines() == [
        f"scan: test/tool/build_test.dart:1 {rule} {message}"
    ]


def test_a_failed_jscpd_gate_names_every_copy_without_its_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def copy(name: str) -> dict[str, object]:
        place = {"line": 10, "column": 36, "position": 244}
        return {"name": name, "start": 1, "end": 10, "endLoc": place}

    clone = {
        "firstFile": copy("a.py"),
        "secondFile": copy("b.py"),
        "format": "python",
        "fragment": "def total(values):\n    result = 0\n    return result",
        "isNew": False,
        "kind": "exact",
        "lines": 10,
        "tokens": 47,
    }
    path = report_file(tmp_path, "jscpd-report.json", {"duplicates": [clone]})
    output = failed("jscpd", path, tmp_path, capsys)
    assert output.splitlines() == ["scan: copied code a.py:1-10 b.py:1-10"]
    assert "def total" not in output


def clone_between(first: tuple[str, int], second: tuple[str, int]) -> dict[str, object]:
    def copy(name: str, start: int) -> dict[str, object]:
        return {"name": name, "start": start, "end": start + 15}

    return {"firstFile": copy(*first), "secondFile": copy(*second)}


def scanned_tree(root: Path, group: str) -> Path:
    command = ["jscpd", "src", "tests", "--format", "python", "--reporters", "json"]
    gate = {
        "name": "duplicates",
        "command": [*command, "--output", "coverage/jscpd"],
        "report": {"type": "jscpd", "path": "coverage/jscpd/jscpd-report.json"},
    }
    folder = root / group
    for name in ("src/pkg/a.py", "src/pkg/b.py", "tests/pkg/a.py"):
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text("x = 1\n")
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"shared": [], "packages": [{"path": group, "checks": [gate]}]})
    )
    clones = [
        clone_between(("pkg/a.py", 1), ("pkg/b.py", 3)),
        clone_between(("pkg/a.py", 1), ("pkg/a.py", 1)),
    ]
    (folder / "coverage/jscpd").mkdir(parents=True)
    output = folder / "coverage/jscpd"
    return report_file(output, "jscpd-report.json", {"duplicates": clones})


@pytest.mark.parametrize(("group", "prefix"), [("shop", "shop/"), (".", "")])
def test_copied_code_lines_name_paths_from_the_repository_root(
    tmp_path: Path, group: str, prefix: str
) -> None:
    path = scanned_tree(tmp_path, group)
    both = f"{prefix}src/pkg/a.py or {prefix}tests/pkg/a.py"
    assert scan_findings.jscpd_findings(path) == [
        f"copied code {both}:1-16 {prefix}src/pkg/b.py:3-18",
        f"copied code {both}:1-16 {both}:1-16",
    ]
    (tmp_path / "hard-eng.gates.json").unlink()
    assert scan_findings.jscpd_findings(path)[0] == (
        "copied code pkg/a.py:1-16 pkg/b.py:3-18"
    )


def test_a_failed_import_linter_gate_prints_its_broken_contracts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = report_file(tmp_path, "import-linter.txt", IMPORT_LINTER_BROKEN)
    assert failed("import-linter", path, tmp_path, capsys).splitlines() == [
        "scan: broken contract: No sibling dependency cycles",
        "scan: No cycles are allowed in greeter.",
        "scan: It could be made acyclic by removing 1 dependency:",
        "scan: - .quiet -> .loud (1 import)",
    ]
    error = "Could not find package 'nonexistent' in your Python path.\n"
    path = report_file(tmp_path, "no-package.txt", error)
    assert failed("import-linter", path, tmp_path, capsys).splitlines() == [
        "scan: Could not find package 'nonexistent' in your Python path."
    ]


def test_a_failed_dart_performance_gate_prints_its_failing_test(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    start = {"id": 3, "name": "renders fast", "line": 4, "url": None}
    events = [
        {"test": start, "type": "testStart"},
        {"testID": 3, "error": "Expected: <5>\n  Actual: <4>\n", "type": "error"},
        {"testID": 3, "result": "failure", "hidden": False, "type": "testDone"},
    ]
    path = report_file(
        tmp_path, "performance.jsonl", "\n".join(json.dumps(e) for e in events)
    )
    output = failed("performance-dart", path, tmp_path, capsys)
    assert (
        output == "scan: Dart test failure: renders fast: Expected: <5> Actual: <4>\n"
    )


def test_a_failed_container_scan_names_its_vulnerable_packages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    package = {
        "package": {"name": "minimist", "version": "0.0.8", "ecosystem": "npm"},
        "vulnerabilities": [{"id": "GHSA-vh95-rmgr-6w4m"}],
        "groups": [{"ids": ["GHSA-vh95-rmgr-6w4m"]}],
    }
    layers = [{"diff_id": "sha256:" + "a" * 64, "is_empty": False}]
    report = {
        "results": [{"source": {"path": "image", "type": "os"}, "packages": [package]}],
        "image_metadata": {"layer_metadata": layers},
    }
    path = report_file(tmp_path, "osv-image.json", report)
    output = failed("osv-image", path, tmp_path, capsys)
    assert (
        output
        == "OSV reports vulnerable packages: minimist@0.0.8: GHSA-vh95-rmgr-6w4m\n"
    )


@pytest.mark.parametrize(
    "scanner",
    ["semgrep", "trivy", "dart-decimate", "jscpd", "import-linter", "performance-dart"],
)
def test_a_report_of_an_unknown_shape_prints_no_line(
    scanner: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    content = "" if scanner == "import-linter" else {"results": 7, "Results": 7}
    odd = report_file(tmp_path, "odd.json", content)
    assert failed(scanner, odd, tmp_path, capsys) == ""
    assert failed(scanner, tmp_path / "missing.json", tmp_path, capsys) == ""


def test_every_report_type_shows_its_findings_on_a_failure() -> None:
    import scan_findings

    shown = set(reports.FINDING_READERS) | scan_findings.PRINTED_ELSEWHERE
    assert set(reports.SCANNERS) - shown == set()
    assert scan_findings.PRINTED_ELSEWHERE <= set(reports.SCANNERS)
    assert not set(reports.FINDING_READERS) & scan_findings.PRINTED_ELSEWHERE
