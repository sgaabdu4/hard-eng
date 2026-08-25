"""Shared primitives for Hard Eng execution-evidence receipts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NoReturn

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"))
from bounded_run import run_captured
from git_env import git_env
from safe_plan_io import consume_if_unchanged, create_new, read_snapshot, replace_if_unchanged, repository_artifact

FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
APPROVAL_RESPONSE = re.compile(r"APPROVE [0-9A-F]{6}")
AUTONOMOUS_DIRECTIVE = "YES — use Hard Eng autonomous mode for this task."
DEFAULT_CHALLENGE_SECONDS = 600
MAX_CHALLENGE_SECONDS = 3600
STOP_BEFORE = [
    "data-deletion-or-destructive-schema",
    "force-or-history-rewrite",
    "machine-scope-write",
    "secret-exposure",
]
EXACT_APPROVAL_KINDS = STOP_BEFORE


class EvidenceError(ValueError):
    pass


def enforcement_configured(repo: Path) -> bool:
    try:
        value = json.loads((repo / "hard-eng.gates.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and isinstance(value.get("enforcement"), dict)


def fail(message: str) -> NoReturn:
    raise EvidenceError(message)


def repo_path(value: str) -> Path:
    repo = Path(value).resolve()
    if not (repo / ".git").exists():
        fail("repository is not a Git checkout")
    return repo


def plan_path(repo: Path, value: str) -> Path:
    raw = Path(value)
    lexical = Path(os.path.abspath(raw if raw.is_absolute() else repo / raw))
    try:
        relative = lexical.relative_to(repo)
    except ValueError:
        fail("PLAN must be inside the repository")
    current = repo
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            fail(f"PLAN path contains a symlink: {current}")
    path = lexical.resolve()
    try:
        relative = path.relative_to(repo)
    except ValueError:
        fail("PLAN must be inside the repository")
    if len(relative.parts) != 3 or relative.parts[0] != "features" or relative.name != "PLAN.md":
        fail("PLAN must be features/<feature>/PLAN.md")
    if not path.is_file() or path.is_symlink():
        fail("PLAN must be a regular file")
    return path


def plan_id(plan: Path) -> str:
    text = plan.read_text(encoding="utf-8")
    matches = re.findall(r"(?m)^- plan_id = (\S+)$", text)
    if len(matches) != 1:
        fail("PLAN requires exactly one plan_id")
    return matches[0]


def receipt_path(plan: Path, name: str) -> Path:
    return plan.parent / "receipts" / name


def action_digest(tool_name: str, tool_input: dict[str, object]) -> str:
    action = json.dumps(
        {"tool_input": tool_input, "tool_name": tool_name.casefold()}, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(action.encode("utf-8")).hexdigest()


def protected_binding_digest(value: dict[str, object]) -> str:
    binding = {
        key: value.get(key)
        for key in (
            "action_digest",
            "approval_kind",
            "effect",
            "plan_fingerprint",
            "plan_id",
            "repository_context",
            "request_digest",
            "session_digest",
            "target",
            "tool_name",
        )
    }
    return text_digest(json.dumps(binding, sort_keys=True, separators=(",", ":")))


def text_digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_text(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def require_digest(value: str, label: str) -> str:
    if not FINGERPRINT.fullmatch(value):
        fail(f"{label} must be a sha256 digest")
    return value


def require_session(value: str) -> str:
    if not value.strip():
        fail("authorization requires a runtime session id")
    return text_digest(value)


def expiry(seconds: int) -> tuple[datetime, datetime]:
    if seconds < 30 or seconds > MAX_CHALLENGE_SECONDS:
        fail(f"expiry must be between 30 and {MAX_CHALLENGE_SECONDS} seconds")
    created = utc_now()
    return created, created + timedelta(seconds=seconds)


def git_value(repo: Path, *args: str) -> str:
    result = run_captured(["git", *args], 15, cwd=str(repo), env=git_env())
    stdout = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode != 0 or not stdout:
        fail(f"cannot establish Git identity: {' '.join(args)}")
    return stdout


def repository_identity(repo: Path) -> dict[str, str]:
    try:
        head = git_value(repo, "rev-parse", "--verify", "HEAD")
    except EvidenceError:
        head = "unborn"
    common = Path(git_value(repo, "rev-parse", "--git-common-dir"))
    git_dir = Path(git_value(repo, "rev-parse", "--git-dir"))
    common = common if common.is_absolute() else repo / common
    git_dir = git_dir if git_dir.is_absolute() else repo / git_dir
    return {
        "checkout_digest": text_digest(str(repo.resolve()) + "\0" + str(git_dir.resolve())),
        "repository_digest": text_digest(str(common.resolve())),
        "repository_head": head,
    }


def repository_context(repo: Path) -> dict[str, str]:
    return {**repository_identity(repo), "repository_artifact": repository_artifact(repo)}


def json_bytes(value: dict[str, object]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def safe_receipt_json(repo: Path, path: Path, value: dict[str, object]) -> None:
    relative = path.relative_to(repo)
    replacement = json_bytes(value)
    try:
        expected, mode = read_snapshot(repo, relative)
    except FileNotFoundError:
        create_new(repo, relative, replacement, 0o600)
    else:
        replace_if_unchanged(repo, relative, expected, mode, replacement)


def load_receipt(repo: Path, plan: Path, name: str) -> tuple[dict[str, object], bytes, int]:
    path = receipt_path(plan, name)
    try:
        raw, mode = read_snapshot(repo, path.relative_to(repo))
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid receipt {name}: {error}")
    if not isinstance(value, dict):
        fail(f"invalid receipt {name}: root must be an object")
    return value, raw, mode


def git_private_path(repo: Path, name: str) -> Path:
    resolved = run_captured(["git", "rev-parse", "--git-dir"], 15, cwd=str(repo), env=git_env())
    stdout = resolved.stdout.decode("utf-8", "replace").strip()
    if resolved.returncode != 0 or not stdout:
        fail("cannot find the repository Git-private directory")
    git_dir = Path(stdout)
    if not git_dir.is_absolute():
        git_dir = repo / git_dir
    return git_dir.resolve() / "hard-eng" / name


def direct_receipt_path(repo: Path) -> Path:
    return git_private_path(repo, "current-direct.json")


def invalidate_direct_receipt(repo: Path) -> bool:
    path = direct_receipt_path(repo)
    try:
        raw, mode = read_snapshot(path.parent, Path(path.name))
    except FileNotFoundError:
        return False
    consume_if_unchanged(path.parent, Path(path.name), raw, mode)
    return True


def repository_relative_path(repo: Path, value: str, label: str) -> Path:
    raw = Path(value)
    if raw.is_absolute() or ".." in raw.parts:
        fail(f"{label} must be repository-relative: {value}")
    lexical = Path(os.path.abspath(repo / raw))
    try:
        relative = lexical.relative_to(repo)
    except ValueError as error:
        raise EvidenceError(f"{label} escaped the repository: {value}") from error
    current = repo
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            fail(f"{label} contains a symlink: {value}")
    return relative


def atomic_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink():
        fail("receipt directory must not be a symlink")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        fail(f"missing regular receipt: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        fail(f"invalid receipt {path.name}: {error}")
    if not isinstance(value, dict):
        fail(f"invalid receipt {path.name}: root must be an object")
    return value
