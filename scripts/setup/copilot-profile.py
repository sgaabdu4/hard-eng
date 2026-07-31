#!/usr/bin/env python3
"""Converge global Copilot instruction discovery in user shell profiles."""

from __future__ import annotations

import contextlib
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Iterator, NoReturn


START = "# >>> hard-eng managed Copilot instructions >>>"
END = "# <<< hard-eng managed Copilot instructions <<<"
VARIABLE = "COPILOT_CUSTOM_INSTRUCTIONS_DIRS"


class Profile:
    def __init__(self, path: Path, current: bytes, mode: int, existed: bool) -> None:
        self.path = path
        self.current = current
        self.mode = mode
        self.existed = existed
        self.updated = b""

    @property
    def signature(self) -> tuple[bool, bytes, int]:
        return self.existed, self.current, self.mode


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup:copilot: {message}")


def shell_name() -> str:
    value = os.environ.get("SHELL", "")
    name = value.rsplit("/", 1)[-1]
    if name not in {"bash", "zsh", "fish"}:
        fail(f"unsupported shell: {value or 'unset'}")
    return name


def fish_config_home(home: Path) -> Path:
    value = os.environ.get("XDG_CONFIG_HOME") or str(home / ".config")
    config_home = Path(value)
    if not config_home.is_absolute():
        fail(f"XDG_CONFIG_HOME must be absolute: {value}")
    return config_home


def profile_paths(home: Path) -> tuple[Path, ...]:
    paths = [
        home / ".bash_profile",
        home / ".bashrc",
        home / ".zshenv",
        home / ".zprofile",
        home / ".zshrc",
        fish_config_home(home) / "fish/config.fish",
    ]
    active = {
        "bash": (home / ".bash_profile", home / ".bashrc"),
        "zsh": (home / ".zshenv", home / ".zprofile", home / ".zshrc"),
        "fish": (fish_config_home(home) / "fish/config.fish",),
    }[shell_name()]
    selected: list[Path] = []
    for path in (*paths, *active):
        if path not in selected:
            selected.append(path)
    return tuple(selected)


def read_profile(path: Path) -> Profile:
    if not os.path.lexists(path):
        return Profile(path, b"", 0o600, False)
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode):
        fail(f"profile is not a regular file; refusing to replace it: {path}")
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        fail(f"profile is not valid UTF-8; refusing to replace it: {path}")
    return Profile(path, raw, stat.S_IMODE(metadata.st_mode), True)


def profile_kind(path: Path) -> str:
    return "fish" if path.name == "config.fish" else "posix"


def managed_block(kind: str) -> str:
    if kind == "fish":
        return (
            f"{START}\n"
            f'set -gx {VARIABLE} "$HOME/.agents"\n'
            f"{END}\n"
        )
    return (
        f"{START}\n"
        f'export {VARIABLE}="$HOME/.agents"\n'
        f"{END}\n"
    )


def marker_indexes(lines: list[str]) -> tuple[list[int], list[int]]:
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == START]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == END]
    return starts, ends


def has_unmanaged_variable(lines: list[str], kind: str) -> bool:
    pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(VARIABLE)}(?![A-Za-z0-9_])")
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or not pattern.search(line):
            continue
        if kind == "fish":
            if re.search(r"\bset\b", line):
                return True
        elif re.search(r"(?:^|[;\s])(?:export\s+)?"
                       rf"{re.escape(VARIABLE)}\s*=", line):
            return True
    return False


def render(profile: Profile) -> None:
    current = profile.current.decode("utf-8")
    lines = current.splitlines(keepends=True)
    starts, ends = marker_indexes(lines)
    kind = profile_kind(profile.path)
    if len(starts) == 0 and len(ends) == 0:
        if has_unmanaged_variable(lines, kind):
            fail(f"Copilot instruction export has another owner: {profile.path}")
        prefix = current
        if prefix and not prefix.endswith(("\n", "\r")):
            prefix += "\n"
        if prefix:
            prefix += "\n"
        profile.updated = (prefix + managed_block(kind)).encode("utf-8")
        return
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        fail(f"malformed or duplicate managed Copilot markers: {profile.path}")
    outside = lines[: starts[0]] + lines[ends[0] + 1 :]
    if has_unmanaged_variable(outside, kind):
        fail(f"Copilot instruction export has another owner: {profile.path}")
    profile.updated = (
        "".join(lines[: starts[0]]) + managed_block(kind) + "".join(lines[ends[0] + 1 :])
    ).encode("utf-8")


def current_signature(profile: Profile) -> tuple[bool, bytes, int]:
    if not os.path.lexists(profile.path):
        return False, b"", 0o600
    metadata = os.lstat(profile.path)
    if not stat.S_ISREG(metadata.st_mode):
        fail(f"profile changed type during convergence: {profile.path}")
    return True, profile.path.read_bytes(), stat.S_IMODE(metadata.st_mode)


def atomic_replace(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".hard-eng-copilot.", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def restore_profile(profile: Profile) -> None:
    if profile.existed:
        atomic_replace(profile.path, profile.current, profile.mode)
        return
    if not os.path.lexists(profile.path):
        return
    metadata = os.lstat(profile.path)
    if not stat.S_ISREG(metadata.st_mode) or profile.path.read_bytes() != profile.updated:
        fail(f"rollback found a changed new profile: {profile.path}")
    profile.path.unlink()


@contextlib.contextmanager
def convergence_lock(home: Path) -> Iterator[None]:
    owner = home / ".local/share/hard-eng"
    if os.path.lexists(owner):
        metadata = os.lstat(owner)
        if not stat.S_ISDIR(metadata.st_mode):
            fail(f"managed asset root is not a regular directory: {owner}")
    else:
        owner.mkdir(parents=True)
    lock = owner / ".copilot-profile.lock"
    try:
        lock.mkdir()
    except FileExistsError:
        fail(f"another Copilot profile convergence is active: {lock}")
    try:
        yield
    finally:
        lock.rmdir()


def backup_profiles(home: Path, profiles: list[Profile]) -> None:
    changed = [profile for profile in profiles if profile.updated != profile.current]
    if not changed:
        return
    backup_dir = home / ".local/share/hard-eng/backups/shell"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if not backup_dir.is_dir() or backup_dir.is_symlink():
        fail(f"backup owner is not a regular directory: {backup_dir}")
    os.chmod(backup_dir, 0o700)
    for index, profile in enumerate(changed):
        if not profile.existed:
            continue
        name = (
            f"{profile.path.name}."
            f"{os.getpid()}."
            f"{index}.copilot.bak"
        )
        destination = backup_dir / name
        destination.write_bytes(profile.current)
        os.chmod(destination, 0o600)


def install(home: Path, profiles: list[Profile]) -> int:
    changed = [profile for profile in profiles if profile.updated != profile.current]
    if not changed:
        print("setup:copilot: PASS unchanged")
        return 0
    with convergence_lock(home):
        for profile in changed:
            if current_signature(profile) != profile.signature:
                fail(
                    "profile changed during convergence; leaving the user edit untouched: "
                    f"{profile.path}"
                )
        backup_profiles(home, profiles)
        committed: list[Profile] = []
        try:
            for profile in changed:
                atomic_replace(profile.path, profile.updated, profile.mode)
                committed.append(profile)
        except OSError as error:
            rollback_error: OSError | None = None
            for profile in reversed(committed):
                try:
                    restore_profile(profile)
                except OSError as restore_exception:
                    rollback_error = restore_exception
                    break
            if rollback_error is not None:
                fail(f"convergence and rollback failed: {rollback_error}")
            fail(f"convergence failed: {error}")
    print(f"setup:copilot: PASS installed ({len(changed)} profile(s))")
    return 0


def check(profiles: list[Profile]) -> int:
    stale = [profile.path for profile in profiles if profile.updated != profile.current]
    if stale:
        fail("managed Copilot instruction block missing or stale: " + ", ".join(map(str, stale)))
    print("setup:copilot: PASS")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"install", "check"}:
        fail("usage: copilot-profile.py install|check")
    home = Path(os.environ["HOME"])
    profiles = [read_profile(path) for path in profile_paths(home)]
    for profile in profiles:
        render(profile)
    if sys.argv[1] == "check":
        return check(profiles)
    return install(home, profiles)


if __name__ == "__main__":
    raise SystemExit(main())
