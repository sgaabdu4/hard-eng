#!/usr/bin/env python3
"""Run a repository script as a child process, or inside this process when HARD_ENG_INPROCESS=1 so mutation testing sees it."""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import threading
import traceback
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Self

from bounded_run import run_captured

INPROCESS_FLAG = "HARD_ENG_INPROCESS"
PROCESS_STATE = threading.RLock()
CHILD_TIMEOUT = 600.0
ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIRS = (
    ROOT / "skills" / "he" / "scripts",
    ROOT / "skills" / "deterministic-checks" / "scripts",
    ROOT / "scripts",
)


class ScriptRunnerError(Exception):
    """A repository script was started as a child process while in-process mode is on."""


@dataclass(frozen=True)
class ScriptResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


def in_process() -> bool:
    return os.environ.get(INPROCESS_FLAG) == "1"


def repository_script(path: Path) -> bool:
    resolved = path.resolve()
    return resolved.suffix == ".py" and any(directory in resolved.parents for directory in SCRIPT_DIRS)


def dotted_name(path: Path) -> str:
    return ".".join(path.resolve().relative_to(ROOT).with_suffix("").parts)


def load_script(path: Path) -> ModuleType:
    name = dotted_name(path)
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path.resolve())
    if spec is None or spec.loader is None:
        raise ScriptRunnerError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


class _ExistingModuleLoader(importlib.abc.Loader):
    def __init__(self, module: ModuleType) -> None:
        self.module = module

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        return self.module

    def exec_module(self, module: ModuleType) -> None:
        return None


class DottedSiblingFinder(importlib.abc.MetaPathFinder):
    """Load `import build_steps` as `skills.he.scripts.build_steps` so every module has one name."""

    def find_spec(
        self, fullname: str, path: object = None, target: object = None
    ) -> importlib.machinery.ModuleSpec | None:
        if "." in fullname:
            return None
        for directory in SCRIPT_DIRS:
            candidate = directory / f"{fullname}.py"
            if not candidate.is_file():
                continue
            dotted = dotted_name(candidate)
            loaded = sys.modules.get(dotted)
            if loaded is not None:
                return importlib.util.spec_from_loader(fullname, _ExistingModuleLoader(loaded))
            return importlib.util.spec_from_file_location(dotted, candidate)
        return None


def install_finder() -> None:
    if not any(isinstance(item, DottedSiblingFinder) for item in sys.meta_path):
        sys.meta_path.insert(0, DottedSiblingFinder())


REGRESSION_SUFFIXES = ("_regression.py", "_regression_check.py")


GUARD_FRAMES = ("_spawned_by_regression", "__init__")


def _spawned_by_regression() -> str | None:
    for frame in reversed(traceback.extract_stack()):
        path = Path(frame.filename)
        if ROOT not in path.parents or (path.name == "script_runner.py" and any(g in frame.name for g in GUARD_FRAMES)):
            continue
        return path.name if path.name.endswith(REGRESSION_SUFFIXES) else None
    return None


def _guarded_popen(original: type[subprocess.Popen[bytes]]) -> type[subprocess.Popen[bytes]]:
    class GuardedPopen(original):  # type: ignore[valid-type, misc]
        def __init__(self, args: object, *rest: object, **kwargs: object) -> None:
            if isinstance(args, (list, tuple)) and len(args) >= 2:
                first, second = str(args[0]), str(args[1])
                if first == sys.executable and repository_script(Path(second)) and (caller := _spawned_by_regression()):
                    raise ScriptRunnerError(f"{caller} started {second} as a child process; use run_script")
            super().__init__(args, *rest, **kwargs)  # type: ignore[misc]

    return GuardedPopen


def install_child_guard() -> None:
    if getattr(subprocess.Popen, "__name__", "") != "GuardedPopen":
        subprocess.Popen = _guarded_popen(subprocess.Popen)  # type: ignore[misc, assignment]


def _exit_code(value: object) -> tuple[int, str]:
    if value is None:
        return 0, ""
    if isinstance(value, int):
        return value, ""
    return 1, f"{value}\n"


class _CapturedFds:
    """Mirror child-process capture: writes straight to fd 1 and 2 land in the result too."""

    def __enter__(self) -> Self:
        self.captures = [_scratch_fd() for _ in (1, 2)]
        self.saved = [os.dup(fd) for fd in (1, 2)]
        for stream in (sys.__stdout__, sys.__stderr__):
            if stream is not None:
                stream.flush()
        for fd, capture in zip((1, 2), self.captures, strict=True):
            os.dup2(capture, fd)
        return self

    def __exit__(self, *_: object) -> None:
        for fd, saved in zip((1, 2), self.saved, strict=True):
            os.dup2(saved, fd)
            os.close(saved)

    def text(self) -> tuple[str, str]:
        parts = []
        for capture in self.captures:
            os.lseek(capture, 0, os.SEEK_SET)
            chunks = []
            while chunk := os.read(capture, 65536):
                chunks.append(chunk)
            os.close(capture)
            parts.append(b"".join(chunks).decode("utf-8", "replace"))
        return parts[0], parts[1]


def _scratch_fd() -> int:
    fd, path = tempfile.mkstemp(prefix="script-runner-")
    os.unlink(path)
    return fd


def _run_inprocess(
    script: Path, args: Sequence[str], cwd: str | None, env: Mapping[str, str] | None, stdin: str | None
) -> ScriptResult:
    module = load_script(script)
    main = getattr(module, "main", None)
    if not callable(main):
        raise ScriptRunnerError(f"{script} has no main()")
    saved_argv, saved_cwd, saved_env = sys.argv, os.getcwd(), dict(os.environ)
    saved_streams = sys.stdin, sys.stdout, sys.stderr
    out, err = io.StringIO(), io.StringIO()
    sys.argv = [str(script), *args]
    sys.stdin, sys.stdout, sys.stderr = io.StringIO(stdin or ""), out, err
    if env is not None:
        os.environ.clear()
        os.environ.update(env)
    if cwd is not None:
        os.chdir(cwd)
    try:
        with _CapturedFds() as fds:
            try:
                code, message = _exit_code(main())
            except SystemExit as exit_request:
                code, message = _exit_code(exit_request.code)
            except Exception:
                code, message = 1, traceback.format_exc()
    finally:
        sys.stdin, sys.stdout, sys.stderr = saved_streams
        sys.argv = saved_argv
        os.environ.clear()
        os.environ.update(saved_env)
        os.chdir(saved_cwd)
    fd_out, fd_err = fds.text()
    return ScriptResult(code, out.getvalue() + fd_out, err.getvalue() + fd_err + message)


def spawn_script(
    script: Path, args: Sequence[str], *, env: Mapping[str, str], cwd: str | Path | None = None, quiet: bool = False
) -> subprocess.Popen[str]:
    """Deliberate child process for tests that need two scripts running at once; env is explicit because an in-process run may be swapping os.environ on another thread."""
    sink = subprocess.DEVNULL if quiet else subprocess.PIPE
    return subprocess.Popen(
        [sys.executable, str(script), *args],
        cwd=None if cwd is None else str(cwd),
        env=dict(env),
        stdout=sink,
        stderr=sink,
        text=True,
    )


def run_script(
    script: Path,
    args: Sequence[str] = (),
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    stdin: str | None = None,
    timeout: float = CHILD_TIMEOUT,
) -> ScriptResult:
    if in_process():
        with PROCESS_STATE:
            return _run_inprocess(script, args, None if cwd is None else str(cwd), env, stdin)
    result = run_captured(
        [sys.executable, str(script), *args],
        timeout,
        cwd=None if cwd is None else str(cwd),
        env=None if env is None else dict(env),
        input_data=None if stdin is None else stdin.encode("utf-8"),
    )
    return ScriptResult(
        result.returncode, result.stdout.decode("utf-8", "replace"), result.stderr.decode("utf-8", "replace")
    )
