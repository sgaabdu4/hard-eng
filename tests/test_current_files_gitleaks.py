"""Prove the current-files Gitleaks scanner preserves its security boundary."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

import gitleaks_scan
import pytest
from gate_config import validate_gate
from gitleaks_scan import run_current_files, snapshot_command


def git(repository: Path, *arguments: str) -> None:
    subprocess.run(["git", *arguments], cwd=repository, check=True)


def repository(root: Path) -> Path:
    project = root / "repository"
    git(root, "init", "-q", str(project))
    git(project, "config", "user.name", "Fixture")
    git(project, "config", "user.email", "fixture@example.invalid")
    (project / ".gitignore").write_text("generated/\ntracked-ignored.txt\n")
    (project / "tracked.txt").write_text("committed\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "baseline")
    return project


def scanner_script(directory: Path) -> Path:
    scanner = directory / "gitleaks"
    scanner.write_text(
        f"#!{sys.executable}\n"
        + """import json
import os
import sys
from pathlib import Path

root = Path.cwd()
contents = {
    path: (root / path).read_text()
    for path in (
        'tracked.txt',
        'tracked-ignored.txt',
        'untracked.txt',
        'deleted.txt',
        'inside-link.txt',
        'skills/submodule/submodule.txt',
        'generated/output.txt',
    )
    if (root / path).is_file()
}
report = Path(sys.argv[sys.argv.index('--report-path') + 1])
report.parent.mkdir(parents=True, exist_ok=True)
report.write_text(
    '{"version":"2.1.0","runs":[{"results":[],"tool":{"driver":'
    '{"name":"gitleaks","rules":[{"id":"fixture"}]}}}]}'
)
Path(os.environ['GITLEAKS_SCOPE_RESULT']).write_text(
    json.dumps({'contents': contents, 'report': str(report), 'cwd': str(root)})
)
raise SystemExit(int(os.environ.get('GITLEAKS_SCOPE_EXIT', '0')))
"""
    )
    scanner.chmod(0o755)
    return scanner


def scan_command(scanner: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    monkeypatch.setenv("PATH", f"{scanner.parent}{os.pathsep}{os.environ['PATH']}")
    return [
        "gitleaks",
        "dir",
        ".",
        "--report-path",
        "reports/gitleaks.sarif",
    ]


def add_submodule(project: Path, root: Path) -> None:
    source = root / "submodule-source"
    git(root, "init", "-q", str(source))
    git(source, "config", "user.name", "Fixture")
    git(source, "config", "user.email", "fixture@example.invalid")
    (source / "submodule.txt").write_text("committed submodule\n")
    git(source, "add", ".")
    git(source, "commit", "-qm", "submodule baseline")
    git(
        project,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(source),
        "skills/submodule",
    )
    git(project, "commit", "-qm", "submodule input")


def test_current_files_include_authored_changes_and_exclude_ignored_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    add_submodule(project, tmp_path)
    (project / "tracked.txt").write_text("modified\n")
    os.symlink(project / "tracked.txt", project / "inside-link.txt")
    git(project, "add", "inside-link.txt")
    git(project, "commit", "-qm", "inside link input")
    (project / "tracked-ignored.txt").write_text("tracked ignored\n")
    git(project, "add", "-f", "tracked-ignored.txt")
    git(project, "commit", "-qm", "tracked ignored input")
    (project / "untracked.txt").write_text("untracked\n")
    generated = project / "generated/output.txt"
    generated.parent.mkdir()
    generated.write_text("ignored generated output\n")
    (project / "skills/submodule/submodule.txt").write_text("modified submodule\n")
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))

    completed = run_current_files(
        scan_command(scanner_script(tmp_path), monkeypatch),
        project,
        30,
        None,
        sys.stderr,
    )

    assert completed.returncode == 0
    observed = json.loads(result.read_text())
    assert observed["contents"] == {
        "tracked-ignored.txt": "tracked ignored\n",
        "tracked.txt": "modified\n",
        "untracked.txt": "untracked\n",
        "inside-link.txt": "modified\n",
        "skills/submodule/submodule.txt": "modified submodule\n",
    }
    assert Path(observed["report"]) == project / "reports/gitleaks.sarif"
    assert Path(observed["cwd"]) != project


def test_native_secrets_gate_uses_current_files_snapshot(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    (tmp_path / ".gitignore").write_text("generated/\n")
    (tmp_path / "tracked.txt").write_text("tracked\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "baseline")
    (tmp_path / "untracked.txt").write_text("untracked\n")
    generated = tmp_path / "generated/output.txt"
    generated.parent.mkdir()
    generated.write_text("ignored generated output\n")
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))
    gate = {
        "name": "secrets-files",
        "role": "secrets-files",
        "command": scan_command(scanner_script(tmp_path), monkeypatch),
        "report": {"type": "gitleaks", "path": "reports/gitleaks.sarif"},
    }

    assert (
        runner.run_gate({"path": ".", "checks": []}, gate, 30, threading.Lock())
        is False
    )

    observed = json.loads(result.read_text())
    assert observed["contents"]["untracked.txt"] == "untracked\n"
    assert "generated/output.txt" not in observed["contents"]


def test_current_files_reject_external_symbolic_links_before_scanning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside content\n")
    os.symlink(outside, project / "external.txt")
    git(project, "add", "external.txt")
    git(project, "commit", "-qm", "external link")
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))

    with pytest.raises(ValueError, match="escapes the repository"):
        run_current_files(
            scan_command(scanner_script(tmp_path), monkeypatch),
            project,
            30,
            None,
            sys.stderr,
        )

    assert not result.exists()


def test_current_files_rejects_an_in_repository_directory_symlink_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    os.symlink(".", project / "loop")
    git(project, "add", "loop")
    git(project, "commit", "-qm", "directory link cycle")
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))

    with pytest.raises(ValueError, match="directory symlink cycle"):
        run_current_files(
            scan_command(scanner_script(tmp_path), monkeypatch),
            project,
            30,
            None,
            sys.stderr,
        )

    assert not result.exists()


def test_current_files_propagate_inventory_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)

    def fail_inventory(*_args: object, **_kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, ["git", "ls-files"])

    monkeypatch.setattr(gitleaks_scan.subprocess, "run", fail_inventory)

    with pytest.raises(subprocess.CalledProcessError):
        run_current_files(
            scan_command(scanner_script(tmp_path), monkeypatch),
            project,
            30,
            None,
            sys.stderr,
        )


def test_current_files_preserve_scanner_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))
    monkeypatch.setenv("GITLEAKS_SCOPE_EXIT", "7")

    completed = run_current_files(
        scan_command(scanner_script(tmp_path), monkeypatch),
        project,
        30,
        None,
        sys.stderr,
    )

    assert completed.returncode == 7
    assert result.exists()


def test_current_files_omits_a_normal_unstaged_tracked_deletion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    deleted = project / "deleted.txt"
    deleted.write_text("tracked before deletion\n")
    git(project, "add", "deleted.txt")
    git(project, "commit", "-qm", "tracked deletion input")
    deleted.unlink()
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))

    completed = run_current_files(
        scan_command(scanner_script(tmp_path), monkeypatch),
        project,
        30,
        None,
        sys.stderr,
    )

    assert completed.returncode == 0
    assert "deleted.txt" not in json.loads(result.read_text())["contents"]


def test_current_files_rejects_an_absolute_report_path_through_a_symlink(
    tmp_path: Path,
) -> None:
    project = repository(tmp_path)
    outside = tmp_path / "outside-reports"
    outside.mkdir()
    os.symlink(outside, project / "reports-link")

    with pytest.raises(ValueError, match="escapes the repository"):
        snapshot_command(
            [
                "gitleaks",
                "dir",
                ".",
                "--report-path",
                str(project / "reports-link/leaks.sarif"),
            ],
            project,
        )


@pytest.mark.parametrize(
    "command",
    [
        ["gitleaks", "dir", "/tmp", "--report-path", "reports/gitleaks.sarif"],
        ["gitleaks", "git", ".", "--report-path", "reports/gitleaks.sarif"],
    ],
)
def test_secrets_files_gate_rejects_scan_targets_outside_its_snapshot(
    tmp_path: Path, command: list[str]
) -> None:
    with pytest.raises(ValueError, match="native `gitleaks dir .`"):
        validate_gate(
            {
                "name": "secrets-files",
                "role": "secrets-files",
                "command": command,
                "report": {"type": "gitleaks", "path": "reports/gitleaks.sarif"},
            },
            tmp_path,
            set(),
        )
