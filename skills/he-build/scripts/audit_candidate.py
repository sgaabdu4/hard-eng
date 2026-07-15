"""Immutable Git-patch materialization for Hard Eng candidate admission."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from audit_admission import parse_planned_paths

MAX_PATCH_BYTES = 8 * 1024 * 1024
_DIFF_HEADER = re.compile(rb"(?m)^diff --git a/([^\r\n]+) b/([^\r\n]+)$")
_FULL_INDEX = re.compile(rb"(?m)^index [0-9a-f]{40}\.\.[0-9a-f]{40}(?: ([0-7]{6}))?$")


class CandidateError(RuntimeError):
    pass


@dataclass(frozen=True)
class CandidateBinding:
    unit_id: str
    completed_slices: tuple[str, ...]
    accumulated_paths: tuple[str, ...]
    accumulated_digest: str


def git_environment(home: Path) -> dict[str, str]:
    allowed = ("PATH", "TMPDIR", "LANG", "LC_ALL")
    return {
        **{name: os.environ[name] for name in allowed if name in os.environ},
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def patch_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load_patch(path: Path) -> bytes:
    resolved = path.expanduser().resolve()
    if resolved.is_symlink() or not resolved.is_file():
        raise CandidateError("candidate patch must be a regular non-symlink file")
    if resolved.stat().st_size > MAX_PATCH_BYTES:
        raise CandidateError("candidate patch exceeds fixed size limit")
    data = resolved.read_bytes()
    if not data:
        raise CandidateError("candidate patch is empty")
    return data


def patch_paths(data: bytes, *, plan_relative: str, sensitive) -> tuple[str, ...]:
    headers = _DIFF_HEADER.findall(data)
    index_modes = _FULL_INDEX.findall(data)
    if not headers or len(index_modes) != len(headers):
        raise CandidateError("candidate patch is not a canonical full-index Git diff")
    if any(mode in {b"120000", b"160000"} for mode in index_modes) or re.search(
        rb"(?m)^(?:new|old) mode (?:120000|160000)$", data
    ):
        raise CandidateError("candidate patch contains symlink or submodule mode")
    paths: list[str] = []
    for left, right in headers:
        try:
            left_text, right_text = left.decode("utf-8"), right.decode("utf-8")
        except UnicodeError as exc:
            raise CandidateError("candidate patch path is not UTF-8") from exc
        if left_text != right_text:
            raise CandidateError("candidate patch rename/copy paths are unsupported")
        path = PurePosixPath(left_text)
        value = path.as_posix()
        if (path.is_absolute() or value != left_text or any(part in {"", ".", ".."} for part in path.parts)
                or value == plan_relative or sensitive(value)):
            raise CandidateError("candidate patch contains unsafe path")
        paths.append(value)
    if len(set(paths)) != len(paths):
        raise CandidateError("candidate patch repeats a path")
    return tuple(paths)


def _paths(root: Path, *args: str) -> tuple[str, ...]:
    raw = _git(root, *args)
    return tuple(sorted(part.decode("utf-8", "surrogateescape")
                        for part in raw.split(b"\0") if part))


def _state_value(plan: Path, key: str) -> str:
    matches = re.findall(rf"(?m)^- {re.escape(key)} = (.+)$", plan.read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise CandidateError(f"PLAN requires exactly one {key}")
    return matches[0].strip()


def _completed_prefix(plan: Path, unit_id: str) -> tuple[str, ...]:
    if _state_value(plan, "active_slice") != unit_id:
        raise CandidateError("candidate unit does not equal active slice manifest")
    try:
        active_number = int(unit_id.removeprefix("S-"))
    except ValueError as exc:
        raise CandidateError("candidate unit is not a valid slice manifest") from exc
    expected = tuple(f"S-{number}" for number in range(1, active_number))
    raw = _state_value(plan, "completed_slices")
    actual = () if raw == "none" else tuple(part.strip() for part in raw.split(","))
    if actual != expected:
        raise CandidateError("completed slices do not equal active slice prefix")
    return actual


def candidate_binding(root: Path, plan: Path, unit_id: str, patch_bytes: bytes, *,
                      sensitive) -> tuple[CandidateBinding, tuple[str, ...], bytes]:
    plan_relative = plan.resolve().relative_to(root).as_posix()
    completed = _completed_prefix(plan, unit_id)
    active_paths = parse_planned_paths(plan, unit_id, root, sensitive)
    accumulated: set[str] = set()
    for completed_id in completed:
        accumulated.update(parse_planned_paths(plan, completed_id, root, sensitive))
    accumulated_paths = tuple(sorted(accumulated))
    changed_paths = patch_paths(patch_bytes, plan_relative=plan_relative, sensitive=sensitive)
    if set(changed_paths) != set(active_paths):
        raise CandidateError("candidate patch paths do not equal active slice manifest")
    staged = _paths(root, "diff", "--cached", "--name-only", "-z", "--diff-filter=ACDMRTUXB")
    if plan_relative in staged:
        raise CandidateError("PLAN must not be staged")
    staged_non_plan = tuple(path for path in staged if path != plan_relative)
    if set(staged_non_plan) != set(accumulated_paths):
        raise CandidateError("staged paths do not equal accumulated completed-slice manifests")
    unstaged = _paths(root, "diff", "--name-only", "-z", "--diff-filter=ACDMRTUXB")
    untracked = _paths(root, "ls-files", "--others", "--exclude-standard", "-z")
    if any(path != plan_relative for path in (*unstaged, *untracked)):
        raise CandidateError("delivery checkout has non-PLAN dirt outside accumulated state")
    accumulated_patch = (b"" if not accumulated_paths else _git(
        root, "diff", "--cached", "--binary", "--full-index", "--no-ext-diff",
        "--no-textconv", "HEAD", "--",
        *accumulated_paths,
    ))
    binding = CandidateBinding(
        unit_id=unit_id,
        completed_slices=completed,
        accumulated_paths=accumulated_paths,
        accumulated_digest=patch_digest(accumulated_patch),
    )
    return binding, changed_paths, accumulated_patch


def _git(root: Path, *args: str, data: bytes | None = None, environment=None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], input=data, capture_output=True, check=False,
        env=environment,
    )
    if result.returncode != 0:
        raise CandidateError(result.stderr.decode("utf-8", "replace").strip() or "git apply failed")
    return result.stdout


@contextmanager
def materialized_candidate(root: Path, plan: Path, patch_bytes: bytes, unit_id: str, *,
                           sensitive, snapshot_id):
    root = root.resolve()
    try:
        plan_relative = plan.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise CandidateError("PLAN is outside delivery repository") from exc
    binding, paths, accumulated_patch = candidate_binding(
        root, plan, unit_id, patch_bytes, sensitive=sensitive
    )
    source_snapshot = snapshot_id(root)
    if _state_value(plan, "snapshot_id") != source_snapshot:
        raise CandidateError("PLAN snapshot is stale for accumulated candidate state")
    with tempfile.TemporaryDirectory(prefix="he-audit-candidate-") as temporary:
        candidate = Path(temporary) / "repo"
        home = Path(temporary) / "home"
        home.mkdir(mode=0o700)
        environment = git_environment(home)
        subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "clone", "-q", "--local",
             "--no-hardlinks", str(root), str(candidate)],
            check=True, capture_output=True, env=environment,
        )
        _git(candidate, "config", "core.hooksPath", "/dev/null", environment=environment)
        if accumulated_patch:
            _git(candidate, "apply", "--check", "--index", "-", data=accumulated_patch,
                 environment=environment)
            _git(candidate, "apply", "--index", "-", data=accumulated_patch,
                 environment=environment)
        candidate_plan = candidate / plan_relative
        candidate_plan.parent.mkdir(parents=True, exist_ok=True)
        candidate_plan.write_bytes(plan.read_bytes())
        if snapshot_id(candidate) != source_snapshot:
            raise CandidateError("accumulated candidate materialization is stale")
        _git(candidate, "apply", "--check", "--index", "-", data=patch_bytes,
             environment=environment)
        _git(candidate, "apply", "--index", "-", data=patch_bytes, environment=environment)
        yield candidate, candidate_plan, paths, patch_digest(patch_bytes), binding
