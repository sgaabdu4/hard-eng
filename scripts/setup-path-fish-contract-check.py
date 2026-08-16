#!/usr/bin/env python3
"""Behavior contract for native Fish PATH convergence."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
PATH_OWNER = ROOT / "scripts/setup/path.sh"
START = "# >>> hard-eng managed PATH >>>"
END = "# <<< hard-eng managed PATH <<<"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-path-fish-contract: FAIL: {message}")


def run_path(home: Path, mode: str, *, xdg: str | None) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "SHELL": "/usr/bin/fish",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if xdg is None:
        env.pop("XDG_CONFIG_HOME", None)
    else:
        env["XDG_CONFIG_HOME"] = xdg
    return subprocess.run(
        ["bash", str(PATH_OWNER), mode],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def check_xdg_convergence() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-fish-path-") as temporary:
        home = Path(temporary)
        config_root = home / "xdg"
        profile = config_root / "fish/config.fish"
        profile.parent.mkdir(parents=True)
        original = "set -gx USER_SETTING keep\n"
        profile.write_text(original, encoding="utf-8")
        profile.chmod(0o640)

        first = run_path(home, "install", xdg=str(config_root))
        if first.returncode:
            fail(first.stderr.strip() or "Fish PATH install failed")
        content = profile.read_text(encoding="utf-8")
        managed_line = (
            'set -gx PATH "$HOME/.local/bin" '
            '(string match -v -- "$HOME/.local/bin" $PATH)'
        )
        if (
            original not in content
            or content.count(START) != 1
            or content.count(END) != 1
            or managed_line not in content
        ):
            fail("Fish PATH block is missing, duplicated, or not shell-native")
        if stat.S_IMODE(profile.stat().st_mode) != 0o640:
            fail("Fish PATH install changed profile mode")

        before = profile.read_bytes()
        rerun = run_path(home, "install", xdg=str(config_root))
        checked = run_path(home, "check", xdg=str(config_root))
        if rerun.returncode or checked.returncode or profile.read_bytes() != before:
            fail("Fish rerun/check did not preserve converged bytes")

        fish = shutil.which("fish")
        if fish is not None:
            managed = str(home / ".local/bin")
            platform_bin = str(home / "platform/bin")
            vendor_root = home / "vendor"
            vendor_config = vendor_root / "fish/vendor_conf.d/10-platform-path.fish"
            vendor_config.parent.mkdir(parents=True)
            vendor_config.write_text(
                f'set -gx PATH "{platform_bin}" $PATH\n', encoding="utf-8"
            )
            live = subprocess.run(
                [fish, "-c", "string join : $PATH"],
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "XDG_CONFIG_HOME": str(config_root),
                    "XDG_DATA_DIRS": str(vendor_root),
                    "PATH": f"/usr/bin:{managed}:/bin:{managed}",
                },
            )
            entries = live.stdout.strip().split(":")
            if (
                live.returncode
                or not entries
                or entries[0] != managed
                or entries.count(managed) != 1
                or platform_bin not in entries
                or "/usr/bin" not in entries
            ):
                fail(
                    "Fish did not keep the managed bin first exactly once while "
                    "preserving platform PATH entries"
                )


def check_default_and_invalid_xdg() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-fish-default-") as temporary:
        home = Path(temporary)
        installed = run_path(home, "install", xdg=None)
        if installed.returncode or not (home / ".config/fish/config.fish").is_file():
            fail("Fish default config owner was not converged")
        rejected = run_path(home, "preflight", xdg="relative/config")
        if rejected.returncode == 0:
            fail("relative XDG_CONFIG_HOME was accepted")


def main() -> int:
    check_xdg_convergence()
    check_default_and_invalid_xdg()
    print("setup-path-fish-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
