#!/usr/bin/env python3
"""Deterministic setup supply-chain regressions."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/he/scripts"))


def fail(message: str) -> None:
    raise SystemExit(f"setup-contract: FAIL: {message}")


def load_digest():
    path = ROOT / "scripts/runtime-tree-digest.py"
    spec = importlib.util.spec_from_file_location("runtime_tree_digest", path)
    if spec is None or spec.loader is None:
        fail("runtime digest module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tree_digest


def locked_version(packages: dict, name: str) -> tuple[int, int, int]:
    metadata = packages.get(f"node_modules/{name}")
    value = metadata.get("version") if isinstance(metadata, dict) else None
    if not isinstance(value, str):
        fail(f"locked npm dependency missing: {name}")
    try:
        parts = tuple(int(part) for part in value.split("-", 1)[0].split("."))
    except ValueError:
        fail(f"invalid locked npm version: {name}={value}")
    if len(parts) != 3:
        fail(f"invalid locked npm version: {name}={value}")
    return parts


def check_lock() -> None:
    manifest = json.loads((ROOT / "runtime/npm/package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "runtime/npm/package-lock.json").read_text(encoding="utf-8"))
    packages = lock.get("packages")
    if not isinstance(packages, dict) or not packages:
        fail("npm lock package closure missing")
    for name, metadata in packages.items():
        if not name:
            continue
        if not isinstance(metadata, dict) or not metadata.get("resolved") or not metadata.get("integrity"):
            fail(f"unpinned npm dependency: {name}")
    hono = locked_version(packages, "@hono/node-server")
    fast_uri = locked_version(packages, "fast-uri")
    override = manifest.get("overrides", {}).get("@hono/node-server")
    if override != ".".join(str(part) for part in hono):
        fail("@hono/node-server override and lock resolution differ")
    if not ((2, 0, 5) <= hono < (3, 0, 0)):
        fail("@hono/node-server resolution includes GHSA-frvp-7c67-39w9")
    if not ((3, 1, 4) <= fast_uri < (4, 0, 0)):
        fail("fast-uri resolution includes GHSA-v2hh-gcrm-f6hx")


def check_tree_digest() -> None:
    digest = load_digest()
    with tempfile.TemporaryDirectory(prefix="hard-eng-runtime-digest-") as temporary:
        root = Path(temporary)
        nested = root / "node_modules/dependency"
        nested.mkdir(parents=True)
        target = nested / "index.js"
        target.write_text("one\n", encoding="utf-8")
        baseline = digest(root)
        target.write_text("two\n", encoding="utf-8")
        if digest(root) == baseline:
            fail("nested dependency mutation escaped runtime digest")
        marker = root.parent / "npm-runtime.sha256"
        marker.write_text(baseline, encoding="ascii")
        if marker.read_text(encoding="ascii") == digest(root):
            fail("writable marker remained authoritative after runtime mutation")
        target.write_text("one\n", encoding="utf-8")
        target.chmod(0o755)
        if digest(root) == baseline:
            fail("runtime mode mutation escaped digest")
        target.chmod(0o644)
        link = root / "command"
        os.symlink("node_modules/dependency/index.js", link)
        linked = digest(root)
        link.unlink()
        os.symlink("wrong-target", link)
        if digest(root) == linked:
            fail("runtime symlink mutation escaped digest")


def check_plan_safe_write() -> None:
    scripts = ROOT / "skills/he/scripts"
    sys.path.insert(0, str(scripts))
    import safe_plan_io
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-io-") as temporary:
        repo = Path(temporary)
        relative = Path("features/example/PLAN.md")
        target = repo / relative
        safe_plan_io.create_new(repo, relative, b"first\n", 0o640)
        before, mode = safe_plan_io.read_snapshot(repo, relative)
        safe_plan_io.replace_if_unchanged(repo, relative, before, mode, b"second\n")
        if target.read_bytes() != b"second\n" or (target.stat().st_mode & 0o777) != 0o640:
            fail("safe PLAN writer did not replace the complete document and preserve mode")
        try:
            safe_plan_io.replace_if_unchanged(repo, relative, before, mode, b"stale\n")
        except safe_plan_io.SafePlanIOError:
            pass
        else:
            fail("safe PLAN writer accepted a stale byte preimage")
        if target.read_bytes() != b"second\n":
            fail("stale PLAN write changed the document")
        if tuple(target.parent.glob(".hard-eng-*")):
            fail("safe PLAN writer leaked a temporary file")


def check_corrupt_archive_rejected() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-corrupt-archive-") as temporary:
        archive = Path(temporary) / "package.tgz"
        content = b"corrupt archive\n"
        archive.write_bytes(content)
        result = subprocess.run(
            ["bash", str(ROOT / "setup.sh"), "npm-archive-check", str(archive), "0" * 128],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            fail("corrupted pinned archive passed check")
        if archive.read_bytes() != content:
            fail("archive check repaired corrupted evidence")


def check_ci_contracts() -> None:
    pins = {
        "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
        "actions/setup-node": ("820762786026740c76f36085b0efc47a31fe5020", "v7.0.0"),
    }
    workflow_paths = (
        ROOT / ".github/workflows/check-skill-contracts.yml",
        ROOT / ".github/workflows/update-managed-skills.yml",
    )
    for path in workflow_paths:
        workflow = path.read_text(encoding="utf-8")
        for action, (revision, version) in pins.items():
            if f"uses: {action}@{revision} # {version}" not in workflow:
                fail(f"{path.name} does not pin {action} to the reviewed full SHA")

    updater = workflow_paths[1].read_text(encoding="utf-8")
    ordered = (
        "git add -- .skill-lock.json skills",
        "git diff --cached --check",
        "worktree.py --repo . --intent publish",
        "bounded_run.py --timeout 600 -- python3 scripts/check-skill-contracts.py",
        "check-design-md.js",
        "check-managed-skills.js",
        'git commit -m "chore: update managed skills"',
        'test -z "$(git status --porcelain=v1 --untracked-files=all)"',
        'git push --dry-run origin "HEAD:${{ github.event.repository.default_branch }}"',
        'git push origin "HEAD:${{ github.event.repository.default_branch }}"',
    )
    positions = tuple(updater.find(anchor) for anchor in ordered)
    if any(position < 0 for position in positions) or positions != tuple(sorted(positions)):
        fail("managed updater does not run every publish gate before commit and push")

    aggregate = (ROOT / "scripts/check-skill-contracts.py").read_text(encoding="utf-8")
    required = (
        '"skills/deterministic-checks/scripts/context-docs.py", "--repo", "."',
        '"scripts/skill-package-contracts-regression.py"',
        '"scripts/skill-package-contracts.py"',
        '"skills/appwrite-backend/scripts/appwrite-query-contract.test.mjs"',
        '"skills/appwrite-backend/scripts/appwrite-schema-guard.test.mjs"',
        '"skills/appwrite-backend/scripts/skill-safety-contract.test.mjs"',
    )
    missing = tuple(anchor for anchor in required if anchor not in aggregate)
    if missing:
        fail(f"aggregate gate wiring missing: {missing}")


def main() -> int:
    result = subprocess.run(["bash", "-n", str(ROOT / "setup.sh")], check=False)
    if result.returncode:
        fail("setup.sh syntax")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    required = (
        "npm ci $offline --cache", "--offline", "check_npm_runtime",
        "runtime_tree_digest", "context-mode-runtime-check.mjs", "Node.js 22.5+",
        'rm -rf "$destination/node_modules/better-sqlite3"',
        'skills/deterministic-checks/scripts/bounded_run.py',
        "--timeout 600 -- python3",
    )
    if any(item not in setup for item in required):
        fail("locked script-free runtime contract missing")
    required_reconstruction = (
        'prepare_npm_runtime "$temporary" install "$NPM_CACHE_DIR"',
        'prepare_npm_runtime "$temporary" check "$cache"',
        'cp -R "$NPM_CACHE_DIR/." "$cache/"',
        'check) require_npm_archive',
        'expected_tree=$(runtime_tree_digest "$temporary")',
        'actual_tree=$(runtime_tree_digest "$NPM_RUNTIME_DIR")',
    )
    if any(item not in setup for item in required_reconstruction):
        fail("runtime check does not reconstruct the complete locked tree")
    if 'prepare_npm_runtime "$temporary" check "$NPM_CACHE_DIR"' in setup:
        fail("runtime check mutates the persistent npm cache")
    if "NPM_RUNTIME_MARKER" in setup or "runtime_lock_digest" in setup:
        fail("writable runtime marker is an authority")
    repository_policy = (ROOT / "AGENTS.override.md").read_text(encoding="utf-8")
    if (
        "skills/deterministic-checks/scripts/bounded_run.py --timeout 600"
        not in repository_policy
    ):
        fail("publish contract invokes the aggregate without a whole-run timeout")
    check_lock()
    check_tree_digest()
    check_plan_safe_write()
    check_corrupt_archive_rejected()
    check_ci_contracts()
    runtime_check = ROOT / "scripts/context-mode-runtime-check.mjs"
    if not runtime_check.is_file() or "fts5" not in runtime_check.read_text(encoding="utf-8").lower():
        fail("context-mode functional SQLite/FTS5 proof missing")
    print("setup-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
