"""A failed gate prints what its report found, and a run with no tests gets no hint."""

import json
from pathlib import Path

import pytest
import reports
from gate_config import Gate
from test_reports import REPORTS

PARALLEL = ["uv", "run", "pytest", "-n", "auto"]
NO_GATE: Gate = {"name": "scan", "command": []}


def failed(
    scanner: str, path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> str:
    reports.scanner_result(False, scanner, NO_GATE, path, [], tmp_path, 1.0)
    return capsys.readouterr().out


def test_a_run_with_no_tests_gets_no_parallel_hint() -> None:
    assert reports.parallel_hint(5, True, PARALLEL) == ""
    assert "-n 0" in reports.parallel_hint(1, True, PARALLEL)


def test_a_failed_secret_scan_names_rule_file_and_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    token = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
    result = {
        "ruleId": "github-pat",
        "message": {"text": f"github-pat has detected secret for file main.py {token}"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": "main.py"},
                    "region": {"startLine": 5, "snippet": {"text": token}},
                }
            }
        ],
        "partialFingerprints": {"commitSha": "0" * 40},
    }
    report = json.loads(
        '{"version":"2.1.0","runs":[{"tool":{"driver":{"name":"gitleaks","rules":[]}}}]}'
    )
    report["runs"][0]["results"] = [result]
    path = tmp_path / "gitleaks.sarif"
    path.write_text(json.dumps(report))
    output = failed("gitleaks", path, tmp_path, capsys)
    assert "github-pat main.py 5" in output
    assert token not in output
    assert "ghp_" not in output


def test_a_failed_react_doctor_gate_prints_its_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = json.loads(REPORTS["react-doctor"])
    report["ok"] = False
    report["diagnostics"] = [
        {
            "filePath": "src/List.tsx",
            "plugin": "react-doctor",
            "rule": "no-derived-state",
            "severity": "warning",
            "message": "Do not copy a prop into state",
            "line": 6,
        },
        {
            "filePath": "src/List.tsx",
            "rule": "no-array-index-as-key",
            "message": "Do not use the index as key",
        },
    ]
    path = tmp_path / "react-doctor.json"
    path.write_text(json.dumps(report))
    output = failed("react-doctor", path, tmp_path, capsys)
    assert "src/List.tsx" in output
    assert "no-derived-state" in output
    assert "Do not copy a prop into state" in output
    assert "no-array-index-as-key" in output


def test_a_failed_fallow_gate_prints_its_findings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    no_files: list[object] = []
    report = {
        "kind": "combined",
        "check": {
            "total_issues": 2,
            "unused_exports": [
                {
                    "path": "src/math.ts",
                    "export_name": "quadruple",
                    "is_type_only": False,
                    "line": 3,
                    "col": 0,
                }
            ],
            "unused_dependencies": [
                {
                    "package_name": "is-odd",
                    "location": "dependencies",
                    "path": "package.json",
                    "line": 9,
                }
            ],
            "unused_files": no_files,
        },
    }
    path = tmp_path / "fallow.json"
    path.write_text(json.dumps(report))
    output = failed("fallow", path, tmp_path, capsys)
    assert "src/math.ts" in output
    assert "quadruple" in output
    assert "is-odd" in output
    assert "package.json" in output


@pytest.mark.parametrize("scanner", ["gitleaks", "react-doctor", "fallow"])
def test_a_missing_or_unreadable_report_prints_nothing_new(
    scanner: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert failed(scanner, tmp_path / "missing.json", tmp_path, capsys) == ""
    broken = tmp_path / "broken.json"
    broken.write_text("{")
    assert failed(scanner, broken, tmp_path, capsys) == ""
