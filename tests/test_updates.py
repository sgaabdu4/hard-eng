"""Real Git update transactions preserve local work and obey check scope."""

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import update

SOURCE = Path(__file__).resolve().parents[1]


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


@pytest.fixture
def release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, str]:
    source, target = tmp_path / "source", tmp_path / "target"
    init(source)
    for name in (".hooks", ".agents", ".github"):
        shutil.copytree(
            SOURCE / name, source / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in (
        "setup.py",
        "setup.sh",
        "AGENTS.md",
        "PRODUCT.md",
        "DESIGN.md",
        ".gitignore",
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


def test_shell_bootstrap_installs_from_main(release: tuple[Path, Path, str]) -> None:
    source, target, _ = release
    git(source, "branch", "-M", "main")
    result = subprocess.run(
        ["sh", str(source / "setup.sh")],
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
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
    assert "SOURCE_CHECK" in capfd.readouterr().err
    assert git(target, "worktree", "list", "--porcelain").count("worktree ") == 1


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
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, old = release
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
