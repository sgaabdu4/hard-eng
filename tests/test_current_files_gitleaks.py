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
import update
from conftest import commit, init
from conftest import git as git_output
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
        '.env',
        'skill-alias',
        'skills/submodule/submodule.txt',
        'generated/output.txt',
        '.claude/skills/example/SKILL.md',
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
    alias = project / "skill-alias"
    alias.symlink_to("skills/submodule/submodule.txt")
    git(project, "add", "skill-alias")
    git(project, "commit", "-qm", "submodule alias input")
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
        "skill-alias": "modified submodule\n",
        "skills/submodule/submodule.txt": "modified submodule\n",
    }
    assert Path(observed["report"]) == project / "reports/gitleaks.sarif"
    assert Path(observed["cwd"]) != project


def scanned(
    tmp_path: Path, project: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, str]:
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
    return json.loads(result.read_text())["contents"]


def test_tracked_link_to_an_ignored_local_secret_is_not_scanned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    (project / ".gitignore").write_text(".env.local\n")
    (project / ".env.local").write_text("TOKEN=local-only-fixture-secret\n")
    (project / ".env").symlink_to(".env.local")
    git(project, "add", ".gitignore", ".env")
    git(project, "commit", "-qm", "local environment link")
    assert scanned(tmp_path, project, monkeypatch) == {"tracked.txt": "committed\n"}


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


def test_current_files_requires_an_initialized_gitlink_before_aliases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    add_submodule(project, tmp_path)
    checkout = tmp_path / "checkout"
    git(tmp_path, "clone", "--quiet", str(project), str(checkout))
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))

    with pytest.raises(
        ValueError, match="submodule is uninitialized: skills/submodule"
    ):
        run_current_files(
            scan_command(scanner_script(tmp_path), monkeypatch),
            checkout,
            30,
            None,
            sys.stderr,
        )

    assert not result.exists()


@pytest.mark.parametrize("gate_fails", [False, True])
def test_candidate_initializes_consumer_submodule_and_cleans_up(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    gate_fails: bool,
) -> None:
    source, target, _ = release
    module = target.parent / "consumer-module"
    init(module)
    (module / "skill.txt").write_text("pinned skill\n")
    commit(module, "consumer skill")
    git(
        target,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(module),
        ".skills",
    )
    (target / "skill-link").symlink_to(".skills/skill.txt")
    (target / "package.json").unlink()
    config_path = target / "hard-eng.gates.json"
    config = json.loads(config_path.read_text())
    config["shared"][0]["command"] = [
        "python3",
        "-c",
        (
            "from pathlib import Path; "
            "assert Path('skill-link').read_text() == 'pinned skill\\n'; "
            f"print('SUBMODULE_READ'); raise SystemExit({int(gate_fails)})"
        ),
    ]
    config_path.write_text(json.dumps(config))
    commit(target, "consumer with linked submodule")
    config_before = (target / ".git/config").read_bytes()
    (target / ".skills/skill.txt").write_text("local skill edit\n")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "always")
    candidate = target.parent / "candidate"
    if gate_fails:
        with pytest.raises(subprocess.CalledProcessError):
            update.verify_candidate(
                target, source, {"project.txt": "updated\n"}, {}, candidate
            )
    else:
        update.verify_candidate(
            target, source, {"project.txt": "updated\n"}, {}, candidate
        )
    assert "\nSUBMODULE_READ\n" in capfd.readouterr().err
    assert not candidate.exists()
    assert git_output(target, "worktree", "list", "--porcelain").count("worktree ") == 1
    assert (target / "skill-link").read_text() == "local skill edit\n"
    assert (target / ".git/config").read_bytes() == config_before
    assert (target / "project.txt").read_text() == "original\n"


def test_clean_checkout_requires_committed_skill_link_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = repository(tmp_path)
    (project / ".gitignore").write_text(".agents/\nreports/\n")
    skill = project / ".agents/skills/example/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# Required skill\n")
    alias = project / ".claude/skills/example"
    alias.parent.mkdir(parents=True)
    alias.symlink_to("../../.agents/skills/example", target_is_directory=True)
    git(project, "add", ".gitignore", ".claude")
    git(project, "commit", "-qm", "incomplete migration")
    checkout = tmp_path / "checkout"
    git(tmp_path, "clone", "--quiet", str(project), str(checkout))
    result = tmp_path / "result.json"
    monkeypatch.setenv("GITLEAKS_SCOPE_RESULT", str(result))
    command = scan_command(scanner_script(tmp_path), monkeypatch)

    with pytest.raises(ValueError, match="source is missing: .claude/skills/example"):
        run_current_files(command, checkout, 30, None, sys.stderr)
    assert not result.exists()

    git(project, "add", "--force", ".agents/skills/example")
    git(project, "commit", "-qm", "include required skill target")
    git(checkout, "pull", "--ff-only", "--quiet")
    assert run_current_files(command, checkout, 30, None, sys.stderr).returncode == 0
    assert (
        json.loads(result.read_text())["contents"][".claude/skills/example/SKILL.md"]
        == "# Required skill\n"
    )


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
    assert "deleted.txt" not in scanned(tmp_path, project, monkeypatch)


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


def test_history_scan_covers_only_commits_a_known_base_lacks(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A based check must not rescan the whole history; an unknown base must."""
    base = git_output(repository, "rev-parse", "HEAD")
    full = ["gitleaks", "git", ".", "--log-opts=--all", "--report-path", "r.sarif"]
    scoped = gitleaks_scan.new_commits_command(full, repository, "HEAD")
    assert scoped == [
        *full[:3],
        f"--log-opts={base}..HEAD",
        *full[4:],
    ]
    assert base[:7] in capsys.readouterr().out
    for unknown in (None, "0" * 40, "missing-reference", "--all"):
        assert gitleaks_scan.new_commits_command(full, repository, unknown) == full
    custom = [*full[:3], "--log-opts=main..HEAD"]
    assert gitleaks_scan.new_commits_command(custom, repository, "HEAD") == custom
