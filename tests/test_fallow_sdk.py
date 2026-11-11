"""Fallow takes commands from SDKs the repository requires as provided."""

import json
import subprocess
from pathlib import Path

import pytest
import reports
from gate_config import Gate
from test_reports import REPORTS


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


def missing_modules_report(tmp_path: Path) -> Path:
    data = json.loads(REPORTS["fallow"])
    data["workspace_diagnostics"] = [
        {"path": "node_modules", "kind": "node-modules-missing"},
        {"path": ".", "kind": "boundaries-not-configured"},
    ]
    path = tmp_path / "report.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.parametrize(
    ("manifest", "install", "passes"),
    [
        ({"name": "core"}, "repo", True),
        ({"name": "core", "dependencies": {}, "devDependencies": {}}, "repo", True),
        ({"name": "core", "dependencies": {"zod": "1.0.0"}}, "repo", False),
        ({"name": "core", "devDependencies": {"vitest": "1.0.0"}}, "repo", False),
        ({"name": "core", "peerDependencies": {"react": "1.0.0"}}, "repo", False),
        (
            {"name": "core", "optionalDependencies": {"fsevents": "1.0.0"}},
            "repo",
            False,
        ),
        ({"name": "core"}, "none", False),
        ({"name": "core"}, "outside", False),
    ],
)
def test_a_member_with_no_dependencies_needs_no_install_folder_of_its_own(
    tmp_path: Path, manifest: dict[str, object], install: str, passes: bool
) -> None:
    repository = tmp_path / "repo"
    member = repository / "packages/core"
    member.mkdir(parents=True)
    (repository / "hard-eng.gates.json").write_text("{}")
    (member / "package.json").write_text(json.dumps(manifest))
    if install != "none":
        ({"repo": repository, "outside": tmp_path}[install] / "node_modules").mkdir()
    path = missing_modules_report(tmp_path)
    if passes:
        reports.validate_fallow(path, set(), member)
    else:
        with pytest.raises(ValueError, match="analysis diagnostics"):
            reports.validate_fallow(path, set(), member)


def test_the_fallow_gate_passes_the_package_folder_to_the_report_check(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repo"
    member = repository / "packages/core"
    member.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    (member / "package.json").write_text(json.dumps({"name": "core"}))
    (repository / "node_modules").mkdir()
    path = missing_modules_report(tmp_path)
    gate: Gate = {"name": "fallow", "command": ["fallow"]}
    reports.validate_scanner_report("fallow", gate, path, ["fallow"], member, 60)
