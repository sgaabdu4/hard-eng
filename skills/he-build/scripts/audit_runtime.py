"""Isolated runtime and warm-prefix parallel scheduling for final audit."""
from __future__ import annotations

import concurrent.futures
import hashlib
import math
import os
import stat
import time
from pathlib import Path

from audit_contract import AuditError
from audit_packet import snapshot_id


MAX_AUDIT_WORKERS = 8
DEADLINE_HEADROOM = 1.25
DEADLINE_RESERVE_SECONDS = 30


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


def deadline_workers(
    *, remaining_shards: int, warm_elapsed_s: float, remaining_s: float,
    max_workers: int = MAX_AUDIT_WORKERS,
) -> int:
    if remaining_shards <= 0:
        return 1
    usable_s = remaining_s - DEADLINE_RESERVE_SECONDS
    estimated_shard_s = max(1.0, warm_elapsed_s * DEADLINE_HEADROOM)
    waves = math.floor(usable_s / estimated_shard_s)
    required = math.ceil(remaining_shards / waves) if waves > 0 else max_workers + 1
    if required > max_workers:
        raise AuditError(
            "AUDIT_DEADLINE_INFEASIBLE: "
            f"required_workers={required} worker_cap={max_workers} "
            f"remaining_shards={remaining_shards}"
        )
    return max(1, required)


def warm_then_parallel(
    scopes, action, cached_tokens, max_workers: int = MAX_AUDIT_WORKERS, *,
    deadline: float | None = None, cancel=lambda: None,
):
    if not scopes:
        raise AuditError("audit requires at least one review shard")
    warm_started = time.monotonic()
    results = [action(1, scopes[0])]
    warm_elapsed = time.monotonic() - warm_started
    indexed = list(enumerate(scopes[1:], 2))
    if not indexed:
        return results, {
            "cacheProven": any(cached_tokens(result) > 0 for result in results),
            "serialProbeCount": 1, "parallelWorkerCount": 1,
        }
    workers = min(max_workers, len(indexed))
    if deadline is not None:
        workers = deadline_workers(
            remaining_shards=len(indexed), warm_elapsed_s=warm_elapsed,
            remaining_s=deadline - time.monotonic(), max_workers=workers,
        )
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    futures = {executor.submit(action, index, scope): index for index, scope in indexed}
    ordered = {}
    try:
        for future in concurrent.futures.as_completed(futures):
            ordered[futures[future]] = future.result()
    except BaseException:
        cancel()
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    executor.shutdown(wait=True)
    results.extend(ordered[index] for index, _ in indexed)
    return results, {
        "cacheProven": any(cached_tokens(result) > 0 for result in results),
        "serialProbeCount": 1,
        "parallelWorkerCount": workers,
    }


def common_prefix_bytes(values) -> int:
    encoded = [value.encode("utf-8", "surrogateescape") for value in values]
    return len(os.path.commonprefix(encoded)) if encoded else 0


def audit_performance_metrics(
    usages, *, elapsed_ms: int, shard_count: int, common_prefix_bytes: int, schedule: dict,
) -> dict[str, int | bool]:
    input_tokens = sum(usage.get("input_tokens", 0) for usage in usages)
    cached_tokens = sum(usage.get("cached_input_tokens", 0) for usage in usages)
    output_tokens = sum(usage.get("output_tokens", 0) for usage in usages)
    reasoning_tokens = sum(usage.get("reasoning_output_tokens", 0) for usage in usages)
    return {
        "elapsedMs": elapsed_ms,
        "shardCount": shard_count,
        "commonPrefixBytes": common_prefix_bytes,
        "cacheHitBasisPoints": cached_tokens * 10_000 // input_tokens if input_tokens else 0,
        "uncachedInputTokens": max(0, input_tokens - cached_tokens),
        "outputTokens": output_tokens,
        "reasoningOutputTokens": reasoning_tokens,
        **schedule,
    }
