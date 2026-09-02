#!/usr/bin/env python3
"""Converge the global Copilot instructions link and retire the legacy shell-profile export.

usage: copilot-instructions.py install|check

Environment: COPILOT_INSTRUCTIONS_LINK (the ~/.copilot/copilot-instructions.md path),
COPILOT_INSTRUCTIONS_TARGET (the canonical AGENTS.md), HOME, optional XDG_CONFIG_HOME.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NoReturn

SETUP_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SETUP_DIR.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup import safe_file
from scripts.setup.cli_errors import run_cli

LEGACY_START = "# >>> hard-eng managed Copilot instructions >>>"
LEGACY_END = "# <<< hard-eng managed Copilot instructions <<<"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup:copilot: {message}")


def required_path(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        fail(f"missing required environment value: {name}")
    return Path(value)


def legacy_profiles(home: Path) -> tuple[Path, ...]:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return (
        home / ".bash_profile",
        home / ".bashrc",
        home / ".zshenv",
        home / ".zprofile",
        home / ".zshrc",
        config_home / "fish/config.fish",
    )


def without_legacy_block(current: str, path: Path) -> str:
    lines = current.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == LEGACY_START]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == LEGACY_END]
    if not starts and not ends:
        return current
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        fail(f"malformed legacy Copilot markers; remove the block by hand: {path}")
    before = lines[: starts[0]]
    if before and before[-1].strip() == "":
        before = before[:-1]
    return "".join(before) + "".join(lines[ends[0] + 1 :])


def link_state(link: Path, target: Path) -> str:
    if target.is_symlink() or not target.is_file():
        fail(f"canonical instructions must be a regular file: {target}")
    if link.is_symlink():
        try:
            same = link.resolve(strict=True) == target.resolve(strict=True)
        except OSError:
            same = False
        if not same:
            fail(f"Copilot instructions link has another owner: {link}")
        return "linked"
    if link.exists():
        fail(f"Copilot instructions file has another owner; move it aside to let Hard Eng own it: {link}")
    return "missing"


def profile_updates(home: Path) -> list[tuple[Path, bytes, int, bytes]]:
    updates: list[tuple[Path, bytes, int, bytes]] = []
    for profile in legacy_profiles(home):
        try:
            current, mode = safe_file.read_snapshot(profile.parent, Path(profile.name))
        except FileNotFoundError:
            continue
        except OSError as error:
            fail(f"profile path is unsafe; leaving it untouched: {profile}: {error}")
        try:
            text = current.decode("utf-8")
        except UnicodeDecodeError:
            continue
        updated = without_legacy_block(text, profile)
        if updated != text:
            updates.append((profile, current, mode, updated.encode("utf-8")))
    return updates


def install(link: Path, target: Path, home: Path) -> int:
    changed: list[str] = []
    updates = profile_updates(home)
    if link_state(link, target) == "missing":
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        changed.append(str(link))
    for profile, current, mode, updated in updates:
        safe_file.replace_path_if_unchanged(profile, current, mode, updated)
        changed.append(str(profile))
    print("setup:copilot: PASS " + (f"updated {', '.join(changed)}" if changed else "unchanged"))
    return 0


def check(link: Path, target: Path, home: Path) -> int:
    if link_state(link, target) != "linked":
        fail(f"Copilot instructions link is missing: {link}")
    stale = [
        str(profile)
        for profile in legacy_profiles(home)
        if profile.is_file() and LEGACY_START in profile.read_text(encoding="utf-8", errors="replace")
    ]
    if stale:
        fail("legacy Copilot instruction block remains: " + ", ".join(stale))
    print("setup:copilot: PASS")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"install", "check"}:
        fail("usage: copilot-instructions.py install|check")
    link = required_path("COPILOT_INSTRUCTIONS_LINK")
    target = required_path("COPILOT_INSTRUCTIONS_TARGET")
    home = Path(os.environ["HOME"])
    if sys.argv[1] == "check":
        return check(link, target, home)
    return install(link, target, home)


if __name__ == "__main__":
    raise SystemExit(run_cli("setup:copilot-instructions", main))
