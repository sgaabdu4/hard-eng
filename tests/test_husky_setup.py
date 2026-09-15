"""Exercise Husky shell dispatch, canonical migration and custom-hook safety."""

import json
import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
import update
from conftest import commit, git, init


def test_husky_update_preserves_shim_and_runs_shell_launcher(
    installer: ModuleType, tmp_path: Path
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _, old_launcher = installer.prepare_hook(tmp_path)
    shim = tmp_path / ".husky/_/pre-push"
    shim.parent.mkdir(parents=True)
    shim.write_text('#!/usr/bin/env sh\n. "$(dirname "$0")/h"')
    dispatcher = shim.parent / "h"
    dispatcher.write_text(
        'n=$(basename "$0")\ns=$(dirname "$(dirname "$0")")/$n\nsh -e "$s" "$@"\n'
    )
    target = tmp_path / ".husky/pre-push"
    target.write_text(old_launcher)
    subprocess.run(
        ["git", "config", "core.hooksPath", ".husky/_"], cwd=tmp_path, check=True
    )
    hook, launcher = installer.prepare_hook(tmp_path)
    assert hook == target
    hook.write_text(launcher)
    assert installer.prepare_hook(tmp_path) == (hook, launcher)
    verifier = tmp_path / ".hooks/hard-eng.py"
    verifier.parent.mkdir()
    verifier.write_text(
        "import sys\nassert sys.argv[1:] == ['pre-push']\n"
        "assert sys.stdin.read() == 'native push input\\n'\nsys.exit(17)\n"
    )
    result = subprocess.run(
        ["sh", str(shim)],
        cwd=tmp_path,
        input="native push input\n",
        text=True,
        check=False,
    )
    assert result.returncode == 17
    assert shim.read_text() == '#!/usr/bin/env sh\n. "$(dirname "$0")/h"'
    assert (
        subprocess.check_output(
            ["git", "config", "core.hooksPath"], cwd=tmp_path, text=True
        ).strip()
        == ".husky/_"
    )
    target.write_text("#!/bin/sh\necho custom\n")
    with pytest.raises(ValueError, match="Existing pre-push hook must be preserved"):
        installer.prepare_hook(tmp_path)
    target.unlink()
    shim.write_text("#!/bin/sh\necho custom shim\n")
    with pytest.raises(ValueError, match="Existing pre-push hook must be preserved"):
        installer.prepare_hook(tmp_path)


@pytest.mark.parametrize("installed", [False, True])
def test_shell_bootstrap_installs_verified_main(
    release: tuple[Path, Path, str], installed: bool
) -> None:
    source, target, _ = release
    git(source, "branch", "-M", "main")
    module = source / ".hooks/update.py"
    module.write_text(
        module.read_text()
        + '\nlatest_verified = lambda previous: subprocess.check_output(["git", "-C", str(Path(__file__).resolve().parents[1]), "rev-parse", "HEAD"], text=True).strip()\n'
    )
    revision = commit(source, "verified fixture update")
    module.write_text(
        module.read_text()
        + f'\nlatest_verified = lambda previous: "{revision}"\ndef update(root): raise AssertionError("Unverified updater executed")\n'
    )
    commit(source, "unverified newer source")
    if installed:
        (target / "project.txt").write_text("preserved local work\n")
    else:
        target = target.parent / "fresh"
        init(target)
        (target / "package.json").write_text('{"private":true}')
        (target / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
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
    else:
        assert "Installed Hard Eng" in result.stdout
    metadata = json.loads((target / update.SOURCE_FILE).read_text())
    assert metadata["revision"] == revision
    assert (target / ".git/hooks/pre-push").stat().st_mode & 0o111
    assert (target / ".github/workflows/hard-eng.yml").is_file() is installed
    if not installed:
        assert "CI setup pending" in result.stderr


def test_shell_bootstrap_current_clone_installs_missing_pre_push(
    release: tuple[Path, Path, str],
) -> None:
    source, target, _ = release
    git(source, "branch", "-M", "main")
    module = source / ".hooks/update.py"
    module.write_text(
        module.read_text()
        + "\ndef latest_verified(previous):\n"
        + "    if previous:\n"
        + "        return None\n"
        + "    return subprocess.check_output(\n"
        + "        ['git', 'rev-parse', 'HEAD'],\n"
        + "        cwd=Path(__file__).resolve().parents[1],\n"
        + "        text=True,\n"
        + "    ).strip()\n"
    )
    revision = commit(source, "current verified source")
    shutil.copyfile(module, target / ".hooks/update.py")
    shutil.copyfile(
        source / ".agents/skills/he/references/workflow.md",
        target / ".agents/skills/he/references/workflow.md",
    )
    (target / update.SOURCE_FILE).write_text(json.dumps({"revision": revision}) + "\n")
    commit(target, "current installed source")
    fresh = target.parent / "fresh"
    subprocess.run(["git", "clone", "--quiet", str(target), str(fresh)], check=True)
    hook = fresh / ".git/hooks/pre-push"
    assert not hook.exists()

    result = subprocess.run(
        ["sh", str(source / "setup.sh")],
        cwd=fresh,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "No newer CI-verified Hard Eng revision is available" in result.stdout
    assert "installed the missing pre-push hook" in result.stdout
    assert hook.stat().st_mode & 0o111
    assert 'hard-eng.py", "pre-push"' in hook.read_text()
    assert git(fresh, "rev-parse", "HEAD") == git(target, "rev-parse", "HEAD")
