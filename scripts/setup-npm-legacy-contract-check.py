#!/usr/bin/env python3

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup npm legacy contract: FAIL: {message}")


def runtime_digest(path: Path) -> str:
    result = subprocess.run(
        ["python3", str(ROOT / "scripts/runtime-tree-digest.py"), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        fail(result.stderr.strip() or "could not digest activated runtime")
    return result.stdout.strip()


def managed_commands() -> tuple[str, ...]:
    result = subprocess.run(
        [str(ROOT / "scripts/setup/manifest.py"), "npm-specs"], capture_output=True, text=True, check=False
    )
    if result.returncode:
        fail(result.stderr.strip() or "could not read managed npm commands")
    return tuple(spec.rsplit("@", 1)[0] for spec in result.stdout.split())


def activate(home: Path, staged: Path) -> subprocess.CompletedProcess[str]:
    script = (
        "set -eu\n"
        f"ROOT={shlex.quote(str(ROOT))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/common.sh'))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/binaries.sh'))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/npm-runtime.sh'))}\n"
        f"activate_npm_runtime {shlex.quote(str(staged))}\n"
    )
    env = os.environ.copy()
    env["HOME"] = str(home)
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False, env=env)


def arrange_runtime(home: Path, owner_name: str) -> tuple[Path, Path]:
    asset_dir = home / ".local/share/hard-eng"
    runtime = asset_dir / "npm-runtime"
    staged = asset_dir / ".hard-eng-npm-stage.test"
    bin_dir = home / ".local/bin"
    runtime.mkdir(parents=True)
    staged.mkdir()
    bin_dir.mkdir(parents=True)
    (runtime / "package.json").write_text(json.dumps({"name": owner_name}) + "\n", encoding="utf-8")
    (runtime / "legacy").write_text("previous\n", encoding="utf-8")
    (staged / "owner").write_text("replacement\n", encoding="utf-8")
    for name in managed_commands():
        target = runtime / "node_modules/.bin" / name
        (bin_dir / name).symlink_to(target)
    return runtime, staged


def check_canonical_legacy_adoption() -> None:
    canonical_name = json.loads((ROOT / "runtime/npm/package.json").read_text(encoding="utf-8"))["name"]
    with tempfile.TemporaryDirectory(prefix="hard-eng-npm-legacy-") as temporary:
        home = Path(temporary)
        runtime, staged = arrange_runtime(home, canonical_name)
        result = activate(home, staged)
        if result.returncode:
            fail(result.stderr.strip() or "canonical legacy runtime was not adopted")
        if not (runtime / "owner").is_file() or (runtime / "legacy").exists():
            fail("canonical legacy runtime was not replaced transactionally")
        receipt = home / ".local/share/hard-eng/state/npm-runtime.sha256"
        if not receipt.is_file() or receipt.read_text(encoding="ascii").strip() != runtime_digest(runtime):
            fail("canonical legacy adoption receipt does not match the active runtime")


def check_lookalike_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-npm-lookalike-") as temporary:
        home = Path(temporary)
        runtime, staged = arrange_runtime(home, "unrelated-runtime")
        result = activate(home, staged)
        if result.returncode == 0:
            fail("lookalike runtime was adopted")
        if (runtime / "legacy").read_text(encoding="utf-8") != "previous\n":
            fail("lookalike runtime changed after rejected adoption")
        if not staged.is_dir():
            fail("staged runtime changed after rejected adoption")


def main() -> int:
    check_canonical_legacy_adoption()
    check_lookalike_rejected()
    print("setup npm legacy contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
