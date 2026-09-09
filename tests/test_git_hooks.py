"""An uncommitted working-tree fix must never approve broken committed code."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from hard_eng import agents, common, git_hooks, setup
from hard_eng.common import GateError


def commit(root: Path, message: str) -> str:
    common.git(root, "add", ".")
    common.git(
        root, "-c", "user.name=Gate Test", "-c", "user.email=gate@example.test", "commit", "-qm", message
    )
    return common.git(root, "rev-parse", "HEAD").strip()


def copy_runtime(root: Path) -> None:
    source = Path(__file__).resolve().parents[1]
    for name in setup.OWNED:
        shutil.copytree(source / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))


def test_pre_push_uses_committed_code_and_preserves_working_fix(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    launcher = tmp_path / "bin/hard-eng"
    launcher.parent.mkdir()
    launcher.write_text("raise SystemExit(8)\n")
    revision = commit(tmp_path, "Broken committed code")
    launcher.write_text("raise SystemExit(0)\n")
    stdin = f"refs/heads/main {revision} refs/heads/main {'0' * 40}\n"
    with pytest.raises(GateError, match="failed its gates"):
        git_hooks.check_push(tmp_path, stdin)
    assert launcher.read_text() == "raise SystemExit(0)\n"
    assert common.git(tmp_path, "rev-parse", "HEAD").strip() == revision
    assert common.git(tmp_path, "worktree", "list", "--porcelain").count("worktree ") == 1
    fixed = commit(tmp_path, "Fix committed code")
    git_hooks.check_push(tmp_path, stdin.replace(revision, fixed))


def test_delete_push_needs_no_scan_and_invalid_input_fails() -> None:
    assert git_hooks.revisions(f"(delete) {'0' * 40} refs/heads/old {'a' * 40}") == []
    with pytest.raises(GateError, match="Invalid Git"):
        git_hooks.revisions("malformed")


def test_hook_install_preserves_another_owner(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    hook = tmp_path / ".git/hooks/pre-push"
    hook.write_text("#!/bin/sh\nexit 7\n")
    with pytest.raises(GateError, match="another owner"):
        git_hooks.install(tmp_path, ".agents/hard-eng/bin/hard-eng")
    assert hook.read_text() == "#!/bin/sh\nexit 7\n"
    hook.unlink()
    git_hooks.install(tmp_path, ".agents/hard-eng/bin/hard-eng")
    assert 'pre-push "$@"' in hook.read_text()
    common.git(tmp_path, "config", "core.hooksPath", ".githooks")
    git_hooks.install(tmp_path, ".agents/hard-eng/bin/hard-eng")
    assert (tmp_path / ".githooks/pre-push").exists()
    common.git(tmp_path, "config", "core.hooksPath", str(tmp_path.parent / "shared-hooks"))
    with pytest.raises(GateError, match="outside this repository"):
        git_hooks.install(tmp_path, ".agents/hard-eng/bin/hard-eng")


@pytest.mark.parametrize("configured", [False, True])
def test_install_produces_a_working_local_cli_and_preserves_project_instructions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configured: bool,
) -> None:
    upstream, project = tmp_path / "upstream", tmp_path / "project"
    source = Path(__file__).resolve().parents[1]
    for path in (upstream, project):
        subprocess.run(["git", "init", "-qb", "main", str(path)], check=True)
    copy_runtime(upstream)
    revision = commit(upstream, "Runtime")
    (project / "src").mkdir()
    (project / "src/app.py").write_text("value = 1\n")
    if configured:
        shutil.copyfile(source / "skills/he/templates/hard-eng.python.json", project / "hard-eng.gates.json")
    (project / "AGENTS.md").write_text("# Existing project rules\nKeep this instruction.\n")
    custom = project / ".agents/skills/project-only/SKILL.md"
    custom.parent.mkdir(parents=True)
    custom.write_text("Keep this project skill.\n")

    def green(_root: Path) -> str:
        return revision

    monkeypatch.setattr(setup, "UPSTREAM", str(upstream))
    monkeypatch.setattr(setup, "latest_green", green)
    setup.install(project)
    assert setup.update(project) == "Hard Eng is current"
    for agent in agents.AGENTS:
        agents.configure(project, agent)
    result = common.run(["python3", str(project / ".agents/hard-eng/bin/hard-eng"), "validate"], project)
    assert result.returncode == (0 if configured else 1), result.stderr
    if configured:
        assert "1 supported packages" in result.stdout
    else:
        assert not (project / "hard-eng.gates.json").exists()
        assert (project / ".codex/hooks.json").is_file()
    assert "Keep this instruction." in (project / "AGENTS.md").read_text()
    assert (project / "CLAUDE.md").read_text() == "@AGENTS.md\n"
    assert (project / ".git/hooks/pre-push").stat().st_mode & 0o111
    assert not (project / ".gitmodules").exists()
    assert not (project / ".agents/hard-eng/.git").exists()
    assert not (project / ".codex/skills").exists()
    assert not (project / ".github/skills").exists()
    assert (project / ".claude/skills/he").resolve() == project / ".agents/skills/he"
    assert (project / ".agents/skills/research/SKILL.md").is_file()
    assert custom.read_text() == "Keep this project skill.\n"


def test_update_selects_newest_green_main_and_preserves_unrelated_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream, project = tmp_path / "upstream", tmp_path / "project"
    for folder in (upstream, project):
        subprocess.run(["git", "init", "-qb", "main", str(folder)], check=True)
        common.git(folder, "config", "user.name", "Gate Test")
        common.git(folder, "config", "user.email", "gate@example.test")
    copy_runtime(upstream)
    version = upstream / "hard_eng/runtime_version.py"
    version.write_text("version = 1\n")
    old = commit(upstream, "Initial runtime")
    monkeypatch.setattr(setup, "UPSTREAM", str(upstream))

    def initial(_root: Path) -> str:
        return old

    with monkeypatch.context() as initial_setup:
        initial_setup.setattr(setup, "latest_green", initial)
        setup.install(project)
    commit(project, "Install runtime")
    version.write_text("version = 2\n")
    green = commit(upstream, "Verified runtime")
    version.write_text("version = 3\n")
    red = commit(upstream, "Broken runtime")
    (project / "staged.txt").write_text("Keep staged\n")
    common.git(project, "add", "staged.txt")
    (project / "untracked.txt").write_text("Keep untracked\n")

    def api(_argv: list[str], _root: Path) -> str:
        import json

        return json.dumps(
            [
                {
                    "workflow_runs": [
                        {
                            "head_sha": old,
                            "conclusion": "success",
                            "status": "completed",
                            "head_branch": "main",
                            "event": "push",
                        },
                        {
                            "head_sha": red,
                            "conclusion": "success",
                            "status": "completed",
                            "head_branch": "other",
                            "event": "push",
                        },
                        {
                            "head_sha": green,
                            "conclusion": "success",
                            "status": "completed",
                            "head_branch": "main",
                            "event": "push",
                        },
                    ]
                }
            ]
        )

    monkeypatch.setattr(setup, "checked", api)
    assert "Updated" in setup.update(project)
    installed = project / ".agents/hard-eng/hard_eng/runtime_version.py"
    assert installed.read_text() == "version = 2\n"
    assert (
        common.git(project, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").strip()
        == ".agents/hard-eng/hard_eng/runtime_version.py"
    )
    assert common.git(project, "diff", "--cached", "--name-only").strip() == "staged.txt"
    assert (project / "untracked.txt").read_text() == "Keep untracked\n"
    assert setup.update(project) == "Hard Eng is current"
    installed.write_text("local change\n")
    with pytest.raises(GateError, match="Local Hard Eng changes"):
        setup.update(project)
    assert installed.read_text() == "local change\n"
