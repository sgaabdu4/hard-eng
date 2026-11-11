"""A failed gate prints what its report found, and a run with no tests gets no hint."""

import json
from pathlib import Path

import pytest
import reports
from gate_config import Gate
from process_group import parallel_hint
from test_reports import REPORTS

PARALLEL = ["uv", "run", "pytest", "-n", "auto"]
NO_GATE: Gate = {"name": "scan", "command": []}


def failed(
    scanner: str, path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> str:
    reports.scanner_result(False, scanner, NO_GATE, path, [], tmp_path, 1.0)
    return capsys.readouterr().out


def test_a_run_with_no_tests_gets_no_parallel_hint() -> None:
    assert parallel_hint(5, True, PARALLEL) == ""
    assert "-n 0" in parallel_hint(1, True, PARALLEL)


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
    assert output == "scan: github-pat main.py:5 in commit 000000000000\n"
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
    assert "scan: src/List.tsx:6 no-derived-state" in output
    assert "src/List.tsx no-array-index-as-key" in output
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
    assert "src/math.ts:3 unused_exports quadruple" in output
    assert "package.json:9 unused_dependencies is-odd" in output


def test_a_failed_fallow_gate_prints_findings_that_have_no_path_of_their_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = {"path": "src/a.ts", "line": 2, "col": 7}
    script = {"path": "package.json", "line": 11, "col": 0, "script_name": "lint"}
    edge = {"path": "src/b.ts", "line": 1, "col": 9}
    check = {
        "unlisted_dependencies": [
            {"package_name": "left-pad", "imported_from": [site]}
        ],
        "unlisted_binaries": [{"binary_name": "fallow", "used_in": [script]}],
        "circular_dependencies": [
            {"files": ["src/a.ts", "src/b.ts"], "length": 2, "line": 1, "edges": [edge]}
        ],
    }
    path = tmp_path / "fallow.json"
    path.write_text(json.dumps({"kind": "combined", "check": check, "dupes": {}}))
    assert failed("fallow", path, tmp_path, capsys).splitlines() == [
        "scan: src/a.ts:2 unlisted_dependencies left-pad",
        "scan: package.json:11 unlisted_binaries fallow",
        "scan: src/a.ts:1 circular_dependencies src/a.ts -> src/b.ts",
    ]


def test_a_fallow_workspace_note_that_fails_the_gate_is_named(
    tmp_path: Path,
) -> None:
    note = {
        "path": "node_modules",
        "kind": "node-modules-missing",
        "message": "'node_modules' does not exist. Run bun install first.",
        "degrades_analysis": True,
    }
    report = json.loads(REPORTS["fallow"])
    report["workspace_diagnostics"] = [note]
    path = tmp_path / "fallow.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="node-modules-missing") as error:
        reports.validate_fallow(path)
    assert note["message"] in str(error.value)


def test_a_failed_fallow_audit_prints_its_findings_and_no_workspace_note(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    copies = [
        {"file": "src/alpha.ts", "start_line": 1, "end_line": 33, "fragment": "x"},
        {"file": "src/beta.ts", "start_line": 1, "end_line": 33, "fragment": "x"},
    ]
    report = {
        "kind": "audit",
        "command": "audit",
        "verdict": "fail",
        "dead_code": {
            "unused_files": [{"path": "src/List.tsx", "introduced": True}],
            "workspace_diagnostics": [
                {"path": ".", "kind": "rule-packs-not-configured", "message": "note"}
            ],
        },
        "duplication": {"clone_groups": [{"instances": copies}]},
    }
    path = tmp_path / "fallow.json"
    path.write_text(json.dumps(report))
    assert failed("fallow", path, tmp_path, capsys).splitlines() == [
        "scan: src/List.tsx unused_files",
        "scan: copied code src/alpha.ts:1-33 src/beta.ts:1-33",
    ]


def test_a_failed_fallow_gate_names_every_copy_without_its_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    group = {
        "instances": [
            {
                "file": "src/alpha.ts",
                "start_line": 1,
                "end_line": 33,
                "fragment": "SECRET_BODY",
            },
            {
                "file": "src/beta.ts",
                "start_line": 4,
                "end_line": 36,
                "fragment": "SECRET_BODY",
            },
        ]
    }
    path = tmp_path / "fallow.json"
    path.write_text(json.dumps({"check": {}, "dupes": {"clone_groups": [group]}}))
    output = failed("fallow", path, tmp_path, capsys)
    assert "src/alpha.ts:1-33" in output
    assert "src/beta.ts:4-36" in output
    assert output.count("\n") == 1
    assert "SECRET_BODY" not in output


def test_a_secret_found_in_history_names_its_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def result(sha: str) -> dict[str, object]:
        place = {"artifactLocation": {"uri": "a.py"}, "region": {"startLine": 2}}
        return {
            "ruleId": "github-pat",
            "locations": [{"physicalLocation": place}],
            "partialFingerprints": {"commitSha": sha},
        }

    sarif = {"runs": [{"results": [result("0123456789abcdef0123"), result("")]}]}
    path = tmp_path / "history.sarif"
    path.write_text(json.dumps(sarif))
    lines = failed("gitleaks", path, tmp_path, capsys).splitlines()
    assert lines == [
        "scan: github-pat a.py:2 in commit 0123456789ab",
        "scan: github-pat a.py:2",
    ]


def test_the_findings_of_all_kinds_stop_at_twenty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    exports = [{"path": f"s{n}.ts", "export_name": "x"} for n in range(30)]
    clones = [{"instances": [{"file": "d.ts", "start_line": 1, "end_line": 2}]}] * 30
    path = tmp_path / "fallow.json"
    path.write_text(
        json.dumps(
            {"check": {"unused_exports": exports}, "dupes": {"clone_groups": clones}}
        )
    )
    lines = failed("fallow", path, tmp_path, capsys).splitlines()
    assert len(lines) == 21
    assert lines[-1] == f"scan: 40 more findings in {path}"


@pytest.mark.parametrize("scanner", ["gitleaks", "react-doctor", "fallow"])
def test_a_missing_or_unreadable_report_prints_nothing_new(
    scanner: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert failed(scanner, tmp_path / "missing.json", tmp_path, capsys) == ""
    broken = tmp_path / "broken.json"
    broken.write_text("{")
    assert failed(scanner, broken, tmp_path, capsys) == ""


@pytest.mark.parametrize(
    "timeout,named,step",
    [
        (
            {"location": {"path": "tests/tables.py"}},
            "ran out of time on tests/tables.py.",
            "move them to a data module, then run the same check again",
        ),
        (
            {"error_type": "Fixpoint timeout"},
            "ran out of time and named no file;",
            "run the same check again",
        ),
    ],
)
def test_a_semgrep_timeout_names_each_file_and_the_step(
    timeout: dict[str, object], named: str, step: str, tmp_path: Path
) -> None:
    report = json.loads(REPORTS["semgrep"])
    report["time"]["fixpoint_timeouts"] = [timeout]
    path = tmp_path / "semgrep.json"
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="ran out of time") as error:
        reports.validate_semgrep(path)
    assert named in str(error.value)
    assert str(error.value).endswith(step)
    assert "None" not in str(error.value)
    assert ("data module" in str(error.value)) == ("tables" in named)
