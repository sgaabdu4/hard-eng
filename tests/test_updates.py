"""Real Git update transactions preserve local work and obey check scope."""

import json
import shutil
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
import update
from shipping import ShippingError, ShippingPolicy

SOURCE = Path(__file__).resolve().parents[1]


def test_installer_preserves_native_mcp_settings_on_rerun(
    installer: ModuleType, tmp_path: Path
) -> None:
    git(tmp_path, "init", "-q")
    settings = {
        "command": "codebase-memory-mcp",
        "args": ["--project", "fitness"],
        "env": {"PROJECT_MODE": "local"},
        "enabled": False,
    }
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"codebase-memory-mcp": settings}})
    )
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex/config.toml").write_text(
        '[mcp_servers.codebase-memory-mcp]\ncommand = "codebase-memory-mcp"\n'
        'args = ["--project", "fitness"]\nenabled = false\n'
        '[mcp_servers.codebase-memory-mcp.env]\nPROJECT_MODE = "local"\n'
    )
    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)
    assert (
        json.loads(changes[".mcp.json"])["mcpServers"]["codebase-memory-mcp"]
        == settings
    )
    servers = tomllib.loads(changes[".codex/config.toml"])["mcp_servers"]
    assert servers["codebase-memory-mcp"] == settings
    assert servers["context-mode"]["command"] == "pnpm"
    for name, content in changes.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    repeated: dict[str, str] = {}
    installer.configure_mcp(tmp_path, repeated)
    assert repeated == changes


def test_uninitialized_skill_submodule_cannot_be_silently_omitted(
    tmp_path: Path,
) -> None:
    skills = tmp_path / ".agents/skills"
    skills.mkdir(parents=True)
    (skills / "canonical").symlink_to("../skill-sources/canonical/skills/canonical")
    with pytest.raises(ValueError, match="submodule update"):
        update.scaffold_files(tmp_path)


def fixed_revision(revision: str) -> Callable[[str], str]:
    def selected(_previous: str) -> str:
        return revision

    return selected


def git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", *arguments], cwd=root, text=True).strip()


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def init(root: Path) -> None:
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")


def test_update_fetches_each_revisions_pinned_skill_submodule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical, upstream = tmp_path / "canonical", tmp_path / "upstream"
    init(canonical)
    skill = canonical / "skills/canonical/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("first revision\n")
    commit(canonical, "first skill")
    init(upstream)
    git(
        upstream,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(canonical),
        ".agents/skill-sources/canonical",
    )
    link = upstream / ".agents/skills/canonical"
    link.parent.mkdir()
    link.symlink_to("../skill-sources/canonical/skills/canonical")
    previous = commit(upstream, "first pin")
    skill.write_text("second revision\n")
    revision = commit(canonical, "second skill")
    module = upstream / ".agents/skill-sources/canonical"
    git(module, "fetch", "origin")
    git(module, "checkout", "--detach", revision)
    current = commit(upstream, "second pin")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{upstream.as_uri()}.insteadOf")
    monkeypatch.setenv(
        "GIT_CONFIG_VALUE_0", f"https://github.com/{update.UPSTREAM}.git"
    )
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "protocol.file.allow")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "always")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    source, old = update.fetch_sources(checkout, current, previous)
    name = ".agents/skills/canonical/SKILL.md"
    assert (source / name).read_text() == "second revision\n"
    assert (old / name).read_text() == "first revision\n"
    assert name in update.scaffold_files(source)


@pytest.fixture
def release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    source, target = tmp_path / "source", tmp_path / "target"
    init(source)
    for name in (".hooks", ".agents", ".github"):
        shutil.copytree(
            SOURCE / name,
            source / name,
            ignore=shutil.ignore_patterns("__pycache__", "skill-sources"),
        )
    for name in (
        "setup.py",
        "setup.sh",
        "AGENTS.md",
        "PRODUCT.md",
        "DESIGN.md",
        ".gitignore",
        "pyproject.toml",
        "uv.lock",
    ):
        shutil.copyfile(SOURCE / name, source / name)
    (source / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [
                    {
                        "name": "source-check",
                        "command": ["python3", "-c", "print('SOURCE_CHECK')"],
                    }
                ],
            }
        )
    )
    old = commit(source, "source baseline")
    init(target)
    (target / "package.json").write_text('{"private":true}')
    (target / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    subprocess.run(
        ["python3", str(source / "setup.py"), str(target)],
        check=True,
        capture_output=True,
    )
    for name in ("PRODUCT.md", "DESIGN.md"):
        shutil.copyfile(SOURCE / name, target / name)
    (target / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [
                    {
                        "name": "application-check",
                        "command": ["python3", "-c", "raise SystemExit(1)"],
                    },
                    {
                        "name": "actionlint",
                        "role": "workflows",
                        "command": ["python3", "-c", "print('WORKFLOW_CHECK')"],
                    },
                    {
                        "name": "zizmor",
                        "role": "ci-security",
                        "command": ["python3", "-c", "print('CI_SECURITY_CHECK')"],
                    },
                ],
            }
        )
    )
    (target / "project.txt").write_text("original\n")
    commit(target, "installed baseline")
    reference = source / ".agents/skills/he/references/workflow.md"
    reference.write_text(reference.read_text() + "\nUpdated fixture instruction.\n")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", f"url.{source.as_uri()}.insteadOf")
    monkeypatch.setenv(
        "GIT_CONFIG_VALUE_0", f"https://github.com/{update.UPSTREAM}.git"
    )
    return source, target, old


@pytest.mark.parametrize("installed", [False, True])
def test_shell_bootstrap_installs_from_main(
    release: tuple[Path, Path, str], installed: bool
) -> None:
    source, target, _ = release
    git(source, "branch", "-M", "main")
    if installed:
        # Control release discovery only; the shell and update transaction are real.
        module = source / ".hooks/update.py"
        module.write_text(
            module.read_text()
            + '\nlatest_verified = lambda previous: subprocess.check_output(["git", "-C", str(Path(__file__).resolve().parents[1]), "rev-parse", "HEAD"], text=True).strip()\n'
        )
        commit(source, "verified fixture update")
        (target / "project.txt").write_text("preserved local work\n")
    else:
        target = target.parent / "fresh"
        init(target)
        (target / "package.json").write_text('{"private":true}')
        (target / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    revision = git(source, "rev-parse", "HEAD")
    result = subprocess.run(
        ["sh", str(source / "setup.sh")],
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
    if installed:
        assert f"Updated Hard Eng to {revision}" in result.stdout
        assert (target / "project.txt").read_text() == "preserved local work\n"
        metadata = json.loads((target / update.SOURCE_FILE).read_text())
        assert metadata["revision"] == revision
    else:
        assert "Installed Hard Eng" in result.stdout
    assert (target / ".git/hooks/pre-push").stat().st_mode & 0o111
    assert (target / ".github/workflows/hard-eng.yml").is_file()


def test_update_commits_only_scaffold_and_preserves_index(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source, target, _ = release
    revision = commit(source, "verified update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
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
    assert changed == {update.SOURCE_FILE, ".agents/skills/he/references/workflow.md"}
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
        with pytest.raises(subprocess.CalledProcessError):
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


def test_project_configuration_update_runs_application_checks(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source, target, old = release
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
    with pytest.raises(subprocess.CalledProcessError):
        update.update(target)
    assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == old
    assert "fixture-cache/" not in (target / ".gitignore").read_text()
    assert git(target, "status", "--porcelain") == ""
    assert "FAIL application-check" in capfd.readouterr().err


@pytest.mark.parametrize(
    "outcome",
    ["Draft", "Ready", "Complete", "absent", "application-failure", "missing-base"],
)
@pytest.mark.parametrize("configured_base", [True, False])
def test_candidate_uses_remote_task_plan_scope(
    release: tuple[Path, Path, str],
    completed_plan: str,
    outcome: str,
    configured_base: bool,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source, target, _ = release
    commit(source, "verified source candidate")
    (target / "package.json").unlink()
    config_path = target / "hard-eng.gates.json"
    config = json.loads(config_path.read_text())
    policy: ShippingPolicy = {
        "base": "main",
        "checks": ["fixture"],
        "ui_paths": [],
        "ci_seconds": 180,
        "pre_push_seconds": 180,
        "delivery": [],
    }
    config["shipping"] = policy
    if not configured_base:
        del config["shipping"]
    command = (
        "import subprocess; print('APPLICATION_SCOPE_CHECK'); "
        "staged=subprocess.check_output(['git','diff','--cached','--name-status'],text=True); "
        "assert 'A\\tnew-managed.mjs' in staged; "
        "assert 'D\\tremoved.txt' in staged; "
        "assert 'M\\tproject.txt' in staged; "
        "assert 'A\\tnew-link' in staged; raise SystemExit(0)"
    )
    if outcome == "application-failure":
        command = command.replace("SystemExit(0)", "SystemExit(1)")
    config["shared"][0]["command"] = ["python3", "-c", command]
    config_path.write_text(json.dumps(config))
    (target / "removed.txt").write_text("old managed content\n")
    git(target, "branch", "-M", "main")
    commit(target, "remote baseline")
    remote = target.parent / "remote.git"
    git(target, "clone", "--bare", str(target), str(remote))
    if configured_base:
        git(remote, "branch", "default", "HEAD^")
        git(remote, "symbolic-ref", "HEAD", "refs/heads/default")
    git(target, "remote", "add", "origin", str(remote))
    git(target, "switch", "-c", "feature/update")
    plan = target / "features/current/PLAN.md"
    if outcome != "absent":
        plan.parent.mkdir(parents=True)
        status = outcome if outcome in ("Draft", "Ready") else "Complete"
        plan.write_text(completed_plan.replace("Status: Complete", f"Status: {status}"))
        commit(target, "task plan")
    git(target, "update-ref", "refs/remotes/origin/main", "HEAD")
    stale = git(target, "rev-parse", "origin/main")
    (target / "project.txt").write_text("unrelated local edit\n")
    if outcome == "missing-base":
        git(remote, "update-ref", "-d", "refs/heads/main")
    candidate = target.parent / "candidate"
    changes: dict[str, str | None] = {
        "project.txt": "candidate update\n",
        "new-managed.mjs": "export const value = 1;\n",
        "removed.txt": None,
    }
    links: dict[str, str | None] = {"new-link": "project.txt"}
    (target / "unrelated.txt").write_text("staged local work\n")
    git(target, "add", "unrelated.txt")
    if outcome not in {"application-failure", "missing-base"}:
        update.verify_candidate(target, source, changes, links, candidate)
    else:
        error = (
            ShippingError
            if outcome == "missing-base"
            else subprocess.CalledProcessError
        )
        with pytest.raises(error):
            update.verify_candidate(target, source, changes, links, candidate)
    assert {
        "working": (target / "project.txt").read_text(),
        "index": git(target, "diff", "--cached", "--name-only"),
        "new_file": (target / "new-managed.mjs").exists(),
        "new_link": (target / "new-link").is_symlink(),
        "removed": (target / "removed.txt").read_text(),
        "tracking": git(target, "rev-parse", "origin/main"),
    } == {
        "working": "unrelated local edit\n",
        "index": "unrelated.txt",
        "new_file": False,
        "new_link": False,
        "removed": "old managed content\n",
        "tracking": stale,
    }
    assert not candidate.exists()
    if outcome != "missing-base":
        assert "APPLICATION_SCOPE_CHECK" in capfd.readouterr().err


def test_supported_update_migrates_custom_workflow_pins(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    completed_plan: str,
) -> None:
    source, target, _ = release
    workflow = target / ".github/workflows/hard-eng.yml"
    expected = workflow.read_text().replace("timeout-minutes: 3", "timeout-minutes: 10")
    workflow.write_text(
        expected.replace(
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5",
        ).replace(
            "703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0",
            "c9883cc79df532ad1a7b81bf9ab944ceb090d65c # v2.0.0",
        )
    )
    (target / "package.json").unlink()
    config_path = target / "hard-eng.gates.json"
    config = json.loads(config_path.read_text())
    config["shared"][0]["command"] = ["python3", "-c", "print('application passes')"]
    config_path.write_text(json.dumps(config))
    commit(target, "custom workflow baseline")
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
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(subprocess.CalledProcessError):
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

    monkeypatch.setattr(update, "github_json", response)
    monkeypatch.setattr(update, "verified_revision", verified)
    assert update.latest_verified(revisions[2]) == revisions[1]
    assert update.latest_verified(revisions[1]) is None


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

    def verified(_revision: str) -> bool:
        return True

    monkeypatch.setattr(update, "verified_revision", verified)
    if extra:
        path = target / ("project.txt" if extra == "local" else extra)
        path.write_text(path.read_text() + "\n")
        if extra != "local":
            commit(target, "mixed application change")
    assert update.check_scaffold_update(target, base) is (extra is None)
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
