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
