"""Small shared IO and subprocess operations."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import cast

Json = dict[str, object]


class GateError(Exception):
    """A check could not establish success."""


def object_value(value: object, label: str) -> Json:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise GateError(f"{label} must be a JSON object")
    return cast(Json, value)


def array(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise GateError(f"{label} must be an array")
    return cast(list[object], value)


def strings(value: object, label: str) -> list[str]:
    items = array(value, label)
    if not all(isinstance(item, str) and item for item in items):
        raise GateError(f"{label} must contain nonempty strings")
    return cast(list[str], items)


def parse_json(text: str, label: str = "report") -> Json:
    try:
        value: object = json.loads(text)
    except ValueError as error:
        raise GateError(f"{label} is not valid JSON") from error
    return object_value(value, label)


def read_json(path: Path) -> Json:
    try:
        return parse_json(path.read_text(), str(path))
    except OSError as error:
        raise GateError(f"Cannot read {path.name}: {error.strerror}") from error


def write_json(path: Path, value: object) -> None:
    write_file(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def write_file(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise GateError(f"Refusing to replace symlink: {path}")
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".hard-eng-")
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def relative_path(root: Path, value: str) -> Path:
    path = root / value
    if Path(value).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise GateError(f"Path escapes repository: {value}")
    return path


def environment(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_") and key not in {"GIT_SSH", "GIT_SSH_COMMAND", "GIT_ASKPASS"}:
            env.pop(key)
    env.update({"CI": "true", "PYTHONDONTWRITEBYTECODE": "1", "NO_COLOR": "1"})
    return env


def run(
    argv: list[str],
    root: Path,
    timeout: float = 120,
    *,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    if not argv or timeout <= 0:
        raise GateError("Command and positive timeout required")
    try:
        process = subprocess.Popen(
            argv,
            cwd=root,
            env=env or environment(root),
            text=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as error:
        raise GateError(f"Cannot start {Path(argv[0]).name}: {error.strerror}") from error
    try:
        stdout, stderr = process.communicate(input_text, timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        if isinstance(error, KeyboardInterrupt):
            raise
        raise GateError(f"{Path(argv[0]).name} timed out after {timeout:g}s") from error
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def checked(argv: list[str], root: Path, timeout: float = 120) -> str:
    result = run(argv, root, timeout)
    if result.returncode:
        raise GateError(f"{Path(argv[0]).name} failed (exit {result.returncode})")
    return result.stdout


def git(root: Path, *args: str) -> str:
    return checked(["git", "-C", str(root), *args], root)


def repository(path: Path) -> Path:
    return Path(git(path.resolve(), "rev-parse", "--show-toplevel").strip()).resolve()


def state_dir(root: Path) -> Path:
    path = Path(git(root, "rev-parse", "--git-path", "hard-eng").strip())
    path = path if path.is_absolute() else root / path
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def source_files(root: Path) -> list[Path]:
    output = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    return sorted({root / name for name in output.split("\0") if name and (root / name).is_file()})
