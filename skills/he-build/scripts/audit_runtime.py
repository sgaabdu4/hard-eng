"""Isolated runtime and warm-prefix parallel scheduling for final audit."""
from __future__ import annotations

import concurrent.futures
import hashlib
import os
import stat
from pathlib import Path

from audit_contract import AuditError
from audit_packet import snapshot_id


MAX_AUDIT_WORKERS = 4


def require_unchanged_snapshot(repo: Path, expected: str) -> None:
    if snapshot_id(repo) != expected:
        raise AuditError("repository changed during audit")


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def require_unchanged_file(path: Path, expected: str, label: str) -> None:
    if file_digest(path) != expected:
        raise AuditError(f"{label} changed during audit")


def set_workspace_writable(root: Path, writable: bool) -> None:
    paths = [root, *root.rglob("*")]
    for path in reversed(paths):
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IWUSR if writable else mode & ~0o222)


def isolated_environment(
    directory: Path, controller_codex: Path | None = None,
) -> tuple[dict[str, str], tuple[str, ...]]:
    original_home = Path.home().resolve()
    original_codex = (
        controller_codex or Path(os.environ.get("CODEX_HOME", original_home / ".codex"))
    ).resolve()
    auth = original_codex / "auth.json"
    if auth.is_symlink() or not auth.is_file():
        raise AuditError("audit controller requires Codex auth.json")
    home = directory / "home"
    home.mkdir()
    allowed = ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM", "NO_COLOR")
    environment = {
        "HOME": str(home),
        "CODEX_HOME": str(original_codex),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "XDG_CACHE_HOME": str(home / ".cache"),
        "PYTHONDONTWRITEBYTECODE": "1",
        **{name: os.environ[name] for name in allowed if name in os.environ},
    }
    return environment, (str(original_home), str(original_codex))


def warm_then_parallel(scopes, action, max_workers: int = MAX_AUDIT_WORKERS):
    if not scopes:
        raise AuditError("audit requires at least one review shard")
    results = [action(1, scopes[0])]
    indexed = list(enumerate(scopes[1:], 2))
    if not indexed:
        return results
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(max_workers, len(indexed)),
    ) as executor:
        futures = [executor.submit(action, index, scope) for index, scope in indexed]
        results.extend(future.result() for future in futures)
    return results
