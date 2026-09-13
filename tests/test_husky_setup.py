"""Exercise Husky shell dispatch, canonical migration and custom-hook safety."""

import subprocess
from pathlib import Path
from types import ModuleType

import pytest


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
