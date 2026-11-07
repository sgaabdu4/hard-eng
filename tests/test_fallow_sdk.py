"""Fallow takes commands from SDKs the repository requires as provided."""

import json
import subprocess
from pathlib import Path

import pytest
import reports


def test_fallow_takes_the_dart_sdk_as_provided_only_in_a_dart_repository(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parent / "fixtures/fallow/audit-unlisted-dart.json"
    audit = json.loads(fixture.read_text())
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(audit))
    repository = tmp_path / "repository"
    (repository / "web").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    assert reports.sdk_binaries(repository / "web") == set()
    with pytest.raises(ValueError, match="passing native audit"):
        reports.validate_fallow(path, reports.sdk_binaries(repository / "web"))
    (repository / "shared").mkdir()
    (repository / "shared/pubspec.yaml").write_text("name: shared\n")
    subprocess.run(["git", "add", "-A"], cwd=repository, check=True)
    provided = reports.sdk_binaries(repository / "web")
    assert provided == {"dart", "flutter"}
    reports.validate_fallow(path, provided)
    dead = audit["dead_code"]
    other = {**dead["unlisted_binaries"][0], "binary_name": "hyprctl"}
    dead["unlisted_binaries"].append(other)
    dead["total_issues"] += 1
    dead["summary"]["total_issues"] += 1
    dead["summary"]["unlisted_binaries"] += 1
    audit["summary"]["dead_code_issues"] += 1
    path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="passing native audit"):
        reports.validate_fallow(path, provided)
