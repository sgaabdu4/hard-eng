#!/usr/bin/env python3
"""Prove feature-setup readiness before planning: base branch, worktree, copied inputs, gate manifest, memory index."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
from checkout_policy import checkout_policy, primary_checkout
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
COPY_HOOK = AGENTS_ROOT / "scripts" / "git-hooks" / "copy-worktree-env.sh"
BASE_BRANCHES = ("main", "develop")
CHECKOUT_CHOICES = ("auto", "current", "worktree")
ENV_FILE_NAME = re.compile(r"^(\.env(\..+)?|.+\.env)$")
FEATURE_SLUG = re.compile(r"^(?!none$)[a-z0-9][a-z0-9-]*$")
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist")
FETCH_TIMEOUT = 60
GIT_TIMEOUT = 120
NULL_SHA = "0" * 40


class CheckoutPlan:
    def __init__(self, root: Path, checkout_choice: str) -> None:
        self.root = root
        self.checkout_choice = checkout_choice
        self.choices: list[tuple[str, str]] = []
        self.base_candidates: list[str] = []
        self.env_candidates: list[str] = []
        self.base_ref: str | None = None
        self.branch: str | None = None
        self.worktree_path: Path | None = None
        self.included: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []


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


def remote_bases(root: Path) -> tuple[dict[str, bool], str | None, str | None] | None:
    remotes = worktree.git(root, "remote", check=False).stdout.split()
    if "origin" not in remotes:
        return None
    fetch = worktree.git(root, "fetch", "--quiet", "origin", check=False, timeout=FETCH_TIMEOUT)
    warning = None if fetch.returncode == 0 else "git fetch origin failed; base branch resolved from the last fetch"
    exists = {
        name: worktree.git(
            root, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{name}", check=False
        ).returncode
        == 0
        for name in BASE_BRANCHES
    }
    head = worktree.git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", check=False)
    default = head.stdout.strip().removeprefix("origin/") if head.returncode == 0 and head.stdout.strip() else None
    return exists, default, warning


def resolve_base(plan: CheckoutPlan, current_branch: str, chosen: str | None) -> None:
    remote = remote_bases(plan.root)
    if remote is None:
        return
    exists, default, warning = remote
    if warning:
        plan.warnings.append(warning)
    if chosen:
        if exists.get(chosen) or chosen == default:
            plan.base_ref = f"origin/{chosen}"
        else:
            plan.errors.append(f"origin has no branch named {chosen}")
        return
    if current_branch in BASE_BRANCHES and exists[current_branch]:
        plan.base_ref = f"origin/{current_branch}"
        return
    present = [name for name in BASE_BRANCHES if exists[name]]
    if len(present) == 2:
        plan.base_candidates = present
        plan.choices.append(("base-branch", "origin has both main and develop: pass --base-branch main|develop"))
    elif present:
        plan.base_ref = f"origin/{present[0]}"
    elif default:
        plan.base_ref = f"origin/{default}"
    else:
        plan.errors.append("origin has no main, develop, or default branch to base the feature on")


def env_candidates(primary: Path, listed: tuple[str, ...]) -> list[str]:
    listing = worktree.git(
        primary, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory", check=False
    )
    found: list[str] = []
    for relative in listing.stdout.split("\0"):
        name = Path(relative).name
        if not relative or relative.endswith("/") or relative in listed:
            continue
        if not ENV_FILE_NAME.match(name) or name.endswith(ENV_TEMPLATE_SUFFIXES):
            continue
        path = primary / relative
        if path.is_file() and not path.is_symlink():
            found.append(relative)
    return sorted(found)


def registered_branch(primary: Path, path: Path) -> str | None:
    listing = worktree.git(primary, "worktree", "list", "--porcelain", "-z", check=False).stdout
    current: Path | None = None
    for record in listing.split("\0"):
        if record.startswith("worktree "):
            current = Path(record.removeprefix("worktree ")).resolve()
        elif record.startswith("branch ") and current == path.resolve():
            return record.removeprefix("branch refs/heads/")
    return None


def feature_worktree(primary: Path, feature_slug: str) -> tuple[Path, str]:
    return primary.parent / f"{primary.name}.worktrees" / feature_slug, f"feature/{feature_slug}"


def existing_feature_worktree(root: Path, policy: str, feature_slug: str) -> Path | None:
    if policy == "primary-only" or not FEATURE_SLUG.match(feature_slug):
        return None
    primary = primary_checkout(root)
    if root.resolve() != primary:
        return None
    path, branch = feature_worktree(primary, feature_slug)
    return path.resolve() if registered_branch(primary, path) == branch else None


def create_worktree(plan: CheckoutPlan, primary: Path, feature_slug: str) -> None:
    if not FEATURE_SLUG.match(feature_slug):
        plan.errors.append("creating the feature worktree requires --feature-slug <lowercase-kebab-slug>")
        return
    path, branch = feature_worktree(primary, feature_slug)
    existing = registered_branch(primary, path)
    if existing == branch:
        plan.root, plan.branch, plan.worktree_path = path.resolve(), branch, path.resolve()
        return
    if existing or path.exists():
        plan.errors.append(f"worktree path already exists for another branch: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    result = worktree.git(
        primary, "worktree", "add", str(path), "-b", branch, str(plan.base_ref), check=False, timeout=GIT_TIMEOUT
    )
    if result.returncode != 0:
        plan.errors.append(f"git worktree add failed: {result.stderr.strip() or result.returncode}")
        return
    plan.root, plan.branch, plan.worktree_path = path.resolve(), branch, path.resolve()


def provision_inputs(plan: CheckoutPlan, primary: Path, commit: bool) -> None:
    target = plan.root
    listed = worktree.include_entries(target)
    new_entries = [path for path in plan.included if path not in listed]
    if new_entries:
        include = target / ".worktreeinclude"
        existing = include.read_text(encoding="utf-8") if include.is_file() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        include.write_text(existing + "".join(f"{entry}\n" for entry in new_entries), encoding="utf-8")
        added = worktree.git(target, "add", "--", ".worktreeinclude", check=False)
        if added.returncode != 0:
            plan.errors.append(f"git add .worktreeinclude failed: {added.stderr.strip()}")
            return
    if target != primary and (new_entries or listed):
        try:
            copied = run_captured(
                ["bash", str(COPY_HOOK), NULL_SHA, "HEAD", "1"], GIT_TIMEOUT, grace=2, cwd=str(target), env=git_env()
            )
        except OSError as error:
            plan.errors.append(f"worktree input copy could not run: {type(error).__name__}")
            return
        if copied.returncode != 0:
            plan.errors.append(f"worktree input copy failed: {copied.stderr.decode('utf-8', 'replace').strip()}")
            return
    if new_entries and commit:
        committed = worktree.git(
            target,
            "commit",
            "-q",
            "-m",
            "chore: list worktree inputs",
            "--",
            ".worktreeinclude",
            check=False,
            timeout=GIT_TIMEOUT,
        )
        if committed.returncode != 0:
            plan.errors.append(f"committing .worktreeinclude failed: {committed.stderr.strip()}")


def plan_checkout(
    root: Path, policy: str, checkout_choice: str, feature_slug: str, base_branch: str | None, include_env: list[str]
) -> CheckoutPlan:
    plan = CheckoutPlan(root=root, checkout_choice=checkout_choice)
    if policy == "primary-only":
        return plan
    primary = primary_checkout(root)
    isolated = root.resolve() != primary
    current_branch = worktree.branch(root)
    dirty = bool(worktree.git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").stdout.strip("\0"))
    listed = worktree.include_entries(root)
    candidates = env_candidates(primary, listed)
    undecided = not isolated and dirty and checkout_choice == "auto"
    wants_worktree = not isolated and (not dirty or checkout_choice == "worktree")
    if undecided:
        plan.choices.append(("checkout", "primary checkout is dirty: pass --checkout-choice current|worktree"))
    if wants_worktree or undecided:
        resolve_base(plan, current_branch, base_branch)
    if candidates and not include_env:
        plan.env_candidates = candidates
        plan.choices.append(("worktreeinclude", "ignored env files found: pass --include-env <path>... or none"))
    if plan.choices or plan.errors:
        return plan
    if include_env != ["none"]:
        unknown = [path for path in include_env if path not in candidates and path not in listed]
        if unknown:
            plan.errors.append("--include-env paths are not ignored files in the primary: " + ",".join(unknown))
            return plan
        plan.included = [path for path in include_env if path not in listed]
    created = False
    if wants_worktree and plan.base_ref:
        create_worktree(plan, primary, feature_slug)
        if plan.errors:
            return plan
        created = True
    if not dirty or created:
        plan.checkout_choice = "auto"
    provision_inputs(plan, primary, commit=created)
    return plan


def emit_plan(plan: CheckoutPlan) -> None:
    if plan.base_ref:
        emit("base_ref", plan.base_ref)
    if plan.branch:
        emit("branch", plan.branch)
    if plan.worktree_path:
        emit("worktree_path", plan.worktree_path)
    emit("env_included", ",".join(plan.included) if plan.included else "none")


def full_run(root: Path, git_dir: Path, fingerprint: str, head: str, plan: CheckoutPlan, feature_slug: str) -> int:
    with ThreadPoolExecutor(max_workers=4) as pool:
        worktree_future = pool.submit(probe_worktree, root, plan.checkout_choice)
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
    if enforcement_detail:
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
        emit("choice_1", "checkout")
        emit("choice_1_prompt", worktree_values.get("choice", "continue current checkout OR create new worktree"))
        return 3

    primary = worktree_values.get("worktree") == "primary"
    checkout = "primary" if primary else f"linked:{worktree_values.get('branch', 'DETACHED')}"
    head = worktree_values.get("head_sha", head)
    warnings = plan.warnings + ([memory_detail] if memory_detail else [])
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
    emit_plan(plan)
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


def emit_choices(plan: CheckoutPlan) -> int:
    emit("result", "choice-required")
    for index, (kind, prompt) in enumerate(plan.choices, start=1):
        emit(f"choice_{index}", kind)
        emit(f"choice_{index}_prompt", prompt)
    for index, name in enumerate(plan.base_candidates, start=1):
        emit(f"base_candidate_{index}", name)
    for index, path in enumerate(plan.env_candidates, start=1):
        emit(f"env_candidate_{index}", path)
    return 3


def command_run(
    repo: str, choice: str, feature_slug: str, base_branch: str | None = None, include_env: list[str] | None = None
) -> int:
    try:
        root, git_dir, policy, fingerprint, head = preflight(repo)
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        emit("result", "invalid")
        emit("error_1", f"repository preflight failed: {error}")
        return 4
    code, detail, payload = verify_state(root, git_dir, fingerprint, head)
    if code == 0:
        emit("result", "current")
        emit("repository_root", root)
        emit("detail", detail)
        return 0
    if code == 5 and payload is not None:
        return refresh_memory(root, git_dir, head, payload)
    existing = existing_feature_worktree(root, policy, feature_slug)
    if existing is not None:
        return command_run(str(existing), choice, feature_slug, base_branch, include_env)
    try:
        plan = plan_checkout(root, policy, choice, feature_slug, base_branch, include_env or [])
    except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
        emit("result", "invalid")
        emit("error_1", f"checkout preparation failed: {error}")
        return 4
    if plan.errors:
        emit("result", "invalid")
        for index, error in enumerate(plan.errors, start=1):
            emit(f"error_{index}", error)
        return 4
    if plan.choices:
        if probe_manifest(root)[1] or probe_enforcement(root)[1]:
            return full_run(root, git_dir, fingerprint, head, plan, feature_slug)
        return emit_choices(plan)
    if plan.root != root:
        try:
            root, git_dir, _, fingerprint, head = preflight(str(plan.root))
        except (OSError, UnicodeError, subprocess.CalledProcessError) as error:
            emit("result", "invalid")
            emit("error_1", f"worktree preflight failed: {error}")
            return 4
        code, detail, _ = verify_state(root, git_dir, fingerprint, head)
        if code == 0:
            emit("result", "current")
            emit("repository_root", root)
            emit_plan(plan)
            emit("detail", detail)
            return 0
    return full_run(root, git_dir, fingerprint, head, plan, feature_slug)


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
    parser.add_argument("--checkout-choice", choices=CHECKOUT_CHOICES, default="auto")
    parser.add_argument("--feature-slug", default="none")
    parser.add_argument("--base-branch", choices=BASE_BRANCHES)
    parser.add_argument("--include-env", action="append", default=[])
    args = parser.parse_args()
    if args.command == "verify":
        return command_verify(args.repo)
    return command_run(args.repo, args.checkout_choice, args.feature_slug, args.base_branch, args.include_env)


if __name__ == "__main__":
    sys.exit(main())
