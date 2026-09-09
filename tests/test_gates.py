"""Exercise fail-closed execution and report integrity at the gate boundary."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from hard_eng import cli, common, config, reports, runner
from hard_eng.common import GateError, Json
from hard_eng.config import Check, Config, Package


def test_flutter_process_frame_does_not_hide_empty_failed_or_incomplete_tests(tmp_path: Path) -> None:
    report = tmp_path / "tests.jsonl"
    events: list[object] = [
        {"type": "start"},
        [{"event": "test.startedProcess", "params": {}}],
        {"type": "testDone", "hidden": True, "skipped": False, "result": "success"},
        {"type": "testDone", "hidden": False, "skipped": False, "result": "success"},
        {"type": "done", "success": True},
    ]
    report.write_text("\n".join(json.dumps(event) for event in events))
    assert reports.dart_tests(report, 1) == 1
    events.pop(3)
    report.write_text("\n".join(json.dumps(event) for event in events))
    with pytest.raises(GateError, match="empty/incomplete"):
        reports.dart_tests(report, 1)
    events.append({"type": "error", "error": "test failed"})
    report.write_text("\n".join(json.dumps(event) for event in events))
    with pytest.raises(GateError):
        reports.dart_tests(report, 1)


def test_fallow_success_exit_cannot_hide_reported_duplicates(repo: Path) -> None:
    result: Json = {
        "kind": "combined",
        "check": {"total_issues": 0, "entry_points": {"total": 1}},
        "dupes": {"stats": {"duplicated_lines": 46}},
    }
    report: Json = {"type": "fallow", "path": "coverage/fallow.json", "stdout": True}
    gate = command(repo, f"print({json.dumps(json.dumps(result))})", report=report)
    with pytest.raises(GateError, match="duplicate-code findings"):
        runner.execute(gate, None, None)
    result["dupes"] = {"stats": {"duplicated_lines": 0}}
    gate = command(repo, f"print({json.dumps(json.dumps(result))})", report=report)
    assert runner.execute(gate, None, None) == "report complete"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("coverage/\n*.xml\n")
    (tmp_path / "app.py").write_text("def double(value):\n    return value * 2\n")
    (tmp_path / "PRODUCT.md").write_text("# Example\nDoubles an input value.\n")
    (tmp_path / "DESIGN.md").write_text("# Example design\nA Python API with no visual interface.\n")
    return tmp_path


def package(root: Path, checks: tuple[Check, ...] = ()) -> Package:
    return Package("app", root, "python", ("app.py",), (), checks)


def command(root: Path, code: str, *, report: Json | None = None) -> Check:
    return Check(
        "example",
        "tests" if report else "build",
        "app",
        root,
        (sys.executable, "-c", code),
        None,
        3,
        report or {},
    )


def native_reports(root: Path, *, covered: int = 7, total: int = 10) -> Json:
    (root / "coverage").mkdir(exist_ok=True)
    (root / "tests.xml").write_text('<testsuite><testcase name="observable_result"/></testsuite>')
    common.write_json(
        root / "coverage/result.json",
        {
            "files": {
                "app.py": {
                    "summary": {
                        "covered_lines": covered,
                        "num_statements": total,
                        "num_branches": 2,
                        "covered_branches": 1,
                    }
                }
            },
        },
    )
    return {"type": "python-tests", "tests": "tests.xml", "coverage": "coverage/result.json"}


def test_missing_cli_configuration_fails_cleanly(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--repo", str(repo), "check"]) == 1
    assert "hard-eng.gates.json" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["PRODUCT.md", "DESIGN.md"])
@pytest.mark.parametrize("empty", [False, True])
def test_missing_or_empty_document_blocks_checks(repo: Path, name: str, empty: bool) -> None:
    document = repo / name
    document.write_text(" \n") if empty else document.unlink()
    gate = command(repo, "from pathlib import Path; Path('.git/ran').touch()")
    project = Config(repo, (package(repo, (gate,)),), (), {})
    with pytest.raises(GateError, match=name):
        runner.check_all(project)
    assert not (repo / ".git/ran").exists()
    document.write_text("# Example\nDocumented from the repository.\n")
    assert runner.check_all(project)["passed"] is True
    assert (repo / ".git/ran").exists()


def test_launcher_help_runs_from_another_directory(tmp_path: Path) -> None:
    launcher = Path(__file__).resolve().parents[1] / "bin/hard-eng"
    result = subprocess.run(
        [sys.executable, str(launcher), "--help"], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Run repository-owned Hard Eng gates" in result.stdout


@pytest.mark.parametrize("name", ["PRODUCT.md", "DESIGN.md"])
def test_unfilled_document_template_does_not_pass(repo: Path, name: str) -> None:
    template = Path(__file__).resolve().parents[1] / "skills/he/templates" / name
    (repo / name).write_text(template.read_text())
    with pytest.raises(GateError, match="unfilled template prompts"):
        runner.required_documents(repo)


def test_command_success_and_failure_are_observable(repo: Path) -> None:
    success = command(repo, "from pathlib import Path; Path('out.txt').write_text('42')")
    assert runner.execute(success, None, None) == "command passed"
    assert (repo / "out.txt").read_text() == "42"
    with pytest.raises(GateError, match="exit 7"):
        runner.execute(command(repo, "raise SystemExit(7)"), None, None)


def test_locked_dependencies_are_available_before_package_checks(repo: Path) -> None:
    consumer = command(repo, "from prepared_dependency import answer; assert answer == 42")
    with pytest.raises(GateError, match="exit 1"):
        runner.execute(consumer, None, None)
    preparation = replace(
        command(
            repo, "from pathlib import Path; Path('prepared_dependency.py').write_text('answer = 42\\n')"
        ),
        name="locked-dependencies",
        role="lockfiles",
    )
    project = Config(repo, (package(repo, (consumer,)),), (preparation,), {})
    assert runner.check_all(project)["passed"] is True


def test_missing_executable_and_timeout_fail(repo: Path) -> None:
    with pytest.raises(GateError, match="Cannot start"):
        common.run(["hard-eng-nonexistent-executable"], repo)
    with pytest.raises(GateError, match="timed out"):
        common.run([sys.executable, "-c", "import time; time.sleep(10)"], repo, 0.05)


def test_full_production_line_coverage_passes_at_threshold(repo: Path) -> None:
    report = native_reports(repo)
    gate = command(repo, "", report=report)
    assert reports.validate(gate, package(repo)) == "1 tests; lines 70.00%; branches 50.00%"


@pytest.mark.parametrize("covered,total", [(6, 10), (0, 0), (11, 10)])
def test_bad_coverage_counts_fail(repo: Path, covered: int, total: int) -> None:
    gate = command(repo, "", report=native_reports(repo, covered=covered, total=total))
    with pytest.raises(GateError):
        reports.validate(gate, package(repo))


def test_unexecuted_production_file_cannot_disappear(repo: Path) -> None:
    report = native_reports(repo)
    (repo / "other.py").write_text("def unused():\n    return 9\n")
    scope = Package("app", repo, "python", ("app.py", "other.py"), (), ())
    with pytest.raises(GateError, match="1 production files missing"):
        reports.validate(command(repo, "", report=report), scope)


def test_test_code_cannot_inflate_production_coverage(repo: Path) -> None:
    report = native_reports(repo, covered=6)
    data = common.read_json(repo / "coverage/result.json")
    files = common.object_value(data["files"], "files")
    files["test_app.py"] = {"summary": {"covered_lines": 100, "num_statements": 100}}
    common.write_json(repo / "coverage/result.json", data)
    with pytest.raises(GateError, match="60.00% is below 70%"):
        reports.validate(command(repo, "", report=report), package(repo))


@pytest.mark.parametrize(
    "body",
    [
        "<testsuite/>",
        "<testsuite><testcase><skipped/></testcase></testsuite>",
        "<testsuite><testcase><failure/></testcase></testsuite>",
        "broken",
    ],
)
def test_empty_skipped_failed_or_broken_tests_fail(repo: Path, body: str) -> None:
    report = native_reports(repo)
    (repo / "tests.xml").write_text(body)
    with pytest.raises(GateError):
        reports.validate(command(repo, "", report=report), package(repo))


def test_old_reports_cannot_make_an_unrun_test_pass(repo: Path) -> None:
    gate = command(repo, "pass", report=native_reports(repo))
    with pytest.raises(GateError, match="Missing or invalid JUnit"):
        runner.execute(gate, package(repo), None)
    assert not (repo / "coverage/result.json").exists()


def test_report_symlink_cannot_delete_another_file(repo: Path) -> None:
    (repo / "important.xml").write_text("preserve")
    (repo / "tests.xml").symlink_to(repo / "important.xml")
    gate = command(
        repo,
        "pass",
        report={"type": "python-tests", "tests": "tests.xml", "coverage": "coverage/result.json"},
    )
    with pytest.raises(GateError, match="symlink"):
        runner.execute(gate, package(repo), None)
    assert (repo / "important.xml").read_text() == "preserve"


def test_failing_gate_cannot_leave_successful_result(repo: Path) -> None:
    gate = command(repo, "raise SystemExit(1)")
    with pytest.raises(GateError, match="required checks failed"):
        runner.check_all(Config(repo, (package(repo, (gate,)),), (), {}))


@pytest.mark.parametrize("text", ["test.only('something', () => {});", "fdescribe('suite', () => {});"])
def test_focused_javascript_tests_fail(repo: Path, text: str) -> None:
    (repo / "app.test.ts").write_text(text)
    with pytest.raises(GateError, match="focused test"):
        runner.source_checks(Config(repo, (package(repo),), (), {}))


def test_file_limit_requires_specific_evidence(repo: Path) -> None:
    (repo / "app.py").write_text("value = 1\n" * 701)
    project = Config(repo, (package(repo),), (), {})
    with pytest.raises(GateError, match="exceeds 700"):
        runner.source_checks(project)


def test_affected_scope_includes_transitive_dependents(repo: Path) -> None:
    packages = tuple(
        Package(name, repo / name, "python", ("src",), deps, ())
        for name, deps in [("core", ()), ("api", ("core",)), ("web", ("api",)), ("other", ())]
    )
    project = Config(repo, packages, (), {})
    assert [p.name for p in config.affected(project, [repo / "core/src/a.py"])] == ["core", "api", "web"]
    assert config.affected(project, [repo / "pyproject.toml"]) == packages


def test_config_cannot_escape_repository(repo: Path) -> None:
    with pytest.raises(GateError, match="escapes"):
        common.relative_path(repo, "../outside")


def test_incomplete_scans_fail() -> None:
    with pytest.raises(GateError, match="no files"):
        reports.security({"errors": [], "results": [], "paths": {"scanned": []}})
    with pytest.raises(GateError, match="no packages"):
        reports.vulnerabilities({"results": []})
    with pytest.raises(GateError, match="scan errors"):
        reports.security({"errors": [{"message": "parse failed"}], "results": []})
    with pytest.raises(GateError, match="vulnerabilities"):
        reports.vulnerabilities({"results": [{"packages": [{"vulnerabilities": [{"id": "CVE-example"}]}]}]})


def test_edit_warning_does_not_exclude_handwritten_production(repo: Path) -> None:
    source = repo / "app.py"
    source.write_text("# DO NOT EDIT without checking the contract\nvalue = 1\n")
    assert reports.production_source(source)
    source.write_text("# Code generated by the project's generator. DO NOT EDIT.\nvalue = 1\n")
    assert not reports.production_source(source)


def test_deployment_report_requires_actual_checks_and_no_findings() -> None:
    result: Json = {"Class": "config", "MisconfSummary": {"Successes": 27, "Failures": 0}}
    reports.deployment({"Results": [result]})
    with pytest.raises(GateError, match="no deployment"):
        reports.deployment({"Results": []})
    result["MisconfSummary"] = {"Successes": 26, "Failures": 1}
    with pytest.raises(GateError, match="findings"):
        reports.deployment({"Results": [result]})
    result["MisconfSummary"] = {"Successes": 0, "Failures": 0}
    with pytest.raises(GateError, match="did not complete"):
        reports.deployment({"Results": [result]})
