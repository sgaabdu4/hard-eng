"""Line and branch coverage totals come from the production files the report lists."""

import json
from pathlib import Path

import pytest
import reports


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
    with pytest.raises(
        ValueError,
        match=r"omits production files: api.dart\. .*linguist-generated=true` in \.gitattributes",
    ):
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


def test_a_missing_python_coverage_report_names_the_cov_step(tmp_path: Path) -> None:
    report = tmp_path / "coverage.json"
    with pytest.raises(ValueError, match="--cov="):
        reports.line_coverage(report, "python-tests", tmp_path, {tmp_path / "a.py"})
