"""Scanner contracts reject findings, incomplete analysis and invalid reports."""

import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType

import pytest
import reports
from gate_config import (
    Gate,
    Group,
    JsonObject,
    validate_gate,
    validate_package_services,
)
from test_tool_execution import execute_provisioned_scanner


@pytest.mark.parametrize(
    "prerequisite", ["before", "missing", "after", "parallel", "different"]
)
def test_delegated_fallow_reuses_only_its_completed_coverage_owner(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prerequisite: str,
) -> None:
    manifest = {
        "scripts": {
            "test:coverage": "node --test",
            "check:fallow": "pnpm run test:coverage && pnpm run scan",
            "scan": "fallow audit --gate all --max-crap 30 --format json --output-file coverage/fallow.json",
        }
    }
    (tmp_path / "package.json").write_text(json.dumps(manifest))
    coverage: Gate = {
        "name": "coverage",
        "role": "tests",
        "command": ["pnpm", "run", "test:coverage"],
    }
    scan: Gate = {
        "name": "scan",
        "role": "dead-code-duplicates",
        "command": ["pnpm", "run", "scan"],
        "report": {"type": "fallow", "path": "coverage/fallow.json"},
    }
    group: Group = {
        "path": ".",
        "language": "javascript",
        "checks": [coverage, scan],
    }
    if prerequisite == "missing":
        group["checks"] = [scan]
    elif prerequisite == "after":
        group["checks"].reverse()
    elif prerequisite == "parallel":
        coverage["parallel"] = True
    elif prerequisite == "different":
        coverage["command"] = ["node", "--test"]
    inherited = {"lockfiles", "vulnerabilities", "security"}
    if prerequisite != "before":
        with pytest.raises(ValueError, match="Wire check:fallow"):
            validate_package_services(tmp_path, group, {}, {}, inherited)
        return
    validate_package_services(tmp_path, group, {}, {}, inherited)
    validate_gate(scan, tmp_path, set())
    assert execute_provisioned_scanner(
        runner,
        tmp_path,
        monkeypatch,
        {"path": ".", "checks": [scan]},
        "fallow",
        "npm:fallow@latest",
        stale_local=True,
        expected_use_npm=False,
    ) == [
        "managed",
        "audit",
        "--gate",
        "all",
        "--max-crap",
        "30",
        "--format",
        "json",
        "--output-file",
        "coverage/fallow.json",
    ]


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        "extra",
        "missing-owner-edge",
        "missing-consumer-edge",
        "late-owner",
        "parallel-owner",
        "wrong-directory",
    ],
)
def test_delegated_fallow_reuses_only_selected_declared_coverage_owners(
    tmp_path: Path, invalid: str | None
) -> None:
    owner: Group = {
        "path": "packages/website",
        "language": "javascript",
        "depends_on": ["packages/api"],
        "checks": [
            {
                "name": "coverage",
                "role": "tests",
                "command": ["pnpm", "run", "test:coverage"],
            }
        ],
    }
    scan: Gate = {
        "name": "scan",
        "role": "dead-code-duplicates",
        "command": ["pnpm", "run", "scan"],
        "report": {"type": "fallow", "path": "coverage/fallow.json"},
    }
    consumer: Group = {
        "path": "packages/api",
        "language": "javascript",
        "depends_on": ["packages/website"],
        "checks": [
            {
                "name": "coverage",
                "role": "tests",
                "command": ["pnpm", "run", "test:coverage"],
            },
            scan,
        ],
    }
    scripts = "pnpm run test:coverage && pnpm --dir ../website run test:coverage && pnpm run scan"
    if invalid == "extra":
        scripts = "pnpm run test:coverage && echo stale && pnpm --dir ../website run test:coverage && pnpm run scan"
    elif invalid == "wrong-directory":
        scripts = "pnpm run test:coverage && pnpm --dir packages/website run test:coverage && pnpm run scan"
    elif invalid == "missing-owner-edge":
        owner["depends_on"] = []
    elif invalid == "missing-consumer-edge":
        consumer["depends_on"] = []
    elif invalid == "parallel-owner":
        owner["checks"][0]["parallel"] = True
    (tmp_path / "packages/api").mkdir(parents=True)
    (tmp_path / "packages/website").mkdir(parents=True)
    (tmp_path / "packages/api/package.json").write_text(
        json.dumps({"scripts": {"check:fallow": scripts}})
    )
    (tmp_path / "packages/website/package.json").write_text(json.dumps({"scripts": {}}))
    by_directory: dict[tuple[Path, str], Group] = {
        ((tmp_path / "packages/api").resolve(), "javascript"): consumer,
        ((tmp_path / "packages/website").resolve(), "javascript"): owner,
    }
    inherited = {"lockfiles", "vulnerabilities", "security"}
    package_groups = [consumer, owner] if invalid == "late-owner" else [owner, consumer]
    if invalid is not None:
        with pytest.raises(ValueError, match="Wire check:fallow"):
            validate_package_services(
                tmp_path, consumer, by_directory, {}, inherited, package_groups
            )
        return
    validate_package_services(
        tmp_path, consumer, by_directory, {}, inherited, package_groups
    )


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


@pytest.fixture
def empty_pnpm(tmp_path: Path) -> Path:
    (tmp_path / "package.json").write_text('{"private":true}')
    (tmp_path / "pnpm-lock.yaml").write_text(
        "lockfileVersion: '9.0'\nimporters:\n  .: {}\n"
    )
    return tmp_path


def test_fallow_optional_unconfigured_detectors_do_not_require_invented_policy(
    tmp_path: Path,
) -> None:
    data = json.loads(REPORTS["fallow"])
    data["workspace_diagnostics"] = [
        {"path": ".", "kind": "boundaries-not-configured"},
        {"path": ".", "kind": "rule-packs-not-configured"},
    ]
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    reports.validate_fallow(path)
    data["check"]["total_issues"] = 1
    data["check"]["policy_violations"] = [{"rule": "required-policy"}]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        reports.validate_fallow(path)


@pytest.mark.parametrize(
    "diagnostics", [[{"kind": "parse-error"}], ["invalid"], None, {}, ""]
)
def test_fallow_unknown_or_malformed_diagnostics_still_fail(
    tmp_path: Path, diagnostics: object
) -> None:
    data = json.loads(REPORTS["fallow"])
    data["workspace_diagnostics"] = diagnostics
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        reports.validate_fallow(path)


@pytest.mark.parametrize("threshold", [15, 30.0, 45])
def test_fallow_audit_requires_active_crap_enforcement(
    tmp_path: Path, threshold: float
) -> None:
    combined = json.loads(REPORTS["fallow"])
    summary: JsonObject = {
        "max_crap_threshold": threshold,
        "files_analyzed": 1,
        "functions_analyzed": 1,
        "functions_above_threshold": 0,
        "severity_critical_count": 0,
        "severity_high_count": 0,
        "severity_moderate_count": 0,
    }
    audit: JsonObject = {
        "kind": "audit",
        "command": "audit",
        "verdict": "pass",
        "dead_code": combined["check"],
        "duplication": combined["dupes"],
        "complexity": {"findings": [], "summary": summary},
    }
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(audit))
    reports.validate_fallow(path)
    for invalid in (0, -1, None, True):
        summary["max_crap_threshold"] = invalid
        path.write_text(json.dumps(audit))
        with pytest.raises(ValueError, match="CRAP enforcement"):
            reports.validate_fallow(path)
    del summary["max_crap_threshold"]
    path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="incomplete"):
        reports.validate_fallow(path)
    summary["max_crap_threshold"] = threshold
    summary["functions_above_threshold"] = 1
    path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="complexity findings"):
        reports.validate_fallow(path)


def test_osv_accepts_native_empty_only_with_dependency_free_pnpm(
    empty_pnpm: Path,
) -> None:
    path = empty_pnpm / "report.json"
    path.write_text('{"results":null}')
    with pytest.raises(ValueError):
        reports.validate_osv(path)
    reports.validate_osv(path, empty_pnpm=empty_pnpm)
    subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            (
                "import importlib.util,sys; from pathlib import Path; "
                "assert importlib.util.find_spec('yaml') is None; "
                f"sys.path.insert(0, {str(Path(reports.__file__).parent)!r}); "
                "import reports; "
                f"reports.validate_osv(Path({str(path)!r}), empty_pnpm=Path({str(empty_pnpm)!r}))"
            ),
        ],
        check=True,
    )


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("package.json", '{"dependencies":{"missing":"1"}}'),
        ("package.json", '{"devDependencies":{"test":"1"}}'),
        ("package.json", '{"peerDependencies":{"peer":"1"}}'),
        ("package.json", '{"optionalDependencies":{"optional":"1"}}'),
        ("package.json", "[]"),
        (
            "pnpm-lock.yaml",
            "lockfileVersion: '9.0'\npackages: {hidden: {}}\nimporters: {.: {}}",
        ),
        ("pnpm-lock.yaml", "lockfileVersion: '9.0'\nimporters: {.: {}, child: {}}"),
        (
            "pnpm-lock.yaml",
            "lockfileVersion: '9.0'\nimporters: {.: {dependencies: {hidden: '1'}}}",
        ),
        ("pnpm-lock.yaml", "broken: ["),
        ("pnpm-lock.yaml", "[]"),
        ("pnpm-lock.yaml", None),
        ("pnpm-workspace.yaml", "packages: ['packages/*']"),
        ("report.json", '{"results":null,"errors":["scan failed"]}'),
        ("report.json", "{}"),
    ],
)
def test_osv_empty_cannot_hide_dependency_or_scan_gaps(
    empty_pnpm: Path, name: str, content: str | None
) -> None:
    path = empty_pnpm / "report.json"
    path.write_text('{"results":null}')
    if content is None:
        (empty_pnpm / name).unlink()
    else:
        (empty_pnpm / name).write_text(content)
    with pytest.raises(ValueError):
        reports.validate_osv(path, empty_pnpm=empty_pnpm)


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
        ("trivy", '"ArtifactType":"filesystem"', '"ArtifactType":"container_image"'),
        ("fallow", '"total_issues":0', '"total_issues":1'),
        ("fallow", '"clone_groups":[]', '"clone_groups":[{}]'),
        ("react-doctor", '"complete":true', '"complete":false'),
        ("react-doctor", '"analyzedFileCount":1', '"analyzedFileCount":2'),
        ("react-doctor", '"skippedChecks":[]', '"skippedChecks":["lint"]'),
        ("dart-decimate", '"tool":"dart-decimate"', '"tool":"other-tool 1.0.0"'),
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


@pytest.mark.parametrize(
    "tool", ["dart-decimate", "dart-decimate 0.0.44", "dart-decimate 0.1.0-beta.1"]
)
def test_dart_decimate_accepts_versioned_tool_name(tmp_path: Path, tool: str) -> None:
    path = tmp_path / "report.json"
    content = REPORTS["dart-decimate"].replace('"dart-decimate"', f'"{tool}"')
    path.write_text(content)
    reports.validate_dart_decimate(path)


def test_trivy_repository_config_retains_failure_checks(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    content = REPORTS["trivy"].replace('"filesystem"', '"repository"')
    path.write_text(content)
    reports.validate_trivy(path)
    path.write_text(content.replace('"Failures":0', '"Failures":1'))
    with pytest.raises(ValueError, match="failed checks"):
        reports.validate_trivy(path)


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


def test_dart_test_failure_keeps_one_bounded_failure_context(tmp_path: Path) -> None:
    path = tmp_path / "tests.jsonl"
    path.write_text(
        '{"type":"testStart","test":{"id":7,"name":"rejects an invalid payload"}}\n'
        '{"type":"error","testID":7,"error":"Expected a valid payload\\nActual: malformed"}\n'
        '{"type":"testDone","testID":7,"result":"failure"}\n'
        '{"type":"done","success":false}\n'
    )
    assert reports.dart_test_failure(
        subprocess.CompletedProcess([], 1), True, "dart-tests", path
    ) == (
        "Dart test failure: rejects an invalid payload: Expected a valid payload Actual: malformed"
    )
    path.write_text('{"type":"done","success":true}\n')
    assert (
        reports.dart_test_failure(
            subprocess.CompletedProcess([], 0), True, "dart-tests", path
        )
        is None
    )


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


@pytest.mark.parametrize(
    "source",
    [
        "import type { Foo } from './foo';\nexport type State = ReturnType<Foo>;",
        "/* contract */ export interface State { id: string; }\n// no runtime",
        "export type { Foo } from './foo';\nexport {};",
    ],
)
def test_lcov_allows_erased_typescript_without_inventing_coverage(
    tmp_path: Path, source: str
) -> None:
    path = tmp_path / "lcov.info"
    path.write_text("SF:used.js\nDA:1,1\nDA:2,0\nend_of_record\n")
    types = tmp_path / "types.ts"
    types.write_text(source)
    assert reports.line_coverage(
        path, "lcov-tests", tmp_path, {tmp_path / "used.js", types}
    ) == (1, 2)
    with pytest.raises(ValueError, match="no executable lines"):
        reports.line_coverage(path, "lcov-tests", tmp_path, {types})


@pytest.mark.parametrize(
    "source",
    [
        "export type Id = string; export const value = 1;",
        "import './side-effect'; export interface Id {}",
        "import { Id } from './side-effect'; export type Value = Id;",
        "export enum Value { One }",
        "export const value = <div />;",
        "export type Broken = ;",
        "console.log('/* not a comment */');",
        "/* before */ console.log('runtime'); /* after */",
        "// comment\u2028console.log('runtime');",
        "// comment\u2029console.log('runtime');",
        "throw Error('inspected source must never execute');",
    ],
)
def test_lcov_keeps_unproven_typescript_in_required_coverage(
    tmp_path: Path, source: str
) -> None:
    path = tmp_path / "lcov.info"
    path.write_text("SF:used.js\nDA:1,1\nend_of_record\n")
    omitted = tmp_path / "omitted.ts"
    omitted.write_text(source)
    with pytest.raises(ValueError, match="omits production files: omitted.ts"):
        reports.line_coverage(path, "lcov-tests", tmp_path, {omitted})


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


@pytest.mark.parametrize(
    ("command", "message"),
    [
        ("dart-decimate check . --boundary-violations", "add --strict"),
        ("dart-decimate check lib --strict --tolerance 1", "tolerate"),
        ("dart-decimate check . --strict --regression-baseline=x", "tolerate"),
        ("pnpm dlx dart-decimate@latest check . --fail-on-regression", "tolerate"),
        ("react-doctor --scope full --blocking warning", "no-respect-inline-disables"),
        ("react-doctor --blocking error --no-respect-inline-disables", "--blocking"),
        ("react-doctor --no-respect-inline-disables", "--blocking warning"),
        ("fallow --fail-on-issues --dead-code-baseline x", "tolerate"),
        ("fallow --only dead-code,dupes --format json", "add --fail-on-issues"),
        ("fallow audit --gate all --save-baseline", "tolerate"),
        ("fallow audit --gate new", "add --gate all"),
    ],
)
def test_gate_rejects_tolerated_or_suppressed_findings(
    tmp_path: Path, command: str, message: str
) -> None:
    gate: Gate = {"name": "scan", "command": command.split()}
    if command.startswith("fallow audit"):
        gate["report"] = {"type": "fallow", "path": "audit.json"}
    with pytest.raises(ValueError, match=message):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize(
    "command",
    [
        "dart-decimate check . --boundary-violations --strict",
        "dart-decimate check . --threshold 0 --strict --format json",
        "react-doctor --blocking=warning --no-respect-inline-disables --json",
        "fallow --only dead-code,dupes --fail-on-issues",
    ],
)
def test_gate_accepts_strict_scanner_commands(tmp_path: Path, command: str) -> None:
    validate_gate({"name": "scan", "command": command.split()}, tmp_path, set())
