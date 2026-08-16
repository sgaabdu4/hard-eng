#!/usr/bin/env python3
"""Regression checks for aggregate proof identity and safe cache reuse."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import time
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts/check-skill-contracts.py"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"skill-contract-regressions: {message}")


def load_checker():
    spec = importlib.util.spec_from_file_location("hard_eng_contract_checker", CHECKER)
    if spec is None or spec.loader is None:
        fail("cannot load check-skill-contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_identity(module) -> None:
    _receipt, identity = module.proof_identity()
    if identity.get("schema_version") != 2:
        fail("proof identity schema was not bumped")
    if not isinstance(identity.get("platform"), dict):
        fail("proof identity omitted platform identity")
    dependencies = identity.get("dependencies")
    if not isinstance(dependencies, dict):
        fail("proof identity omitted dependency identity")
    descriptors = dependencies.get("descriptors")
    trees = dependencies.get("trees")
    if not isinstance(descriptors, dict) or not isinstance(trees, dict):
        fail("proof identity omitted dependency descriptors or tree digests")
    if not isinstance(descriptors.get("package-lock.json"), dict):
        fail("proof identity omitted package lock identity")
    if not isinstance(trees.get("node_modules"), str):
        fail("proof identity omitted installed dependency tree digest")
    runtimes = identity.get("runtimes")
    if not isinstance(runtimes, dict) or not runtimes:
        fail("proof identity omitted runtime identity")
    for value in runtimes.values():
        if value is not None and not isinstance(value, dict):
            fail("runtime identity has an invalid shape")
        if value is not None and not isinstance(value.get("sha256"), str):
            fail("runtime identity omitted executable content hash")
    environment = identity.get("environment")
    if not isinstance(environment, dict):
        fail("proof identity omitted environment allowlist")
    for value in environment.values():
        if value is not None and not isinstance(value, dict):
            fail("environment identity has an invalid shape")
        if value is not None and "value" in value:
            fail("proof identity cached an environment value")


def check_content_hash(module) -> None:
    with tempfile.TemporaryDirectory(prefix="skill-contract-identity-") as temporary:
        path = Path(temporary) / "runtime"
        path.write_bytes(b"first")
        first = module.file_identity(path)
        path.write_bytes(b"second")
        second = module.file_identity(path)
    if first["sha256"] == second["sha256"]:
        fail("runtime content changes did not change the proof identity")


def check_dependency_root_symlink(module) -> None:
    with tempfile.TemporaryDirectory(prefix="skill-contract-tree-") as temporary:
        fixture = Path(temporary)
        repository = fixture / "repo"
        external = fixture / "external"
        repository.mkdir()
        external.mkdir()
        payload = external / "payload"
        payload.write_bytes(b"first")
        root = repository / "node_modules"
        root.symlink_to(external, target_is_directory=True)
        original_root = module.ROOT
        module.ROOT = repository
        try:
            try:
                module.dependency_tree_digest(root, time.monotonic() + 5)
            except OSError:
                rejected = True
            else:
                rejected = False
        finally:
            module.ROOT = original_root
    if not rejected:
        fail("dependency identity accepted a symlinked root")


def check_dependency_content(module) -> None:
    with tempfile.TemporaryDirectory(prefix="skill-contract-dependency-") as temporary:
        repository = Path(temporary)
        root = repository / "node_modules"
        root.mkdir()
        payload = root / "package.js"
        payload.write_bytes(b"first")
        original_root = module.ROOT
        module.ROOT = repository
        try:
            first = module.dependency_tree_digest(root, time.monotonic() + 5)
            payload.write_bytes(b"second")
            second = module.dependency_tree_digest(root, time.monotonic() + 5)
            try:
                module.dependency_tree_digest(root, time.monotonic() - 1)
            except TimeoutError:
                pass
            else:
                fail("dependency identity ignored its whole-run deadline")
        finally:
            module.ROOT = original_root
    if first == second:
        fail("dependency content changes did not change the proof identity")


def check_environment_identity(module) -> None:
    name = "PYTHONHASHSEED"
    original = os.environ.get(name)
    try:
        os.environ[name] = "first-sensitive-value"
        first = module._safe_environment_identity()
        os.environ[name] = "second-sensitive-value"
        second = module._safe_environment_identity()
    finally:
        if original is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = original
    if first[name] == second[name]:
        fail("environment changes did not change the proof identity")
    rendered = repr((first, second))
    if "first-sensitive-value" in rendered or "second-sensitive-value" in rendered:
        fail("proof identity exposed an environment value")


def main() -> int:
    module = load_checker()
    check_identity(module)
    check_content_hash(module)
    check_dependency_root_symlink(module)
    check_dependency_content(module)
    check_environment_identity(module)
    print("skill-contract-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
