"""The OSV report reader accepts a local uv package that has no version."""

import json
from pathlib import Path

import pytest
import reports

FOLDER = Path(__file__).parent / "fixtures/osv"
REGISTRY = '{ registry = "https://pypi.org/simple" }'


def osv_report(tmp_path: Path, kind: str, source: str = '{ editable = "." }') -> Path:
    lock = (FOLDER / f"{kind}-uv.lock").read_text()
    (tmp_path / "uv.lock").write_text(lock.replace('{ editable = "." }', source))
    report = json.loads((FOLDER / f"{kind}-osv.json").read_text())
    report["results"][0]["source"]["path"] = str(tmp_path / "uv.lock")
    path = tmp_path / "osv.json"
    path.write_text(json.dumps(report))
    return path


@pytest.mark.parametrize("kind", ["single", "workspace"])
@pytest.mark.parametrize("source", ['{ editable = "." }', '{ virtual = "." }'])
def test_osv_accepts_a_local_uv_package_with_no_version(
    tmp_path: Path, kind: str, source: str
) -> None:
    reports.validate_osv(osv_report(tmp_path, kind, source))


def test_osv_refuses_a_registry_package_with_no_version_and_names_it(
    tmp_path: Path,
) -> None:
    path = osv_report(tmp_path, "single", REGISTRY)
    with pytest.raises(ValueError, match="demo") as refused:
        reports.validate_osv(path)
    assert str(tmp_path / "uv.lock") in str(refused.value)


def test_osv_refuses_a_package_with_no_name(tmp_path: Path) -> None:
    path = osv_report(tmp_path, "single")
    report = json.loads(path.read_text())
    del report["results"][0]["packages"][1]["package"]["name"]
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="no name"):
        reports.validate_osv(path)


def change_demo(path: Path, **fields: str | None) -> None:
    report = json.loads(path.read_text())
    demo = report["results"][0]["packages"][1]["package"]
    demo.update({key: value for key, value in fields.items() if value is not None})
    for key in [key for key, value in fields.items() if value is None]:
        del demo[key]
    path.write_text(json.dumps(report))


@pytest.mark.parametrize(
    ("lock_name", "report_name"), [("demo", "Demo"), ("my.pkg", "My_Pkg")]
)
def test_osv_matches_a_local_package_name_ignoring_case_and_marks(
    tmp_path: Path, lock_name: str, report_name: str
) -> None:
    path = osv_report(tmp_path, "single")
    lock = tmp_path / "uv.lock"
    lock.write_text(lock.read_text().replace('name = "demo"', f'name = "{lock_name}"'))
    change_demo(path, name=report_name)
    reports.validate_osv(path)


def test_osv_accepts_a_directory_source(tmp_path: Path) -> None:
    reports.validate_osv(osv_report(tmp_path, "single", '{ directory = "." }'))


@pytest.mark.parametrize(
    ("change", "step"),
    [
        ({"ecosystem": "npm"}, "Update the lockfile"),
        ({"ecosystem": None}, "no ecosystem"),
        ({"version": "1.0", "ecosystem": None}, "no ecosystem"),
    ],
)
def test_osv_names_the_missing_field_and_a_step_that_can_help(
    tmp_path: Path, change: dict[str, str | None], step: str
) -> None:
    path = osv_report(tmp_path, "single")
    change_demo(path, **change)
    with pytest.raises(ValueError, match=step) as refused:
        reports.validate_osv(path)
    assert "uv lock" not in str(refused.value)


def test_osv_refuses_an_empty_version_from_another_managers_lockfile(
    tmp_path: Path,
) -> None:
    path = osv_report(tmp_path, "single")
    report = json.loads(path.read_text())
    report["results"][0]["source"]["path"] = str(tmp_path / "poetry.lock")
    (tmp_path / "poetry.lock").write_text((tmp_path / "uv.lock").read_text())
    path.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="poetry.lock") as refused:
        reports.validate_osv(path)
    assert "uv lock" not in str(refused.value)


def test_osv_refuses_a_local_package_when_the_lockfile_is_missing(
    tmp_path: Path,
) -> None:
    path = osv_report(tmp_path, "single")
    (tmp_path / "uv.lock").unlink()
    with pytest.raises(ValueError, match="demo"):
        reports.validate_osv(path)
