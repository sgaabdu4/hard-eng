"""Scanner contracts reject findings, incomplete analysis and invalid reports."""

import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import reports

REPORTS = {
    "lighthouse-ci": '[{"url":"http://localhost/","auditId":"largest-contentful-paint","name":"maxNumericValue","level":"error","expected":2500,"actual":1200,"passed":true}]',
    "deptry": "[]",
    "osv": '{"results":[{"source":{"path":"uv.lock","type":"lockfile"},"packages":[{"package":{"name":"example","version":"1","ecosystem":"PyPI"}}]}]}',
    "semgrep": '{"results":[],"errors":[],"skipped_rules":[],"paths":{"scanned":["src/a.py"]},"time":{"rules":["rule"],"targets":[{"path":"src/a.py","num_bytes":20}]}}',
    "gitleaks": '{"version":"2.1.0","runs":[{"results":[],"tool":{"driver":{"name":"gitleaks","rules":[{"id":"rule"}]}}}]}',
    "trivy": '{"SchemaVersion":2,"ArtifactType":"filesystem","Results":[{"Class":"config","Target":"Dockerfile","Type":"dockerfile","MisconfSummary":{"Successes":1,"Failures":0}}]}',
    "fallow": '{"kind":"combined","check":{"total_issues":0,"summary":{"total_issues":0},"entry_points":{"total":1}},"dupes":{"clone_groups":[],"stats":{"clone_groups":0,"duplication_percentage":0,"total_files":1,"total_lines":5,"total_tokens":30}}}',
    "react-doctor": '{"schemaVersion":3,"mode":"full","ok":true,"reactDetected":true,"error":null,"diff":null,"diagnostics":[],"summary":{"errorCount":0,"warningCount":0,"affectedFileCount":0,"totalDiagnosticCount":0},"projects":[{"complete":true,"skippedChecks":[],"diagnostics":[],"analyzedFiles":["src/a.tsx"],"analyzedFileCount":1,"scannedFileCount":1,"project":{"sourceFileCount":1}}]}',
    "dart-decimate": '{"schema_version":"dart-decimate.report.v1","kind":"combined","tool":"dart-decimate","command":"check","verdict":"pass","findings":[],"clone_groups":[],"summary":{"findings":0,"dead_files":0,"unused_exports":0,"unused_types":0,"unused_enum_members":0,"unused_class_members":0,"unrendered_widgets":0,"missing_entry_points":0,"unresolved_dependencies":0,"code_duplications":0,"duplicated_lines":0,"duplication_percentage_basis_points":0,"duplication_threshold_basis_points":0,"duplication_threshold_exceeded":false,"files":1,"duplication_analyzed_lines":10}}',
    "jscpd": '{"duplicates":[],"statistics":{"formats":{"python":{"clones":0,"duplicatedLines":0,"duplicatedTokens":0,"newClones":0,"newDuplicatedLines":0,"percentage":0,"percentageTokens":0,"sources":1,"lines":10,"tokens":40}},"total":{"clones":0,"duplicatedLines":0,"duplicatedTokens":0,"newClones":0,"newDuplicatedLines":0,"percentage":0,"percentageTokens":0,"sources":1,"lines":10,"tokens":40}}}',
    "import-linter": "Analyzed 3 files, 2 dependencies.\nNo cycles KEPT\nContracts: 1 kept, 0 broken.\n",
}


@pytest.mark.parametrize(
    "replacement",
    [
        {"level": "warn"},
        {"passed": False},
        {"actual": None},
        {"auditId": "color-contrast"},
        {"url": ""},
    ],
)
def test_lighthouse_requires_passing_performance_budget(
    tmp_path: Path, replacement: dict[str, object]
) -> None:
    result = json.loads(REPORTS["lighthouse-ci"])
    result[0].update(replacement)
    path = tmp_path / "assertions.json"
    path.write_text(json.dumps(result))
    with pytest.raises(ValueError):
        reports.validate_lighthouse(path)


@pytest.mark.parametrize(
    "content",
    [
        "<testsuite/>",
        "<testsuite><testcase><skipped/></testcase></testsuite>",
        "<testsuite><testcase><failure/></testcase></testsuite>",
    ],
)
def test_performance_junit_rejects_missing_or_failed_tests(
    tmp_path: Path, content: str
) -> None:
    path = tmp_path / "performance.xml"
    path.write_text(content)
    with pytest.raises(ValueError):
        reports.validate_performance_junit(path)


@pytest.mark.parametrize("kind", list(REPORTS))
def test_valid_report_contract(kind: str, tmp_path: Path) -> None:
    path = tmp_path / "report"
    path.write_text(REPORTS[kind])
    reports.SCANNERS[kind](path)


@pytest.mark.parametrize("kind", list(REPORTS))
@pytest.mark.parametrize("content", ["", "null", "{}", "not json"])
def test_incomplete_report_fails(kind: str, content: str, tmp_path: Path) -> None:
    path = tmp_path / "report"
    path.write_text(content)
    with pytest.raises((ValueError, TypeError)):
        reports.SCANNERS[kind](path)


@pytest.mark.parametrize(
    "kind,old,new",
    [
        ("osv", '"version":"1"', '"version":""'),
        ("osv", '"packages":[', '"packages":[],"ignored":['),
        ("semgrep", '"results":[]', '"results":[{"finding":true}]'),
        ("semgrep", '"errors":[]', '"errors":[{"parse":true}]'),
        ("semgrep", '"skipped_rules":[]', '"skipped_rules":["rule"]'),
        ("semgrep", '"num_bytes":20', '"num_bytes":0'),
        ("semgrep", '"rules":["rule"]', '"rules":[]'),
        (
            "semgrep",
            '"rules":["rule"]',
            '"rules":["rule"],"fixpoint_timeouts":[{"error_type":"Fixpoint timeout"}]',
        ),
        ("gitleaks", '"results":[]', '"results":[{"secret":"redacted"}]'),
        ("gitleaks", '"rules":[{"id":"rule"}]', '"rules":[]'),
        ("trivy", '"Failures":0', '"Failures":1'),
        ("trivy", '"Successes":1', '"Successes":0'),
        ("fallow", '"total_issues":0', '"total_issues":1'),
        ("fallow", '"clone_groups":[]', '"clone_groups":[{}]'),
        ("react-doctor", '"complete":true', '"complete":false'),
        ("react-doctor", '"analyzedFileCount":1', '"analyzedFileCount":2'),
        ("react-doctor", '"skippedChecks":[]', '"skippedChecks":["lint"]'),
        ("dart-decimate", '"findings":[]', '"findings":[{}]'),
        ("dart-decimate", '"dead_files":0', '"dead_files":1'),
        ("dart-decimate", '"files":1', '"files":0'),
        ("jscpd", '"duplicates":[]', '"duplicates":[{}]'),
        ("jscpd", '"sources":1', '"sources":0'),
        ("import-linter", "No cycles KEPT", "No cycles BROKEN"),
        ("import-linter", "Analyzed 3", "Analyzed 0"),
        ("import-linter", "1 kept, 0 broken", "0 kept, 0 broken"),
    ],
)
def test_findings_and_empty_analysis_fail(
    kind: str, old: str, new: str, tmp_path: Path
) -> None:
    path = tmp_path / "report"
    path.write_text(REPORTS[kind].replace(old, new))
    with pytest.raises(ValueError):
        reports.SCANNERS[kind](path)


@pytest.mark.parametrize("source_type", ["artifact", "lockfile"])
def test_image_report_requires_valid_layer_origin(
    tmp_path: Path, source_type: str
) -> None:
    path = tmp_path / "report"
    report = json.loads(REPORTS["osv"])
    report["results"][0]["source"]["type"] = source_type
    report["results"][0]["packages"][0]["package"]["image_origin_details"] = {
        "index": 0
    }
    report["image_metadata"] = {
        "layer_metadata": [{"is_empty": False, "diff_id": "sha256:" + "a" * 64}]
    }
    path.write_text(json.dumps(report))
    reports.validate_osv_image(path)
    report["results"][0]["packages"][0]["package"]["image_origin_details"]["index"] = 2
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="layer"):
        reports.validate_osv_image(path)


def test_native_logs_must_show_complete_scan() -> None:
    reports.validate_deptry_log(io.StringIO("Scanning 2 files...\n"))
    reports.validate_trivy_log(
        io.StringIO("time\tINFO\t[misconfig] Misconfiguration scanning is enabled\n")
    )
    for text in (
        "",
        "Scanning 0 files...",
        "Scanning 2 files...\nWarning: Skipping processing of bad.py",
    ):
        with pytest.raises(ValueError):
            reports.validate_deptry_log(io.StringIO(text))
    with pytest.raises(ValueError):
        reports.validate_trivy_log(io.StringIO("time\tERROR\tfailed"))
    with pytest.raises(ValueError):
        reports.validate_trivy_log(io.StringIO(""))


def test_nonempty_completed_tests(tmp_path: Path) -> None:
    path = tmp_path / "tests.xml"
    path.write_text("<testsuite><testcase/><testcase><skipped/></testcase></testsuite>")
    assert reports.completed_tests(path, "python-tests") == 1
    path.write_text("<testsuite><testcase><failure/></testcase></testsuite>")
    with pytest.raises(ValueError):
        reports.completed_tests(path, "python-tests")
    path.write_text("<testsuite><testcase><skipped/></testcase></testsuite>")
    assert reports.completed_tests(path, "python-tests") == 0
    path.write_text(
        '[{"type":"testDone","hidden":false,"skipped":false,"result":"success"}]\n{"type":"done","success":true}\n'
    )
    assert reports.completed_tests(path, "dart-tests") == 1
    path.write_text('{"type":"done","success":false}\n')
    with pytest.raises(ValueError):
        reports.completed_tests(path, "dart-tests")


def test_coverage_requires_unexecuted_files_and_merges_lcov(tmp_path: Path) -> None:
    path = tmp_path / "lcov.info"
    path.write_text(
        "SF:used.js\nDA:1,1\nDA:2,0\nend_of_record\nSF:used.js\nDA:1,1\nDA:2,1\nend_of_record\n"
    )
    assert reports.line_coverage(
        path, "lcov-tests", tmp_path, {tmp_path / "used.js"}
    ) == (2, 2)
    with pytest.raises(ValueError, match="omits"):
        reports.line_coverage(
            path, "lcov-tests", tmp_path, {tmp_path / "used.js", tmp_path / "unused.js"}
        )
    path.write_text("SF:used.js\nDA:1,1\n")
    with pytest.raises(ValueError, match="Incomplete"):
        reports.lcov_coverage(path, tmp_path)


def test_dart_coverage_allows_export_barrels_but_requires_executable_files(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lcov.info"
    path.write_text("SF:total.dart\nDA:1,1\nend_of_record\n")
    barrel = tmp_path / "api.dart"
    barrel.write_text("export 'total.dart';\n")
    expected = {tmp_path / "total.dart", barrel}
    assert reports.line_coverage(path, "dart-tests", tmp_path, expected) == (1, 1)
    barrel.write_text("export 'total.dart';\nint unused() => 1;\n")
    with pytest.raises(ValueError, match="omits production files: api.dart"):
        reports.line_coverage(path, "dart-tests", tmp_path, expected)


def test_branch_coverage_is_reported_separately_from_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "coverage.json"
    path.write_text(
        json.dumps(
            {
                "files": {
                    "app.py": {
                        "summary": {
                            "covered_lines": 7,
                            "num_statements": 10,
                            "covered_branches": 1,
                            "num_branches": 4,
                        }
                    }
                }
            }
        )
    )
    assert reports.line_coverage(
        path, "python-tests", tmp_path, {tmp_path / "app.py"}
    ) == (7, 10)
    assert "Branch coverage: 1/4 (25.00%; informational)" in capsys.readouterr().out


def test_junit_rejects_entities(tmp_path: Path) -> None:
    path = tmp_path / "tests.xml"
    secret = tmp_path / "private.txt"
    secret.write_text("must-not-be-expanded")
    path.write_text(
        f'<!DOCTYPE testsuite [<!ENTITY external SYSTEM "{secret.as_uri()}">]><testsuite>&external;</testsuite>'
    )
    with pytest.raises(ET.ParseError, match="undefined entity"):
        reports.completed_tests(path, "python-tests")
    entities = '<!ENTITY a "1234567890">'
    for index in range(7):
        entities += (
            f'<!ENTITY {chr(98 + index)} "' + ("&" + chr(97 + index) + ";") * 10 + '">'
        )
    path.write_text(f"<!DOCTYPE testsuite [{entities}]><testsuite>&h;</testsuite>")
    with pytest.raises(ET.ParseError, match="amplification"):
        reports.completed_tests(path, "python-tests")
