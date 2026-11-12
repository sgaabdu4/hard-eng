"""Line and branch coverage totals come from the production files the report lists."""

import json
from pathlib import Path
from types import ModuleType

import pytest
import reports
from test_setup import repository


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
    with pytest.raises(ValueError, match="replace the old name") as refusal:
        reports.line_coverage(report, "python-tests", tmp_path, {tmp_path / "a.py"})
    text = str(refusal.value)
    assert "`sources` list of the package" in text
    assert "each --cov= value of its tests command in hard-eng.gates.json" in text
    assert "rerun setup" not in text


@pytest.mark.parametrize(
    ("name", "content"),
    [
        (".coveragerc", "[run]\nomit = app/_compat.py,\n"),
        (".coveragerc.toml", '[run]\nomit = ["app/_compat.py"]\n'),
        ("pyproject.toml", '[tool.coverage.run]\nomit = ["app/_compat.py"]\n'),
        ("setup.cfg", "[coverage:run]\nomit =\n    app/_compat.py\n"),
    ],
)
def test_a_python_file_that_an_omit_setting_hides_names_that_setting(
    tmp_path: Path, name: str, content: str
) -> None:
    """Tests cannot cover a file that the project's own coverage settings leave out."""
    report = tmp_path / "coverage.json"
    summary = {"covered_lines": 1, "num_statements": 1}
    report.write_text(json.dumps({"files": {"app/main.py": {"summary": summary}}}))
    expected = {tmp_path / "app/main.py", tmp_path / "app/_compat.py"}
    with pytest.raises(ValueError, match="omits production files") as plain:
        reports.line_coverage(report, "python-tests", tmp_path, expected)
    assert "omit" not in str(plain.value).split("omits production files")[1]
    (tmp_path / name).write_text(content)
    with pytest.raises(ValueError, match="omits production files") as refusal:
        reports.line_coverage(report, "python-tests", tmp_path, expected)
    assert (
        f"{name} has a coverage `omit` setting: remove its entries for these files"
        in str(refusal.value)
    )


def test_a_setup_rerun_keeps_the_old_name_in_sources_and_the_cov_value(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="1"\n')
    (tmp_path / "oldname").mkdir()
    (tmp_path / "oldname/__init__.py").write_text("value = 1\n")
    installer.install(tmp_path)
    (tmp_path / "oldname").rename(tmp_path / "newname")
    installer.install(tmp_path)
    package = json.loads((tmp_path / "hard-eng.gates.json").read_text())["packages"][0]
    tests = next(gate for gate in package["checks"] if gate["role"] == "tests")
    assert package["sources"] == ["oldname"]
    assert "--cov=oldname" in tests["command"]
