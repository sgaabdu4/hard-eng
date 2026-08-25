#!/usr/bin/env python3
"""Prove feature-setup readiness before planning: checkout, worktree write, gate manifest, memory index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import stat
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DETERMINISTIC_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(DETERMINISTIC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

import project_gate
import worktree
from bounded_run import run_captured
from checkout_policy import checkout_policy
from git_env import git_env

SETUP_STATE_VERSION = 1
RECEIPT_NAME = "hard-eng-feature-setup-v1.json"
MEMORY_TOOL = "codebase-memory-mcp"
WORKTREE_SCRIPT = DETERMINISTIC_SCRIPTS / "worktree.py"
WORKTREE_TIMEOUT = 1500
LIST_TIMEOUT = 30
INDEX_TIMEOUT = 300
MIGRATION_DIRECTIVE = "run the deterministic-checks gate-migration before planning"
WIRING_DIRECTIVE = (
    "hard-eng.gates.json is present but no commit hook enforces it: wire hooks per the "
    "deterministic-checks hooks reference (for example a .githooks/pre-commit invoking "
    "project_gate.py phase, then git config core.hooksPath .githooks)"
)
AGENTS_ROOT = SCRIPT_DIR.parents[2]


def emit(key: str, value: object) -> None:
    print(f"{key}={str(value).replace(chr(10), ' ').replace(chr(13), ' ')}")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def git_head(root: Path) -> str:
    result = worktree.git(root, "rev-parse", "--verify", "HEAD", check=False)
    return result.stdout.strip() if result.returncode == 0 else "UNBORN"


def receipt_path(git_dir: Path) -> Path:
    return git_dir / RECEIPT_NAME


def input_fingerprint(root: Path, policy: str) -> str:
    digest = hashlib.sha256()
    for part in (str(SETUP_STATE_VERSION), worktree.setup_input_fingerprint(root)):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    manifest = root / project_gate.MANIFEST_NAME
    try:
        content = manifest.read_bytes() if manifest.is_file() and not manifest.is_symlink() else b"absent"
    except OSError:
        content = b"absent"
    digest.update(content)
    digest.update(b"\0")
    digest.update(policy.encode("utf-8"))
    digest.update(b"\0")
    digest.update(hooks_state(root).encode("utf-8"))
    digest.update(b"\0")
    digest.update(f"{sys.version_info.major}.{sys.version_info.minor}".encode("ascii"))
    return digest.hexdigest()


def preflight(repo: str) -> tuple[Path, Path, str, str, str]:
    root = worktree.git_root(repo)
    git_dir = worktree.git_path(root, "--git-dir")
    policy = checkout_policy(root)
    fingerprint = input_fingerprint(root, policy)
    return root, git_dir, policy, fingerprint, git_head(root)


def read_receipt(receipt: Path) -> dict | None:
    try:
        if receipt.is_symlink() or not receipt.is_file():
            return None
        if stat.S_IMODE(receipt.stat().st_mode) & 0o077:
            return None
        payload = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def write_receipt(receipt: Path, payload: dict) -> None:
    if receipt.is_symlink() or (receipt.exists() and not receipt.is_file()):
        raise OSError("feature-setup receipt target is unsafe")
    temporary = receipt.with_name(f".{receipt.name}.{secrets.token_hex(24)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, receipt)
        receipt.chmod(0o600)
        directory = os.open(receipt.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def receipt_payload(
    root: Path,
    checkout: str,
    feature_slug: str,
    head: str,
    fingerprint: str,
    memory: tuple[str, str | None],
    warnings: list[str],
) -> dict:
    return {
        "version": SETUP_STATE_VERSION,
        "receipt_id": secrets.token_hex(8),
        "repository_root": str(root),
        "checkout": checkout,
        "feature_slug": feature_slug,
        "head_sha": head,
        "created_at": utc_now(),
        "input_fingerprint": fingerprint,
        "probes": {
            "worktree_write": "PASS",
            "gate_manifest": "PASS",
            "memory_index": {"verdict": memory[0], "indexed_head_sha": memory[1]},
        },
        "verdict": "PASS",
        "warnings": warnings,
    }


def verify_state(root: Path, git_dir: Path, fingerprint: str, head: str) -> tuple[int, str, dict | None]:
    payload = read_receipt(receipt_path(git_dir))
    if payload is None:
        return 4, "no current feature-setup receipt: run setup_state.py run", None
    if payload.get("version") != SETUP_STATE_VERSION or payload.get("verdict") != "PASS":
        return 4, "feature-setup receipt is not a passing current-version receipt: run setup_state.py run", None
    if payload.get("repository_root") != str(root):
        return 4, "feature-setup receipt belongs to a different checkout: run setup_state.py run", None
    if payload.get("input_fingerprint") != fingerprint:
        return 4, "feature-setup inputs changed since the receipt: run setup_state.py run", None
    probes = payload.get("probes")
    memory = probes.get("memory_index") if isinstance(probes, dict) else None
    indexed = memory.get("indexed_head_sha") if isinstance(memory, dict) else None
    if isinstance(indexed, str) and indexed and indexed != head:
        return 5, "codebase memory index is behind HEAD: setup_state.py run refreshes only the memory probe", payload
    return 0, "feature-setup receipt current", payload


def probe_worktree(root: Path, choice: str) -> tuple[int, dict[str, str], list[str]]:
    command = [
        sys.executable,
        str(WORKTREE_SCRIPT),
        "--repo",
        str(root),
        "--intent",
        "write",
        "--checkout-choice",
        choice,
    ]
    try:
        captured = run_captured(command, WORKTREE_TIMEOUT, grace=2, env=git_env())
    except OSError as error:
        return 4, {}, [f"worktree write probe could not run: {type(error).__name__}"]
    values: dict[str, str] = {}
    for line in captured.stdout.decode("utf-8", "replace").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values.setdefault(key, value)
    errors: list[str] = []
    index = 1
    while f"error_{index}" in values:
        errors.append(values[f"error_{index}"])
        index += 1
    return captured.returncode, values, errors


def probe_manifest(root: Path) -> tuple[str, str | None]:
    manifest = root / project_gate.MANIFEST_NAME
    if manifest.is_symlink() or not manifest.is_file():
        return "FAIL", f"{project_gate.MANIFEST_NAME} is missing: {MIGRATION_DIRECTIVE}"
    try:
        for phase in ("commit", "push", "ci"):
            project_gate.load_phase(root, phase)
    except project_gate.ProjectGateError as error:
        return "FAIL", f"{error}: {MIGRATION_DIRECTIVE}"
    return "PASS", None


def hooks_state(root: Path) -> str:
    local = worktree.git(root, "config", "--local", "--get", "core.hooksPath", check=False)
    if local.returncode == 0 and local.stdout.strip():
        value = local.stdout.strip()
        hook_dir = Path(value).expanduser()
        if not hook_dir.is_absolute():
            hook_dir = root / hook_dir
        hook = hook_dir / "pre-commit"
        return f"hooks-path:{value}:{int(hook.is_file() and os.access(hook, os.X_OK))}"
    common = worktree.git_path(root, "--git-common-dir")
    native = common / "hooks" / "pre-commit"
    if native.is_file() and os.access(native, os.X_OK):
        return "native-hooks:1"
    owner = worktree.git(AGENTS_ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir", check=False)
    if owner.returncode == 0 and owner.stdout.strip() and Path(owner.stdout.strip()).resolve() == common:
        return "owner-dispatcher:1"
    return "unwired:0"


def probe_enforcement(root: Path) -> tuple[str, str | None]:
    return ("PASS", None) if hooks_state(root).endswith(":1") else ("FAIL", WIRING_DIRECTIVE)


def memory_cli(arguments: list[str], payload: dict, timeout: float) -> dict | None:
    executable = shutil.which(MEMORY_TOOL)
    if not executable:
        return None
    try:
        captured = run_captured(
            [executable, "cli", *arguments], timeout, grace=2, input_data=json.dumps(payload).encode("utf-8")
        )
        if captured.returncode != 0:
            return None
        parsed = json.loads(captured.stdout.decode("utf-8", "replace"))
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def indexed_head(root: Path) -> str | None:
    listing = memory_cli(["list_projects"], {}, LIST_TIMEOUT)
    projects = listing.get("projects") if listing else None
    if not isinstance(projects, list):
        return None
    for entry in projects:
        if isinstance(entry, dict) and entry.get("root_path") == str(root):
            git_info = entry.get("git")
            if isinstance(git_info, dict) and isinstance(git_info.get("head_sha"), str):
                return git_info["head_sha"]
    return None


def probe_memory(root: Path, head: str) -> tuple[str, str | None, str | None]:
    if shutil.which(MEMORY_TOOL) is None:
        return "WARN", None, "codebase memory tool unavailable; planning evidence degrades to direct reads"
    if indexed_head(root) == head:
        return "PASS", head, None
    memory_cli(["index_repository"], {"repo_path": str(root)}, INDEX_TIMEOUT)
    if indexed_head(root) == head:
        return "PASS", head, None
    return "WARN", None, "codebase memory index refresh incomplete; planning evidence degrades to direct reads"


def refresh_memory(root: Path, git_dir: Path, head: str, payload: dict) -> int:
    verdict, indexed, detail = probe_memory(root, head)
    payload["probes"]["memory_index"] = {"verdict": verdict, "indexed_head_sha": indexed}
    payload["head_sha"] = head
    payload["created_at"] = utc_now()
    payload["warnings"] = [detail] if detail else []
    try:
        write_receipt(receipt_path(git_dir), payload)
    except OSError as error:
        emit("result", "invalid")
        emit("error_1", f"feature-setup receipt write failed: {type(error).__name__}")
        return 4
    emit("result", "pass")
    emit("refresh", "memory-only")
    emit("memory_index", verdict)
    if detail:
        emit("warning_1", detail)
    return 0


def full_run(root: Path, git_dir: Path, fingerprint: str, head: str, choice: str, feature_slug: str) -> int:
    with ThreadPoolExecutor(max_workers=4) as pool:
        worktree_future = pool.submit(probe_worktree, root, choice)
        manifest_future = pool.submit(probe_manifest, root)
        enforcement_future = pool.submit(probe_enforcement, root)
        memory_future = pool.submit(probe_memory, root, head)
    worktree_code, worktree_values, worktree_errors = worktree_future.result()
    manifest_verdict, manifest_detail = manifest_future.result()
    enforcement_verdict, enforcement_detail = enforcement_future.result()
    memory_verdict, memory_indexed, memory_detail = memory_future.result()

    errors = list(worktree_errors)
    if worktree_code not in (0, 3) and not errors:
        errors.append(f"worktree write probe failed with exit {worktree_code}")
    if manifest_detail:
        errors.append(manifest_detail)
    elif enforcement_detail:
        errors.append(enforcement_detail)
    if errors:
        emit("result", "invalid")
        emit("worktree_write", "PASS" if worktree_code in (0, 3) else "FAIL")
        emit("gate_manifest", manifest_verdict)
        emit("gate_enforcement", enforcement_verdict)
        emit("memory_index", memory_verdict)
        for index, error in enumerate(errors, start=1):
            emit(f"error_{index}", error)
        return 4
    if worktree_code == 3:
        emit("result", "choice-required")
        emit("choice", worktree_values.get("choice", "continue current checkout OR create new worktree"))
        return 3

    primary = worktree_values.get("worktree") == "primary"
    checkout = "primary" if primary else f"linked:{worktree_values.get('branch', 'DETACHED')}"
    head = worktree_values.get("head_sha", head)
    warnings = [memory_detail] if memory_detail else []
    payload = receipt_payload(
        root, checkout, feature_slug, head, fingerprint, (memory_verdict, memory_indexed), warnings
    )
    receipt = receipt_path(git_dir)
    try:
        write_receipt(receipt, payload)
    except OSError as error:
        emit("result", "invalid")
        emit("error_1", f"feature-setup receipt write failed: {type(error).__name__}")
        return 4
    if read_receipt(receipt) != payload:
        emit("result", "invalid")
        emit("error_1", "feature-setup receipt verification failed")
        return 4
    emit("result", "pass")
    emit("repository_root", root)
    emit("checkout", checkout)
    emit("worktree_write", "PASS")
    emit("gate_manifest", "PASS")
    emit("gate_enforcement", "PASS")
    emit("memory_index", memory_verdict)
    for index, warning in enumerate(warnings, start=1):
        emit(f"warning_{index}", warning)
    emit("receipt", receipt)
    return 0


def command_verify(repo: str) -> int:
    try:
        root, git_dir, _, fingerprint, head = preflight(repo)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        emit("result", "invalid")
        emit("error_1", f"repository preflight failed: {error}")
        return 4
    code, detail, _ = verify_state(root, git_dir, fingerprint, head)
    emit("result", "current" if code == 0 else "stale-memory" if code == 5 else "invalid")
    emit("detail", detail)
    return code


def command_run(repo: str, choice: str, feature_slug: str) -> int:
    try:
        root, git_dir, _, fingerprint, head = preflight(repo)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        emit("result", "invalid")
        emit("error_1", f"repository preflight failed: {error}")
        return 4
    code, detail, payload = verify_state(root, git_dir, fingerprint, head)
    if code == 0:
        emit("result", "current")
        emit("detail", detail)
        return 0
    if code == 5 and payload is not None:
        return refresh_memory(root, git_dir, head, payload)
    return full_run(root, git_dir, fingerprint, head, choice, feature_slug)


def require_setup(repo: Path | str) -> str | None:
    """Planning entry guard: None when the feature-setup receipt is current (soft memory staleness allowed)."""
    try:
        root, git_dir, _, fingerprint, head = preflight(str(repo))
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        return f"feature setup unverifiable: {error}"
    code, detail, _ = verify_state(root, git_dir, fingerprint, head)
    return None if code in (0, 5) else detail


def seed_receipt_for_fixture(repo: Path | str) -> Path:
    root, git_dir, _, fingerprint, head = preflight(str(repo))
    payload = receipt_payload(root, "primary", "none", head, fingerprint, ("WARN", None), [])
    receipt = receipt_path(git_dir)
    write_receipt(receipt, payload)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "verify"))
    parser.add_argument("--repo", default=".")
    parser.add_argument("--checkout-choice", choices=("auto", "current"), default="auto")
    parser.add_argument("--feature-slug", default="none")
    args = parser.parse_args()
    if args.command == "verify":
        return command_verify(args.repo)
    return command_run(args.repo, args.checkout_choice, args.feature_slug)


if __name__ == "__main__":
    sys.exit(main())
