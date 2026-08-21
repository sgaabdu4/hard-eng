#!/usr/bin/env python3
"""Validate and execute one product-walkthrough phase boundary."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

sys.dont_write_bytecode = True

DETERMINISTIC_SCRIPTS = Path(__file__).resolve().parents[2] / "deterministic-checks" / "scripts"
if str(DETERMINISTIC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

from bounded_run import CapturedRunResult, run_captured

ALLOWED_ENVIRONMENT = ("HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "TZ")
ARGUMENT_KINDS = {
    "artifact-path",
    "job-path",
    "literal",
    "phase-id",
    "project-file",
    "project-path",
    "synthetic-endpoint",
}
SYNTHETIC_HOSTS = {"127.0.0.1", "::1", "localhost"}
URL = re.compile(r"https?://[^\s]+")


class BoundaryError(ValueError):
    pass


@dataclass(frozen=True)
class BoundaryPlan:
    mode: str
    phase: str
    argv: tuple[str, ...]
    cwd: Path
    root: Path
    artifact_root: Path
    executable: dict[str, Any]
    argument_files: tuple[dict[str, Any], ...]
    endpoints: tuple[str, ...]
    environment: dict[str, str]
    backend: dict[str, Any]


def _inside(root: Path, path: Path, field: str, *, must_exist: bool = False) -> Path:
    if not path.is_absolute():
        raise BoundaryError(f"{field} must be absolute")
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise BoundaryError(f"{field} escapes its owner") from exc
    _reject_symlinks(path, include_final=must_exist)
    if must_exist and not path.exists():
        raise BoundaryError(f"{field} does not exist")
    return path


def _reject_symlinks(path: Path, *, include_final: bool = True) -> None:
    absolute = Path(os.path.abspath(path))
    parts = absolute.parts
    current = Path(parts[0])
    limit = len(parts) if include_final else len(parts) - 1
    for index in range(1, limit):
        current /= parts[index]
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                raise BoundaryError(f"path contains symlink: {current}")
        except FileNotFoundError:
            break


def reject_symlink_components(path: Path, *, include_final: bool = True) -> None:
    _reject_symlinks(path, include_final=include_final)


def digest_file(path: Path) -> str:
    _reject_symlinks(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        hasher = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            hasher.update(chunk)
        return hasher.hexdigest()
    finally:
        os.close(descriptor)


def read_json_file(path: Path) -> dict[str, Any]:
    _reject_symlinks(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BoundaryError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BoundaryError(f"JSON root must be an object: {path}")
    return value


def write_json_once(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_symlinks(path, include_final=False)
    if path.exists():
        raise BoundaryError(f"refusing to overwrite immutable receipt: {path}")
    descriptor, temporary_raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_raw)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise BoundaryError(f"refusing to overwrite immutable receipt: {path}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    parent = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def _file_identity(path: Path, expected_sha256: str, field: str) -> dict[str, Any]:
    _reject_symlinks(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise BoundaryError(f"{field} must be a regular file")
        if before.st_uid not in {0, os.getuid()}:
            raise BoundaryError(f"{field} has an unapproved owner")
        if before.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise BoundaryError(f"{field} may not be group/other writable")
        if before.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) == 0:
            raise BoundaryError(f"{field} is not executable")
        hasher = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            hasher.update(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ):
            raise BoundaryError(f"{field} changed while hashing")
    finally:
        os.close(descriptor)
    actual_sha256 = hasher.hexdigest()
    if actual_sha256 != expected_sha256:
        raise BoundaryError(f"{field} SHA-256 does not match approval")
    return {
        "path": str(path),
        "sha256": actual_sha256,
        "owner_uid": before.st_uid,
        "mode": stat.S_IMODE(before.st_mode),
        "device": before.st_dev,
        "inode": before.st_ino,
        "bytes": before.st_size,
    }


def _synthetic_endpoint(raw: str, field: str) -> str:
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not host
        or (host not in SYNTHETIC_HOSTS and not host.endswith(".invalid"))
    ):
        raise BoundaryError(f"{field} must be an explicit synthetic endpoint")
    return raw


def _environment() -> dict[str, str]:
    result = {
        name: os.environ[name] for name in ALLOWED_ENVIRONMENT if name in os.environ and "\x00" not in os.environ[name]
    }
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    return result


def _trusted_backend(path: Path, name: str) -> dict[str, Any]:
    return {"name": name, **_file_identity(path, _sha256(path), f"{name} backend")}


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _containment_backend(mode: str, artifact_root: Path, cwd: Path) -> dict[str, Any]:
    if mode == "declarative":
        return {
            "name": "none",
            "supported": False,
            "filesystem": "declared-project-only",
            "network": "declared-synthetic-only",
            "prefix": [],
        }
    system = platform.system()
    if system == "Darwin":
        executable = Path("/usr/bin/sandbox-exec")
        if not executable.is_file():
            raise BoundaryError("enforced containment is unavailable on this host")
        escaped = str(artifact_root).replace('"', '\\"')
        profile = "\n".join(
            (
                "(version 1)",
                "(allow default)",
                "(deny network*)",
                "(deny file-write*)",
                f'(allow file-write* (subpath "{escaped}"))',
                '(allow file-write-data (literal "/dev/null"))',
            )
        )
        backend = _trusted_backend(executable, "macos-sandbox-exec")
        return {
            **backend,
            "supported": True,
            "filesystem": "artifact-root-write-only",
            "network": "denied",
            "policy_sha256": hashlib.sha256(profile.encode()).hexdigest(),
            "prefix": [str(executable), "-p", profile],
        }
    if system == "Linux":
        executable = next((path for path in (Path("/usr/bin/bwrap"), Path("/bin/bwrap")) if path.is_file()), None)
        if executable is None:
            raise BoundaryError("enforced containment is unavailable on this host")
        backend = _trusted_backend(executable, "linux-bwrap")
        return {
            **backend,
            "supported": True,
            "filesystem": "artifact-root-write-only",
            "network": "denied",
            "prefix": [
                str(executable),
                "--die-with-parent",
                "--new-session",
                "--unshare-net",
                "--ro-bind",
                "/",
                "/",
                "--bind",
                str(artifact_root),
                str(artifact_root),
                "--chdir",
                str(cwd),
                "--",
            ],
        }
    raise BoundaryError("enforced containment is unavailable on this host")


def validate_boundary(
    phase: str, value: dict[str, Any], *, root: Path, artifact_root: Path, job_path: Path
) -> BoundaryPlan:
    argv = value.get("argv")
    schema = value.get("argument_schema")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) or not item or "\x00" in item for item in argv)
    ):
        raise BoundaryError(f"phase {phase} argv must be non-empty strings")
    if not isinstance(schema, list) or len(schema) != len(argv) - 1:
        raise BoundaryError(f"phase {phase} argument schema must bind every argument")
    executable_path = Path(argv[0])
    if not executable_path.is_absolute():
        raise BoundaryError(f"phase {phase} executable must be absolute")
    expected_sha256 = value.get("executable_sha256")
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise BoundaryError(f"phase {phase} executable SHA-256 is required")
    executable = _file_identity(executable_path, expected_sha256, f"phase {phase} executable")
    argument_files: list[dict[str, Any]] = []
    for index, (argument, rule) in enumerate(zip(argv[1:], schema, strict=True), start=1):
        if not isinstance(rule, dict) or not {"kind", "value"}.issubset(rule):
            raise BoundaryError(f"phase {phase} argument {index} schema is invalid")
        kind = rule["kind"]
        expected_fields = {"kind", "value", "sha256"} if kind == "project-file" else {"kind", "value"}
        if set(rule) != expected_fields:
            raise BoundaryError(f"phase {phase} argument {index} schema is invalid")
        if kind not in ARGUMENT_KINDS or rule["value"] != argument:
            raise BoundaryError(f"phase {phase} argument {index} is unexpected")
        if kind == "job-path" and argument != str(job_path):
            raise BoundaryError(f"phase {phase} argument {index} must be the current job")
        if kind == "phase-id" and argument != phase:
            raise BoundaryError(f"phase {phase} argument {index} must equal the phase")
        if kind == "project-file":
            path = _inside(root, Path(argument), f"phase {phase} argument {index}", must_exist=True)
            if not path.is_file():
                raise BoundaryError(f"phase {phase} argument {index} must be a project file")
            expected = rule["sha256"]
            if not isinstance(expected, str) or digest_file(path) != expected:
                raise BoundaryError(f"phase {phase} argument {index} file SHA-256 does not match approval")
            argument_files.append({"path": str(path), "sha256": expected})
        if kind == "project-path":
            _inside(root, Path(argument), f"phase {phase} argument {index}")
        if kind == "artifact-path":
            _inside(artifact_root, Path(argument), f"phase {phase} argument {index}")
        if kind == "synthetic-endpoint":
            _synthetic_endpoint(argument, f"phase {phase} argument {index}")
    endpoints_raw = value.get("endpoints")
    if not isinstance(endpoints_raw, list) or any(not isinstance(item, str) for item in endpoints_raw):
        raise BoundaryError(f"phase {phase} endpoints must be a string list")
    endpoints = tuple(_synthetic_endpoint(item, f"phase {phase} endpoint") for item in endpoints_raw)
    if len(endpoints) != len(set(endpoints)):
        raise BoundaryError(f"phase {phase} endpoints must be unique")
    for argument in argv[1:]:
        for match in URL.finditer(argument):
            endpoint = _synthetic_endpoint(match.group(), f"phase {phase} endpoint argument")
            if endpoint not in endpoints:
                raise BoundaryError(f"phase {phase} endpoint argument is not declared")
    containment = value.get("containment")
    if not isinstance(containment, dict) or set(containment) != {"mode"}:
        raise BoundaryError(f"phase {phase} containment must contain only mode")
    mode = containment["mode"]
    if mode not in {"declarative", "enforced-local"}:
        raise BoundaryError(f"phase {phase} containment mode is unsupported")
    if mode == "enforced-local" and endpoints:
        raise BoundaryError(f"phase {phase} enforced-local mode denies all network endpoints")
    cwd = _inside(root, Path(value.get("cwd", "")), f"phase {phase} cwd", must_exist=True)
    backend = _containment_backend(mode, artifact_root, cwd)
    return BoundaryPlan(
        mode=mode,
        phase=phase,
        argv=tuple(argv),
        cwd=cwd,
        root=root,
        artifact_root=artifact_root,
        executable=executable,
        argument_files=tuple(argument_files),
        endpoints=endpoints,
        environment=_environment(),
        backend=backend,
    )


def execute_boundary(plan: BoundaryPlan, timeout: int) -> tuple[CapturedRunResult, dict[str, Any]]:
    _file_identity(Path(plan.executable["path"]), plan.executable["sha256"], f"phase {plan.phase} executable")
    for item in plan.argument_files:
        if digest_file(Path(item["path"])) != item["sha256"]:
            raise BoundaryError(f"phase {plan.phase} argument file changed before execution")
    command = [*plan.backend["prefix"], *plan.argv]
    result = run_captured(command, timeout=float(timeout), grace=2.0, cwd=str(plan.cwd), env=plan.environment)
    after = _file_identity(Path(plan.executable["path"]), plan.executable["sha256"], f"phase {plan.phase} executable")
    if after != plan.executable:
        raise BoundaryError(f"phase {plan.phase} executable identity changed during execution")
    for item in plan.argument_files:
        if digest_file(Path(item["path"])) != item["sha256"]:
            raise BoundaryError(f"phase {plan.phase} argument file changed during execution")
    argv_digest = hashlib.sha256(json.dumps(list(plan.argv), separators=(",", ":")).encode()).hexdigest()
    backend = {key: value for key, value in plan.backend.items() if key != "prefix"}
    evidence = {
        "requested_mode": plan.mode,
        "classification": ("enforced" if plan.mode == "enforced-local" else "declarative-not-enforced"),
        "backend": backend,
        "executable": plan.executable,
        "argument_files": list(plan.argument_files),
        "argv_count": len(plan.argv),
        "argv_sha256": argv_digest,
        "environment_names": sorted(plan.environment),
        "filesystem": {
            "policy": plan.backend["filesystem"],
            "writable_root": str(plan.artifact_root),
            "enforced": plan.mode == "enforced-local",
        },
        "network": {
            "policy": plan.backend["network"],
            "endpoints": list(plan.endpoints),
            "enforced": plan.mode == "enforced-local",
        },
        "process_group_terminal": result.terminal,
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
    }
    return result, evidence
