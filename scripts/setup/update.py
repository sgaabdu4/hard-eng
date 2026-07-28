#!/usr/bin/env python3
"""Verify and atomically apply an explicitly reviewed setup manifest."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[2]
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env

MANIFEST_PATH = ROOT / "scripts/setup/manifest.json"
PACKAGE_PATH = ROOT / "runtime/npm/package.json"
LOCK_PATH = ROOT / "runtime/npm/package-lock.json"
CONTRACT = ROOT / "scripts/setup-contract-check.py"


class UpdateError(RuntimeError):
    pass


def load_manifest_module():
    path = ROOT / "scripts/setup/manifest.py"
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("setup_manifest", path)
    if spec is None or spec.loader is None:
        raise UpdateError("manifest validator unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(arguments: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        env=git_env(),
    )


def require_clean_repository() -> None:
    result = run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT)
    if result.returncode:
        raise UpdateError(result.stderr.strip() or "cannot inspect repository")
    if result.stdout:
        raise UpdateError("repository must be clean before setup update")


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise UpdateError(f"cannot read JSON {path}: {error}") from error
    if not isinstance(value, dict):
        raise UpdateError(f"JSON root must be an object: {path}")
    return value


def validate_structure(current: dict, candidate: dict) -> None:
    stable_top = ("schema_version", "requirements")
    for key in stable_top:
        if candidate.get(key) != current.get(key):
            raise UpdateError(f"candidate changes non-pin contract: {key}")
    current_runtime = current["npm_runtime"]
    candidate_runtime = candidate["npm_runtime"]
    if candidate_runtime.get("remove_paths") != current_runtime.get("remove_paths"):
        raise UpdateError("candidate changes npm remove_paths")
    current_packages = current_runtime["packages"]
    candidate_packages = candidate_runtime["packages"]
    if [
        (item["name"], item["tree_exclusions"]) for item in candidate_packages
    ] != [
        (item["name"], item["tree_exclusions"]) for item in current_packages
    ]:
        raise UpdateError("candidate changes npm package ownership")

    for name, binary in candidate["binaries"].items():
        version = binary["version"]
        for asset in binary["assets"].values():
            if version not in asset["url"]:
                raise UpdateError(f"binary URL does not contain reviewed version: {name}")
    npm_versions = {item["name"]: item["version"] for item in candidate_packages}
    if candidate["binaries"]["codebase-memory-mcp"]["version"] != npm_versions[
        "codebase-memory-mcp"
    ]:
        raise UpdateError("Codebase Memory npm and binary versions differ")


def sha_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_npm_archives(candidate: dict, temporary: Path) -> None:
    cache = temporary / "npm-cache"
    packs = temporary / "npm-packs"
    cache.mkdir()
    packs.mkdir()
    for package in candidate["npm_runtime"]["packages"]:
        spec = f"{package['name']}@{package['version']}"
        before = set(packs.glob("*.tgz"))
        result = run(
            ["npm", "pack", spec, "--cache", str(cache), "--pack-destination", str(packs)]
        )
        if result.returncode:
            raise UpdateError(result.stderr.strip() or f"npm pack failed: {spec}")
        created = set(packs.glob("*.tgz")) - before
        if len(created) != 1:
            raise UpdateError(f"npm pack output ambiguous: {spec}")
        archive = created.pop()
        if sha_file(archive, "sha512") != package["sha512"]:
            raise UpdateError(f"npm sha512 mismatch: {spec}")


def verify_context_ref(candidate: dict) -> None:
    context = candidate["codex"]["context_mode"]
    reference = f"refs/tags/{context['marketplace_ref']}"
    result = run(["git", "ls-remote", context["marketplace_source"], f"{reference}*"])
    if result.returncode:
        raise UpdateError(result.stderr.strip() or "cannot verify Context Mode tag")
    references = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if len(fields) == 2:
            references[fields[1]] = fields[0]
    commit = references.get(f"{reference}^{{}}", references.get(reference))
    if commit != context["marketplace_commit"]:
        raise UpdateError("Context Mode tag commit mismatch")


def verify_binary_assets(candidate: dict, temporary: Path) -> None:
    downloads = temporary / "downloads"
    downloads.mkdir()
    for name, binary in candidate["binaries"].items():
        for platform, asset in binary["assets"].items():
            destination = downloads / f"{name}-{platform}"
            digest = hashlib.sha256()
            try:
                with urllib.request.urlopen(asset["url"], timeout=60) as response:
                    with destination.open("wb") as output:
                        while chunk := response.read(1024 * 1024):
                            output.write(chunk)
                            digest.update(chunk)
            except OSError as error:
                raise UpdateError(f"asset download failed: {name}/{platform}: {error}") from error
            if digest.hexdigest() != asset["sha256"]:
                raise UpdateError(f"binary sha256 mismatch: {name}/{platform}")


def build_runtime_files(candidate: dict, temporary: Path) -> tuple[bytes, bytes]:
    package = load_json(PACKAGE_PATH)
    package["dependencies"] = {
        item["name"]: item["version"] for item in candidate["npm_runtime"]["packages"]
    }
    runtime = temporary / "runtime"
    runtime.mkdir()
    package_bytes = (json.dumps(package, indent=2) + "\n").encode()
    (runtime / "package.json").write_bytes(package_bytes)
    shutil.copy2(LOCK_PATH, runtime / "package-lock.json")
    result = run(
        [
            "npm",
            "install",
            "--package-lock-only",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
        ],
        cwd=runtime,
    )
    if result.returncode:
        raise UpdateError(result.stderr.strip() or "npm lock refresh failed")
    return package_bytes, (runtime / "package-lock.json").read_bytes()


def write_atomic(
    target: Path,
    content: bytes,
    mode: int,
    replace: Callable[[str | Path, str | Path], None],
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".hard-eng-update.", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def commit_files(
    updates: dict[Path, bytes],
    validator: Callable[[], None],
    *,
    expected: dict[Path, bytes] | None = None,
    replace: Callable[[str | Path, str | Path], None] = os.replace,
) -> None:
    snapshots: dict[Path, tuple[bytes, int]] = {}
    for target in updates:
        if target.is_symlink() or not target.is_file():
            raise UpdateError(f"update target is not a regular file: {target}")
        snapshots[target] = (target.read_bytes(), stat.S_IMODE(target.stat().st_mode))
        if expected is not None and expected.get(target) != snapshots[target][0]:
            raise UpdateError(f"update target changed during verification: {target}")
    if all(snapshots[path][0] == content for path, content in updates.items()):
        validator()
        return
    replaced: list[Path] = []
    try:
        for target, (before, _) in snapshots.items():
            if target.read_bytes() != before:
                raise UpdateError(f"update target changed concurrently: {target}")
        for target, content in updates.items():
            write_atomic(target, content, snapshots[target][1], replace)
            replaced.append(target)
        validator()
    except BaseException as error:
        rollback_errors = []
        for target in reversed(replaced):
            before, mode = snapshots[target]
            try:
                write_atomic(target, before, mode, replace)
            except BaseException as rollback_error:
                rollback_errors.append(f"{target}: {rollback_error}")
        if rollback_errors:
            raise UpdateError(
                "setup update failed and rollback was incomplete: "
                + "; ".join(rollback_errors)
            ) from error
        raise


def validate_applied_contract() -> None:
    result = run([sys.executable, str(CONTRACT)], cwd=ROOT)
    if result.returncode:
        raise UpdateError(result.stderr.strip() or "updated setup contract failed")


def main(arguments: list[str]) -> int:
    if len(arguments) != 1:
        raise UpdateError("usage: setup.sh update <reviewed-manifest.json>")
    candidate_path = Path(arguments[0]).expanduser().resolve()
    require_clean_repository()
    preimages = {
        path: path.read_bytes() for path in (MANIFEST_PATH, PACKAGE_PATH, LOCK_PATH)
    }
    try:
        current = json.loads(preimages[MANIFEST_PATH])
    except json.JSONDecodeError as error:
        raise UpdateError(f"cannot read current manifest: {error}") from error
    candidate = load_json(candidate_path)
    try:
        load_manifest_module().validate(candidate)
    except SystemExit as error:
        raise UpdateError(f"candidate manifest is invalid: {error}") from error
    validate_structure(current, candidate)
    with tempfile.TemporaryDirectory(prefix="hard-eng-setup-update-") as temporary_name:
        temporary = Path(temporary_name)
        verify_npm_archives(candidate, temporary)
        verify_context_ref(candidate)
        verify_binary_assets(candidate, temporary)
        package_bytes, lock_bytes = build_runtime_files(candidate, temporary)
        manifest_bytes = (json.dumps(candidate, indent=2) + "\n").encode()
        commit_files(
            {
                MANIFEST_PATH: manifest_bytes,
                PACKAGE_PATH: package_bytes,
                LOCK_PATH: lock_bytes,
            },
            validate_applied_contract,
            expected=preimages,
        )
    print("setup:update: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except UpdateError as error:
        print(f"setup:update: {error}", file=sys.stderr)
        raise SystemExit(1)
