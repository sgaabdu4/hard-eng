"""Real Git update transactions preserve local work and obey check scope."""

import io
import json
import re
import shutil
import subprocess
import tomllib
import urllib.error
import urllib.request
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
import update
from conftest import SOURCE, commit, git, init
from gate_config import JsonObject, json_file
from shipping import ShippingPolicy
from test_setup import repository as setup_repository
from test_setup import snapshot


def test_installer_preserves_native_mcp_settings_on_rerun(
    installer: ModuleType, tmp_path: Path
) -> None:
    git(tmp_path, "init", "-q")
    settings = {
        "command": "project-mcp",
        "args": ["--project", "fitness"],
        "env": {"PROJECT_MODE": "local"},
        "enabled": False,
    }
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"project-mcp": settings}})
    )
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex/config.toml").write_text(
        '[mcp_servers.project-mcp]\ncommand = "project-mcp"\n'
        'args = ["--project", "fitness"]\nenabled = false\n'
        '[mcp_servers.project-mcp.env]\nPROJECT_MODE = "local"\n'
    )
    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)
    assert ".mcp.json" not in changes
    servers = tomllib.loads(
        changes.get(".codex/config.toml", (tmp_path / ".codex/config.toml").read_text())
    )["mcp_servers"]
    assert servers["project-mcp"] == settings
    assert set(servers) == {"project-mcp"}
    for name, content in changes.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    repeated: dict[str, str] = {}
    installer.configure_mcp(tmp_path, repeated)
    assert all((tmp_path / name).read_text() == text for name, text in repeated.items())


def test_uninitialized_skill_submodule_cannot_be_silently_omitted(
    tmp_path: Path,
) -> None:
    skills = tmp_path / ".agents/skills"
    skills.mkdir(parents=True)
    (skills / "canonical").symlink_to("../skill-sources/canonical/skills/canonical")
    with pytest.raises(ValueError, match="submodule update"):
        update.scaffold_files(tmp_path)


def test_installed_project_scans_skip_agent_worktrees(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    init(root)
    (root / "package.json").write_text('{"private":true}')
    (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    installer.install(root)
    commit(root, "installed")
    git(root, "worktree", "add", "-q", ".claude/worktrees/builder")
    from gitleaks_scan import scan_paths

    assert not [path for path in scan_paths(root) if "worktrees" in path.parts]


def test_scaffold_distribution_excludes_ignored_runtime_files(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("node_modules/\n__pycache__/\n")
    skill = tmp_path / ".agents/skills/recorder"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Recorder\n")
    for directory in ("node_modules", "__pycache__"):
        binary = skill / directory / "binary"
        binary.parent.mkdir()
        binary.write_bytes(b"\xff\x00")
    assert update.scaffold_files(tmp_path) == {".agents/skills/recorder/SKILL.md"}


def test_installed_hooks_survive_project_ruff_settings(tmp_path: Path) -> None:
    for name in update.scaffold_files(SOURCE):
        if name.startswith(".hooks/"):
            (tmp_path / name).parent.mkdir(exist_ok=True)
            shutil.copy(SOURCE / name, tmp_path / name)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "app"\nversion = "1"\nrequires-python = ">=3.14"\n'
        '[tool.ruff]\ntarget-version = "py314"\nline-length = 120\n'
        '[tool.ruff.lint]\nselect = ["ALL"]\n'
    )
    for command in (["format", "--check", "."], ["check", "."]):
        result = subprocess.run(
            ["uvx", "ruff@latest", *command, "--no-cache"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr


def fixed_revision(revision: str) -> Callable[[str], str]:
    def selected(_previous: str) -> str:
        return revision

    return selected


def test_update_commits_only_scaffold_and_preserves_index(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source, target, _ = release
    ignored = ".agents/skills/he/references/ignored-update.md"
    ignored_path = source / ignored
    ignored_path.write_text("ignored update fixture\n")
    revision = commit(source, "verified update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    (target / ".git/info/exclude").write_text(f"{ignored}\n")
    (target / "staged.txt").write_text("unrelated staged work\n")
    git(target, "add", "staged.txt")
    (target / "project.txt").write_text("unrelated working edit\n")
    message = update.update(target)
    assert revision in message
    changed = set(
        git(
            target, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"
        ).splitlines()
    )
    assert changed == {
        update.SOURCE_FILE,
        ".agents/skills/he/references/workflow.md",
        ignored,
    }
    assert git(target, "diff", "--cached", "--name-only") == "staged.txt"
    assert (target / "project.txt").read_text() == "unrelated working edit\n"
    assert "SOURCE_CHECK" not in capfd.readouterr().err
    assert git(target, "worktree", "list", "--porcelain").count("worktree ") == 1


@pytest.mark.parametrize("reject_commit", [False, True])
def test_update_commits_husky_launcher_and_runs_native_hook(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    reject_commit: bool,
    shipping_policy: ShippingPolicy,
) -> None:
    source, target, _ = release
    shim = target / ".husky/_/pre-push"
    shim.parent.mkdir(parents=True)
    shim.write_text('#!/usr/bin/env sh\n. "$(dirname "$0")/h"')
    shim.chmod(0o755)
    dispatcher = shim.parent / "h"
    dispatcher.write_text("""#!/usr/bin/env sh
[ "$HUSKY" = "2" ] && set -x
n=$(basename "$0")
s=$(dirname "$(dirname "$0")")/$n
[ ! -f "$s" ] && exit 0

if [ -f "$HOME/.huskyrc" ]; then
\techo "husky - '~/.huskyrc' is DEPRECATED, please move your code to ~/.config/husky/init.sh"
fi
i="${XDG_CONFIG_HOME:-$HOME/.config}/husky/init.sh"
[ -f "$i" ] && . "$i"

[ "${HUSKY-}" = "0" ] && exit 0

export PATH="node_modules/.bin:$PATH"
sh -e "$s" "$@"
c=$?

[ $c != 0 ] && echo "husky - $n script failed (code $c)"
[ $c = 127 ] && echo "husky - command not found in PATH=$PATH"
exit $c
""")
    launcher = target / ".husky/pre-push"
    launcher.write_text((target / ".git/hooks/pre-push").read_text())
    git(target, "config", "core.hooksPath", ".husky/_")
    config_path = target / "hard-eng.gates.json"
    config = json.loads(config_path.read_text())
    config["shipping"] = shipping_policy
    config["shared"].append(
        {"name": "shell", "role": "shell", "command": ["python3", "-c", "pass"]}
    )
    config_path.write_text(json.dumps(config))
    base = commit(target, "existing canonical Python launcher under Husky")
    shim_bytes = shim.read_bytes()
    dispatcher_bytes = dispatcher.read_bytes()
    select_release(source, monkeypatch)
    revision = git(source, "rev-parse", "HEAD")
    monkeypatch.setenv("HUSKY", "1")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(target / "user-config"))
    if reject_commit:
        old_launcher = launcher.read_bytes()
        old_marker = (target / update.SOURCE_FILE).read_bytes()
        reject_shim = shim.with_name("pre-commit")
        reject_shim.write_bytes(shim_bytes)
        reject_shim.chmod(0o755)
        (target / ".husky/pre-commit").write_text("#!/bin/sh\nexit 23\n")
        with pytest.raises(subprocess.SubprocessError):
            update.update(target)
        assert launcher.read_bytes() == old_launcher
        assert (target / update.SOURCE_FILE).read_bytes() == old_marker
        assert git(target, "rev-parse", "HEAD") == base
        return
    assert revision in update.update(target)
    assert ".husky/pre-push" in git(target, "diff", "--name-only", base).splitlines()
    assert launcher.read_text().startswith("#!/usr/bin/env sh\nexec python3 ")
    assert shim.read_bytes() == shim_bytes
    assert dispatcher.read_bytes() == dispatcher_bytes
    assert git(target, "config", "core.hooksPath") == ".husky/_"
    subprocess.run(
        ["git", "hook", "run", "pre-push", "--", "origin", "unused"],
        cwd=target,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )

    def verified(_revision: str) -> bool:
        return True

    monkeypatch.setattr(update, "verified_revision", verified)
    assert update.check_scaffold_update(target, base)
    launcher.write_text("#!/bin/sh\necho custom\n")
    commit(target, "custom hook is not a canonical scaffold update")
    with pytest.raises(subprocess.CalledProcessError):
        update.check_scaffold_update(target, base)


def test_ignored_local_configuration_prevents_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    name = ".mcp.json"
    monkeypatch.setenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
    (target / "app.js").write_text('import { Client } from "appwrite";\n')
    (target / name).write_text(
        '{"mcpServers":{"appwrite":{"url":"https://mcp.appwrite.io/"}}}\n'
    )
    commit(target, "configure applicable Appwrite integration")
    select_release(source, monkeypatch)
    git(target, "rm", "--cached", name)
    git(target, "commit", "-qm", "keep integration configuration local")
    (target / ".git/info/exclude").write_text(name + "\n")
    local = '{"mcpServers":{"private":{"command":"private-integration"}}}\n'
    (target / name).write_text(local)
    (target / "staged.txt").write_text("unrelated staged work\n")
    git(target, "add", "staged.txt")
    (target / "project.txt").write_text("unrelated working edit\n")
    before = git(target, "rev-parse", "HEAD")
    marker_before = (target / update.SOURCE_FILE).read_bytes()
    with pytest.raises(ValueError, match="overlaps local edits"):
        update.update(target)
    assert (target / name).read_text() == local
    assert git(target, "rev-parse", "HEAD") == before
    assert (target / update.SOURCE_FILE).read_bytes() == marker_before
    assert git(target, "diff", "--cached", "--name-only") == "staged.txt"
    assert (target / "project.txt").read_text() == "unrelated working edit\n"
    assert git(target, "worktree", "list", "--porcelain").count("worktree ") == 1


@pytest.mark.parametrize("case", ["clean", "husky", "dirty", "rejected"])
def test_install_commits_only_clean_installed_paths(
    installer: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    case: str,
) -> None:
    tmp_path = tmp_path / "project"
    init(tmp_path)
    (tmp_path / "package.json").write_text('{"private":true}')
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    commit(tmp_path, "project")
    if case == "dirty":
        (tmp_path / "AGENTS.md").write_text("# Uncommitted project rules\n")
    if case == "husky":
        shim = tmp_path / ".husky/_/pre-push"
        shim.parent.mkdir(parents=True)
        shim.write_text('#!/usr/bin/env sh\n. "$(dirname "$0")/h"')
        (shim.parent / "h").write_text("#!/usr/bin/env sh\n")
        (tmp_path / ".gitignore").write_text(".husky/_/\n")
        commit(tmp_path, "husky")
        git(tmp_path, "config", "core.hooksPath", ".husky/_")
    if case == "rejected":
        hook = tmp_path / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\necho rejected by project hook\nexit 1\n")
        hook.chmod(0o755)
    installer.install(tmp_path)
    output = capsys.readouterr().out
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    if case in {"clean", "husky"}:
        assert "Committed the installed files locally without pushing." in output
        assert status == []
        assert (".husky/pre-push" in git(tmp_path, "ls-files")) == (case == "husky")
        if case == "clean":
            installer.install(tmp_path)
            assert "Installed files already match the current commit." in (
                capsys.readouterr().out
            )
        return
    reason = {
        "dirty": "these paths already had local changes",
        "rejected": "rejected by project hook",
    }[case]
    assert f"Installed files are not committed ({reason})" in output
    assert ".hooks/ " in output and ".agents/skills/he/ " in output
    assert "?? AGENTS.md" in status and "?? .hooks/" in status
    assert not subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_untracked_install_is_named_instead_of_local_edits(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, old = release
    select_release(source, monkeypatch)
    git(target, "rm", "-rq", "--cached", ".hooks", ".agents")
    git(target, "commit", "-qm", "installed files left untracked")
    with pytest.raises(
        ValueError,
        match=r"^Installed Hard Eng files are not committed: \.agents/skills/he/ \.hooks/; commit them",
    ):
        update.update(target)
    assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == old


@pytest.mark.parametrize("wrapped", [True, False])
def test_scaffold_update_validates_retained_files_scanner(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    wrapped: bool,
) -> None:
    source, target, old = release
    config_path = target / "hard-eng.gates.json"
    config = json.loads(config_path.read_text())
    command = ["gitleaks", "dir", ".", "--report-path", "coverage/files.sarif"]
    if wrapped:
        command = [
            "node",
            "scripts/run_tracked_gitleaks.mjs",
            *command[:2],
            *command[3:],
        ]
    config["shared"].append(
        {"name": "files", "role": "secrets-files", "command": command}
    )
    config_path.write_text(json.dumps(config))
    before = commit(target, "existing project scanner")
    config_before = config_path.read_bytes()
    marker_before = (target / update.SOURCE_FILE).read_bytes()
    select_release(source, monkeypatch)

    if wrapped:
        with pytest.raises(
            ValueError, match="secrets-files requires native `gitleaks dir .`"
        ):
            update.update(target)
        assert git(target, "rev-parse", "HEAD") == before
        assert (target / update.SOURCE_FILE).read_bytes() == marker_before
    else:
        assert "Updated Hard Eng" in update.update(target)
        assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] != old
        assert "FAIL application-check" not in capfd.readouterr().err
    assert config_path.read_bytes() == config_before
    assert git(target, "status", "--porcelain") == ""
    assert git(target, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_scaffold_update_does_not_import_extra_candidate_hook_modules(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    shadow = target / ".hooks/typing.py"
    shadow.write_text('raise RuntimeError("candidate hook import")\n')
    commit(target, "preserved project hook module")
    select_release(source, monkeypatch)

    assert "Updated Hard Eng" in update.update(target)
    assert shadow.read_text() == 'raise RuntimeError("candidate hook import")\n'
    assert git(target, "status", "--porcelain") == ""


def test_overlapping_local_edit_prevents_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, old = release
    select_release(source, monkeypatch)
    reference = target / ".agents/skills/he/references/workflow.md"
    reference.write_text("local custom instructions\n")
    with pytest.raises(subprocess.CalledProcessError):
        update.update(target)
    assert reference.read_text() == "local custom instructions\n"
    assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == old


@pytest.mark.parametrize("case", ["unedited", "edited", "rejected"])
def test_update_removes_unused_stack_skill_unless_edited(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    source, target, old = release
    skill = ".agents/skills/appwrite-backend"
    link = ".claude/skills/appwrite-backend"
    shutil.copytree(source / skill, target / skill)
    (target / link).symlink_to("../../" + skill)
    guide = target / skill / "SKILL.md"
    if case == "edited":
        guide.write_text("local Appwrite rules\n")
    commit(target, "install from a release that copied every skill")
    installed = set(git(target, "ls-files", "--", skill, link).splitlines())
    select_release(source, monkeypatch)
    if case == "edited":
        with pytest.raises(ValueError, match="Local scaffold edit"):
            update.update(target)
        assert guide.read_text() == "local Appwrite rules\n"
        assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == old
        return
    if case == "rejected":
        hook = target / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        with pytest.raises(subprocess.SubprocessError):
            update.update(target)
        assert git(target, "status", "--porcelain") == ""
        assert (target / link / "SKILL.md").is_file()
        return
    update.update(target)
    deleted = git(
        target,
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "--diff-filter=D",
        "-r",
        "HEAD",
    )
    assert set(deleted.splitlines()) == installed
    assert not (target / skill).exists()
    assert not (target / link).is_symlink()
    assert (target / ".claude/skills/he/SKILL.md").is_file()


@pytest.mark.parametrize("name", ["team.md", "model-roles.md"])
def test_install_adds_claude_rules_and_keeps_project_rules(
    installer: ModuleType, tmp_path: Path, name: str
) -> None:
    setup_repository(tmp_path)
    project_rule = tmp_path / ".claude/rules" / name
    project_rule.parent.mkdir(parents=True)
    project_rule.write_text("Project Claude rule\n")
    before = snapshot(tmp_path)
    if name == "model-roles.md":
        with pytest.raises(ValueError, match="already differs"):
            installer.install(tmp_path)
        assert snapshot(tmp_path) == before
        return
    installer.install(tmp_path)
    assert project_rule.read_text() == "Project Claude rule\n"
    for rule in (installer.SOURCE / ".claude/rules").glob("*.md"):
        assert (project_rule.parent / rule.name).read_bytes() == rule.read_bytes()
    installed = snapshot(tmp_path)
    installer.install(tmp_path)
    assert snapshot(tmp_path) == installed


@pytest.mark.parametrize("edited", [False, True])
def test_update_refreshes_claude_rules_and_keeps_project_rules(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, edited: bool
) -> None:
    source, target, old = release
    rules = target / ".claude/rules"
    (rules / "team.md").write_text("Project Claude rule\n")
    if edited:
        (rules / "subagents.md").write_text("Local subagent rule\n")
    base = commit(target, "project rules")
    (source / ".claude/rules/model-roles.md").write_text("Updated model roles\n")
    (source / ".claude/rules/review.md").write_text("New review rule\n")
    (source / ".claude/rules/subagents.md").unlink()
    select_release(source, monkeypatch)
    if edited:
        with pytest.raises(ValueError, match="Local scaffold edit"):
            update.update(target)
        assert (rules / "subagents.md").read_text() == "Local subagent rule\n"
        assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == old
        return
    update.update(target)
    changed = git(
        target, "diff-tree", "--no-commit-id", "--name-status", "-r", "HEAD"
    ).splitlines()
    assert {
        "M\t.claude/rules/model-roles.md",
        "A\t.claude/rules/review.md",
        "D\t.claude/rules/subagents.md",
    } <= set(changed)
    assert (rules / "model-roles.md").read_text() == "Updated model roles\n"
    assert (rules / "team.md").read_text() == "Project Claude rule\n"
    assert not (rules / "subagents.md").exists()
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert update.check_scaffold_update(target, base)


def test_project_configuration_update_commits_without_rerunning_application_checks(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source, target, _ = release
    remote = target.parent / "application-remote.git"
    git(target, "clone", "--bare", str(target), str(remote))
    git(target, "remote", "add", "origin", str(remote))
    (target / "package.json").unlink()
    commit(target, "application without task plan")
    installer = source / "setup.py"
    installer.write_text(
        installer.read_text().replace('"coverage/"', '"coverage/", "fixture-cache/"')
    )
    revision = commit(source, "configuration update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    assert revision in update.update(target)
    assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == revision
    assert "fixture-cache/" in git(target, "show", "HEAD:.gitignore")
    assert git(target, "status", "--porcelain") == ""
    assert "application-check" not in capfd.readouterr().err
    assert git(target, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_supported_update_migrates_custom_workflow_pins(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    completed_plan: str,
    shipping_policy: ShippingPolicy,
) -> None:
    source, target, _ = release
    workflow = target / ".github/workflows/hard-eng.yml"
    expected = workflow.read_text().replace("timeout-minutes: 3", "timeout-minutes: 10")
    workflow.write_text(
        expected.replace(
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5",
        )
        .replace(
            "703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0",
            "c9883cc79df532ad1a7b81bf9ab944ceb090d65c # v2.0.0",
        )
        .replace(
            expected[expected.index("on:\n") : expected.index("\n\npermissions:") + 1],
            "on:\n  push:\n    branches-ignore:\n      - 'feature/**'\n  pull_request:\n",
            1,
        )
        .replace(
            "${{ inputs.base_sha || github.event.pull_request.base.sha",
            "${{ github.event.pull_request.base.sha",
            1,
        )
    )
    (target / "package.json").unlink()
    config_path = target / "hard-eng.gates.json"
    config = json.loads(config_path.read_text())
    config["shared"][0]["command"] = ["python3", "-c", "print('application passes')"]
    config["shipping"] = shipping_policy
    config_path.write_text(json.dumps(config))
    commit(target, "custom workflow baseline")
    git(target, "branch", "-M", shipping_policy["base"])
    remote = target.parent / "workflow-remote.git"
    git(target, "clone", "--bare", str(target), str(remote))
    git(target, "remote", "add", "origin", str(remote))
    (target / "PLAN.md").write_text(completed_plan)
    commit(target, "completed update plan")
    revision = commit(source, "verified workflow migration")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    assert revision in update.update(target)
    assert workflow.read_text() == expected
    assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == revision
    assert git(target, "status", "--porcelain") == ""


def test_failed_commit_rolls_back_scaffold(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, old = release
    select_release(source, monkeypatch)
    hook = target / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\necho 'AGENTS.md is over its budget' >&2\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(
        subprocess.SubprocessError, match="AGENTS.md is over its budget"
    ):
        update.update(target)
    assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == old
    assert git(target, "status", "--porcelain") == ""


def select_release(source: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    revision = commit(source, "verified update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))


def test_development_install_does_not_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / update.SOURCE_FILE
    marker.parent.mkdir()
    marker.write_text('{"revision":null}')

    def unexpected(previous: str) -> str:
        raise AssertionError("A development install must not query upstream")

    monkeypatch.setattr(update, "latest_verified", unexpected)
    assert "uncommitted" in update.update(tmp_path)


@pytest.mark.parametrize(
    "conclusion,expected",
    [("success", True), ("failure", False), ("skipped", False), ("neutral", False)],
)
def test_only_successful_aggregate_is_a_verified_release(
    monkeypatch: pytest.MonkeyPatch, conclusion: str, expected: bool
) -> None:
    revision = "a" * 40

    def response(endpoint: str) -> object:
        assert revision in endpoint
        return {
            "check_runs": [
                {
                    "id": 1,
                    "name": "hard-eng",
                    "app": {"slug": "github-actions"},
                    "head_sha": revision,
                    "status": "completed",
                    "conclusion": conclusion,
                }
            ]
        }

    monkeypatch.setattr(update, "github_json", response)
    assert update.verified_revision(revision) is expected


def test_failed_rerun_supersedes_earlier_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "a" * 40

    def response(_endpoint: str) -> object:
        return {
            "check_runs": [
                {
                    "id": identifier,
                    "name": "hard-eng",
                    "app": {"slug": "github-actions"},
                    "head_sha": revision,
                    "status": "completed",
                    "conclusion": conclusion,
                }
                for identifier, conclusion in [(1, "success"), (2, "failure")]
            ]
        }

    monkeypatch.setattr(update, "github_json", response)
    assert update.verified_revision(revision) is False


def test_update_selection_skips_failed_newer_revision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revisions = ["a" * 40, "b" * 40, "c" * 40]

    def response(endpoint: str) -> object:
        assert "sha=main" in endpoint
        return [{"sha": revision} for revision in revisions]

    def verified(revision: str) -> bool:
        return revision == revisions[1]

    monkeypatch.setattr(update, "upstream_moved", Mock(return_value=True))
    monkeypatch.setattr(update, "github_json", response)
    monkeypatch.setattr(update, "verified_revision", verified)
    assert update.latest_verified(revisions[2]) == revisions[1]
    assert update.latest_verified(revisions[1]) is None


@pytest.mark.parametrize(
    ("answer", "walks"),
    [(304, False), ("a" * 40, False), ("b" * 40, True)],
    ids=["not-modified", "same-head", "moved"],
)
def test_freshness_walks_commits_only_after_upstream_moves(
    monkeypatch: pytest.MonkeyPatch, answer: int | str, walks: bool
) -> None:
    monkeypatch.setenv("GH_TOKEN", "fixture-token")

    def respond(request: urllib.request.Request, timeout: float) -> io.BytesIO:
        assert request.get_header("Accept") == "application/vnd.github.sha"
        assert request.get_header("If-none-match") == f'"{"a" * 40}"'
        if answer == 304:
            raise urllib.error.HTTPError(request.full_url, 304, "", Message(), None)
        return io.BytesIO(str(answer).encode())

    walk = Mock(return_value=[{"sha": "a" * 40}])
    monkeypatch.setattr(urllib.request, "urlopen", respond)
    monkeypatch.setattr(update, "github_json", walk)
    assert update.latest_verified("a" * 40) is None
    assert walk.called is walks


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("feature", {"apps/web"}),
        ("gate-config", None),
        ("unverified", None),
        ("edited-hook", None),
        ("impact", None),
    ],
)
def test_update_mixed_with_feature_work_checks_only_affected_packages(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected: set[str] | None,
) -> None:
    from gate_config import Group, changed_files, changed_packages

    source, target, _ = release
    base = git(target, "rev-parse", "HEAD")
    select_release(source, monkeypatch)
    update.update(target)
    page = target / "apps/web/page.ts"
    page.parent.mkdir(parents=True)
    page.write_text("export const page = 1;\n")
    if case == "gate-config":
        config = target / "hard-eng.gates.json"
        config.write_text(config.read_text() + "\n")
    if case == "edited-hook":
        hook = target / ".hooks/update.py"
        hook.write_text(hook.read_text() + "\n")
    commit(target, "feature work on the updated branch")
    verified = Mock(return_value=case != "unverified")
    monkeypatch.setattr(update, "verified_revision", verified)
    packages: dict[str, Group] = {
        path: {"path": path, "checks": []} for path in ("apps/web", "apps/api")
    }
    names = changed_files(target, base)
    assert names is not None
    selected = changed_packages(
        target, packages, base, names, prove_update=case != "impact"
    )
    if expected is None:
        assert isinstance(selected, str)
    else:
        assert selected == expected
    assert verified.called is (case not in {"gate-config", "impact"})


@pytest.mark.parametrize("extra", [None, "project.txt", "hard-eng.gates.json", "local"])
def test_committed_scaffold_exemption_preserves_application_boundary(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    extra: str | None,
) -> None:
    source, target, _ = release
    base = git(target, "rev-parse", "HEAD")
    select_release(source, monkeypatch)
    update.update(target)

    verified = Mock(return_value=True)
    monkeypatch.setattr(update, "verified_revision", verified)
    if extra:
        path = target / ("project.txt" if extra == "local" else extra)
        path.write_text(path.read_text() + "\n")
        if extra != "local":
            commit(target, "mixed application change")
    assert update.check_scaffold_update(target, base) is (extra is None)
    assert verified.call_count == (extra is None)
    if extra is None:
        hook = target / ".git/hooks/pre-push"
        before = hook.read_bytes()
        linked = target.parent / "linked"
        git(target, "worktree", "add", "--detach", str(linked), "HEAD")
        try:
            assert update.check_scaffold_update(linked, base)
            assert hook.read_bytes() == before
            git(linked, "config", "core.hooksPath", str(target.parent / "external"))
            with pytest.raises(subprocess.CalledProcessError):
                update.check_scaffold_update(linked, base)
            assert hook.read_bytes() == before
        finally:
            subprocess.run(
                ["git", "config", "--unset", "core.hooksPath"], cwd=target, check=False
            )
            git(target, "worktree", "remove", "--force", str(linked))


def test_unverified_scaffold_update_fails(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    base = git(target, "rev-parse", "HEAD")
    select_release(source, monkeypatch)
    update.update(target)

    def unverified(_revision: str) -> bool:
        return False

    monkeypatch.setattr(update, "verified_revision", unverified)
    with pytest.raises(ValueError, match="successful upstream"):
        update.check_scaffold_update(target, base)


def test_written_json_matches_the_project_formatter_layout(tmp_path: Path) -> None:
    fits, wraps = "a" * 46, "a" * 47
    config: JsonObject = {
        "version": 1,
        "shipping": {"base": "main", "checks": ["verify"], "ui_paths": []},
        "packages": [
            {
                "path": ".",
                "sources": ["lib"],
                "report": {},
                "checks": [
                    {"command": ["dart", fits], "name": "fits"},
                    {"command": ["dart", wraps], "name": "wraps"},
                ],
            }
        ],
    }
    prettier = f"""{{
  "version": 1,
  "shipping": {{
    "base": "main",
    "checks": ["verify"],
    "ui_paths": []
  }},
  "packages": [
    {{
      "path": ".",
      "sources": ["lib"],
      "report": {{}},
      "checks": [
        {{
          "command": ["dart", "{fits}"],
          "name": "fits"
        }},
        {{
          "command": [
            "dart",
            "{wraps}"
          ],
          "name": "wraps"
        }}
      ]
    }}
  ]
}}
"""
    assert json_file(tmp_path, config) == prettier
    (tmp_path / "biome.json").write_text("{}\n")
    assert json_file(tmp_path, config) == re.sub(
        "(?m)^(?:  )+", lambda indent: "\t" * (len(indent[0]) // 2), prettier
    )


def test_retired_families_config_is_regenerated_and_reported(
    installer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    setup_repository(tmp_path)
    secrets = installer.gate_config(tmp_path)["shared"][0]["command"]
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "families": {
                    "lint": ["node_modules/.bin/biome", "lint", "."],
                    "contract": ["python3", "scripts/contract.py"],
                    "skills": ["python3", "scripts/check-skill-contracts.py"],
                    "inline": ["python3", "-c", "print(1)"],
                    "flagged": ["python3", "-u", "-W", "error", "scripts/gone.py"],
                    "audit": ["node_modules/.bin/fallow", "audit", "--format", "json"],
                    "removed": ["node_modules/.bin/pnpm", "--dir", "gone", "run", "x"],
                    "secrets": secrets,
                },
                "phases": {"push": ["lint", "contract", "audit", "removed"]},
            }
        )
    )
    for tool in (
        "node_modules/.bin/fallow",
        "node_modules/.bin/pnpm",
        "scripts/contract.py",
    ):
        (tmp_path / tool).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / tool).touch()
    installer.install(tmp_path)
    notice = capsys.readouterr().err
    assert "skills (script not found)" in notice and "inline (" not in notice
    assert "flagged (script not found)" in notice
    assert "lint (program not found): ['node_modules/.bin/biome'" in notice
    assert "audit (Fallow audit gates require a native fallow report" in notice
    assert "removed ([Errno 2] No such file or directory" in notice
    written = (tmp_path / "hard-eng.gates.json").read_text()
    config = json.loads(written)
    assert written == json_file(tmp_path, config)
    assert "families" not in config and "phases" not in config
    assert [package["language"] for package in config["packages"]] == ["javascript"]
    assert [gate["command"] for gate in config["shared"]].count(secrets) == 1
    assert {
        "name": "legacy-contract",
        "command": ["python3", "scripts/contract.py"],
    } in (config["shared"])
    assert ["python3", "-c", "print(1)"] in [
        gate["command"] for gate in config["shared"]
    ]
    before = snapshot(tmp_path)
    installer.install(tmp_path)
    assert "Regenerated" not in capsys.readouterr().err
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    ("command", "script"),
    [
        (["node", "--require", "setup.js", "scripts/gone.mjs"], "scripts/gone.mjs"),
        (["node", "--eval", "process.exit(0)"], None),
        (["python3", "-m", "pytest"], None),
        (["bash", "-o", "pipefail", "--", "scripts/check.sh"], "scripts/check.sh"),
    ],
)
def test_retired_interpreter_script_is_found_past_options(
    installer: ModuleType, command: list[str], script: str | None
) -> None:
    assert installer.script_operand(command) == script


REACT_DOCTOR_0_9_14_COMMAND_INPUT_RISK = re.compile(
    r"(?:(?<![.\w$])(?:exec(?:Sync)?|system|passthru|proc_open|shell_exec)"
    r"|\b(?:os\.system|subprocess\.(?:run|Popen|call)"
    r"|(?:child_process|childProcess|cp)\.exec\w*))\s*\([^)]{0,220}"
    r"(?:req\.|request\.|params\.|query\.|body\.|searchParams|\$_(?:GET|POST|REQUEST)"
    r"|shell\s*=\s*true|f['\"`][^'\"`]*\{)",
    re.IGNORECASE,
)


def test_installed_hooks_pass_react_doctor_command_input_rule() -> None:
    findings = [
        f"{path.relative_to(SOURCE)}:{source.count(chr(10), 0, match.start()) + 1}"
        for path in sorted((SOURCE / ".hooks").rglob("*.py"))
        for source in [path.read_text()]
        for match in REACT_DOCTOR_0_9_14_COMMAND_INPUT_RISK.finditer(source)
    ]
    assert findings == []
