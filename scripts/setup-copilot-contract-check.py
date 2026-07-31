#!/usr/bin/env python3
"""Behavior contracts for global Copilot instruction discovery."""

from __future__ import annotations

import os
import shutil
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = "# >>> hard-eng managed Copilot instructions >>>"
END = "# <<< hard-eng managed Copilot instructions <<<"
VARIABLE = "COPILOT_CUSTOM_INSTRUCTIONS_DIRS"


def fail(message: str) -> None:
    raise SystemExit(f"setup-copilot-contract: FAIL: {message}")


def run_owner(
    home: Path,
    mode: str,
    shell: str,
    *,
    xdg: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "SHELL": f"/bin/{shell}",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if xdg is None:
        env.pop("XDG_CONFIG_HOME", None)
    else:
        env["XDG_CONFIG_HOME"] = str(xdg)
    script = (
        "set -eu\n"
        f"ROOT={shlex.quote(str(ROOT))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/common.sh'))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/copilot.sh'))}\n"
        f"{mode}_copilot_integration\n"
    )
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def prepare_home(home: Path) -> tuple[Path, dict[Path, bytes]]:
    os.symlink(ROOT, home / ".agents")
    (home / ".copilot").mkdir()
    xdg = home / "xdg"
    originals = {
        home / ".bash_profile": b"export BASH_PROFILE_SETTING=keep\n",
        home / ".bashrc": b"export BASHRC_SETTING=keep\n",
        home / ".zshenv": b"export ZSHENV_SETTING=keep\n",
        home / ".zprofile": b"export ZPROFILE_SETTING=keep\n",
        home / ".zshrc": b"export ZSHRC_SETTING=keep\n",
        xdg / "fish/config.fish": b"set -gx FISH_SETTING keep\n",
    }
    for path, content in originals.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (home / ".zshrc").chmod(0o640)
    return xdg, originals


def target_profiles(home: Path, xdg: Path) -> tuple[Path, ...]:
    return (
        home / ".bash_profile",
        home / ".bashrc",
        home / ".zshenv",
        home / ".zprofile",
        home / ".zshrc",
        xdg / "fish/config.fish",
    )


def check_rendered(home: Path, xdg: Path, originals: dict[Path, bytes]) -> None:
    for path in target_profiles(home, xdg):
        content = path.read_text(encoding="utf-8")
        if content.count(START) != 1 or content.count(END) != 1:
            fail(f"Copilot markers missing or duplicated: {path}")
        expected = (
            f'set -gx {VARIABLE} "$HOME/.agents"\n'
            if path.name == "config.fish"
            else f'export {VARIABLE}="$HOME/.agents"\n'
        )
        if expected not in content or originals[path].decode() not in content:
            fail(f"Copilot block changed user content or has the wrong export: {path}")
    if (home / ".zshrc").stat().st_mode & 0o777 != 0o640:
        fail("Copilot convergence changed an existing profile mode")


def check_interpreters(home: Path, xdg: Path) -> None:
    bash_profile = home / ".bash_profile"
    bash = subprocess.run(
        ["bash", "-c", ". \"$1\"; printf '%s' \"$COPILOT_CUSTOM_INSTRUCTIONS_DIRS\"", "--", str(bash_profile)],
        capture_output=True,
        text=True,
        check=False,
        env={"HOME": str(home), "PATH": os.environ["PATH"]},
    )
    if bash.returncode or bash.stdout != str(home / ".agents"):
        fail("Bash did not resolve the canonical Copilot instructions directory")

    zsh = shutil.which("zsh")
    if zsh is not None:
        sourced = subprocess.run(
            [zsh, "-c", ". \"$1\"; printf '%s' \"$COPILOT_CUSTOM_INSTRUCTIONS_DIRS\"", "--", str(home / ".zshrc")],
            capture_output=True,
            text=True,
            check=False,
            env={"HOME": str(home), "PATH": os.environ["PATH"]},
        )
        if sourced.returncode or sourced.stdout != str(home / ".agents"):
            fail("Zsh did not resolve the canonical Copilot instructions directory")

    fish = shutil.which("fish")
    if fish is not None:
        sourced = subprocess.run(
            [fish, "-c", "source $argv[1]; printf '%s' $COPILOT_CUSTOM_INSTRUCTIONS_DIRS", "--", str(xdg / "fish/config.fish")],
            capture_output=True,
            text=True,
            check=False,
            env={"HOME": str(home), "PATH": os.environ["PATH"]},
        )
        if sourced.returncode or sourced.stdout != str(home / ".agents"):
            fail("Fish did not resolve the canonical Copilot instructions directory")


def check_convergence() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        first = run_owner(home, "install", "fish", xdg=xdg)
        if first.returncode:
            fail(first.stderr.strip() or "Copilot profile convergence failed")
        check_rendered(home, xdg, originals)
        check_interpreters(home, xdg)
        before = {path: path.read_bytes() for path in target_profiles(home, xdg)}
        modes = {path: path.stat().st_mode & 0o777 for path in target_profiles(home, xdg)}
        second = run_owner(home, "install", "fish", xdg=xdg)
        checked = run_owner(home, "check", "fish", xdg=xdg)
        after = {path: path.read_bytes() for path in target_profiles(home, xdg)}
        if second.returncode or checked.returncode or after != before:
            fail("Copilot rerun/check did not preserve converged profile bytes")
        if {path: path.stat().st_mode & 0o777 for path in target_profiles(home, xdg)} != modes:
            fail("Copilot rerun/check changed profile modes")


def check_skip_without_copilot() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-skip-") as temporary:
        home = Path(temporary)
        os.symlink(ROOT, home / ".agents")
        result = run_owner(home, "install", "bash")
        checked = run_owner(home, "check", "bash")
        if result.returncode or checked.returncode:
            fail("Copilot owner did not skip a home without .copilot")
        if any((home / name).exists() for name in (".bash_profile", ".bashrc", ".zshenv", ".zprofile", ".zshrc")):
            fail("Copilot skip created shell profiles")


def check_check_is_read_only() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-check-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        for path in target_profiles(home, xdg):
            path.unlink()
        result = run_owner(home, "check", "bash", xdg=xdg)
        if result.returncode == 0 or any(path.exists() for path in target_profiles(home, xdg)):
            fail("Copilot check mutated or accepted missing profiles")


def check_conflicts() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-conflict-") as temporary:
        home = Path(temporary)
        os.symlink(ROOT, home / ".agents")
        (home / ".copilot").mkdir()
        profile = home / ".zshrc"
        original = f'export {VARIABLE}="$HOME/other"\n'
        profile.write_text(original, encoding="utf-8")
        result = run_owner(home, "install", "zsh")
        if result.returncode == 0 or profile.read_text(encoding="utf-8") != original:
            fail("foreign Copilot export was overwritten")
        if any((home / name).exists() for name in (".bash_profile", ".bashrc", ".zshenv", ".zprofile")):
            fail("Copilot conflict caused partial profile creation")

    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-malformed-") as temporary:
        home = Path(temporary)
        os.symlink(ROOT, home / ".agents")
        (home / ".copilot").mkdir()
        profile = home / ".bash_profile"
        original = f"keep\n{START}\nunclosed\n"
        profile.write_text(original, encoding="utf-8")
        result = run_owner(home, "install", "bash")
        if result.returncode == 0 or profile.read_text(encoding="utf-8") != original:
            fail("malformed Copilot block was overwritten")


def check_lock_conflict() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-lock-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        lock = home / ".local/share/hard-eng/.copilot-profile.lock"
        lock.mkdir(parents=True)
        before = {path: path.read_bytes() for path in target_profiles(home, xdg)}
        result = run_owner(home, "install", "fish", xdg=xdg)
        after = {path: path.read_bytes() for path in target_profiles(home, xdg)}
        if result.returncode == 0 or after != before:
            fail("active Copilot convergence lock was ignored or caused mutation")


def main() -> int:
    check_convergence()
    check_skip_without_copilot()
    check_check_is_read_only()
    check_conflicts()
    check_lock_conflict()
    print("setup-copilot-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
