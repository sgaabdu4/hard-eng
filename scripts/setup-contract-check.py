#!/usr/bin/env python3
"""Deterministic setup supply-chain regressions."""

# Size exception: dense contract cases for one installation surface.

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/he/scripts"))
sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))

from bounded_run import run_captured


def fail(message: str) -> NoReturn:
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


def check_setup_manifest() -> None:
    manifest_path = ROOT / "scripts/setup/manifest.json"
    manifest_tool = ROOT / "scripts/setup/manifest.py"
    if not manifest_path.is_file() or not manifest_tool.is_file():
        fail("setup manifest owner missing")
    result = subprocess.run(
        [sys.executable, str(manifest_tool), "validate"], capture_output=True, text=True, check=False
    )
    if result.returncode or result.stdout.strip() != "setup:manifest: PASS":
        fail(result.stderr.strip() or "setup manifest validation failed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    specification = importlib.util.spec_from_file_location("setup_manifest_contract", manifest_tool)
    if specification is None or specification.loader is None:
        fail("setup manifest validator could not be loaded")
    validator = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(validator)
    for label, mutate in (
        ("leading-zero", lambda value: value["requirements"].__setitem__("node_min", "026.0.0")),
        ("prerelease", lambda value: value["requirements"].__setitem__("node_min", "26.0.0-rc.1")),
        ("build-metadata", lambda value: value["requirements"].__setitem__("node_min", "26.0.0+local")),
    ):
        candidate = json.loads(json.dumps(manifest))
        mutate(candidate)
        try:
            validator.validate(candidate)
        except SystemExit:
            pass
        else:
            fail(f"setup manifest accepted {label} as a stable semantic version")
    runtime = json.loads((ROOT / "runtime/npm/package.json").read_text(encoding="utf-8"))
    expected_dependencies = {package["name"]: package["version"] for package in manifest["npm_runtime"]["packages"]}
    if runtime.get("dependencies") != expected_dependencies:
        fail("npm runtime dependencies drifted from setup manifest")
    lock = json.loads((ROOT / "runtime/npm/package-lock.json").read_text(encoding="utf-8"))
    locked_root = lock.get("packages", {}).get("", {}).get("dependencies")
    if locked_root != expected_dependencies:
        fail("npm lock root dependencies drifted from setup manifest")


def check_tree_digest() -> None:
    digest = load_digest()
    with tempfile.TemporaryDirectory(prefix="hard-eng-runtime-digest-") as temporary:
        root = Path(temporary) / "runtime"
        root.mkdir()
        nested = root / "node_modules/dependency"
        nested.mkdir(parents=True)
        target = nested / "index.js"
        target.write_text("one\n", encoding="utf-8")
        baseline = digest(root)
        root.chmod(0o750)
        if digest(root) == baseline:
            fail("runtime root mode mutation escaped digest")
        root.chmod(0o755)
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
        actual = root.with_name("runtime-actual")
        root.rename(actual)
        root.symlink_to(actual, target_is_directory=True)
        try:
            digest(root)
        except ValueError:
            pass
        else:
            fail("symlink runtime root was accepted")
        cli = subprocess.run(
            [sys.executable, str(ROOT / "scripts/runtime-tree-digest.py"), str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
        if cli.returncode == 0:
            fail("runtime digest CLI followed a symlink root")
        if "Traceback" in cli.stderr or "runtime-tree-digest: FAIL:" not in cli.stderr:
            fail("runtime digest CLI did not return a typed symlink-root error")


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


def run_path_install(home: Path, shell: str, *, path_prefix: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["SHELL"] = f"/bin/{shell}"
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"
    return subprocess.run(
        ["bash", str(ROOT / "scripts/setup/path.sh"), "install"], capture_output=True, text=True, check=False, env=env
    )


def check_path_convergence() -> None:
    start_marker = "# >>> hard-eng managed PATH >>>"
    end_marker = "# <<< hard-eng managed PATH <<<"
    for shell, profile_name in (("zsh", ".zshrc"), ("bash", ".bashrc"), ("fish", ".config/fish/config.fish")):
        with tempfile.TemporaryDirectory(prefix=f"hard-eng-{shell}-path-") as temporary:
            home = Path(temporary)
            result = run_path_install(home, shell)
            if result.returncode:
                fail(result.stderr.strip() or f"{shell} PATH install failed")
            profile = home / profile_name
            content = profile.read_text(encoding="utf-8")
            if content.count(start_marker) != 1 or content.count(end_marker) != 1:
                fail(f"{shell} PATH block missing or duplicated")
            before = profile.read_bytes()
            rerun = run_path_install(home, shell)
            if rerun.returncode or profile.read_bytes() != before:
                fail(f"{shell} PATH rerun changed a converged profile")
            checked = subprocess.run(
                ["bash", str(ROOT / "scripts/setup/path.sh"), "check"],
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "HOME": str(home),
                    "SHELL": f"/bin/{shell}",
                    "XDG_CONFIG_HOME": str(home / ".config"),
                },
            )
            if checked.returncode or profile.read_bytes() != before:
                fail(f"{shell} PATH check changed or rejected a converged profile")
            executable = shutil.which(shell)
            if executable is None:
                fail(f"{shell} is required for native PATH fixture parsing")
            source_command = (
                f"source {shlex.quote(str(profile))}; string join : $PATH"
                if shell == "fish"
                else f"source {shlex.quote(str(profile))}; printf '%s' \"$PATH\""
            )
            sourced = subprocess.run(
                [executable, "--no-config", "-c", source_command]
                if shell == "fish"
                else [executable, "-f", "-c", source_command],
                capture_output=True,
                text=True,
                check=False,
                env={"HOME": str(home), "PATH": f"/usr/bin:{home}/.local/bin:/bin"},
            )
            if sourced.returncode or not sourced.stdout.startswith(f"{home}/.local/bin:"):
                fail(f"{shell} managed bin directory is not first in PATH")

    with tempfile.TemporaryDirectory(prefix="hard-eng-path-repair-") as temporary:
        home = Path(temporary)
        profile = home / ".zshrc"
        original = f'export USER_SETTING=keep\n{start_marker}\nexport PATH="/obsolete:$PATH"\n{end_marker}\n'
        profile.write_text(original, encoding="utf-8")
        profile.chmod(0o640)
        result = run_path_install(home, "zsh")
        if result.returncode:
            fail(result.stderr.strip() or "owned PATH block repair failed")
        repaired = profile.read_text(encoding="utf-8")
        if "export USER_SETTING=keep\n" not in repaired or "/obsolete" in repaired:
            fail("owned PATH repair changed user content or retained stale content")
        if profile.stat().st_mode & 0o777 != 0o640:
            fail("owned PATH repair changed profile mode")
        backup_dir = home / ".local/share/hard-eng/backups/shell"
        backups = tuple(backup_dir.glob(".zshrc.*"))
        if len(backups) != 1 or backups[0].read_text(encoding="utf-8") != original:
            fail("owned PATH repair did not preserve one exact backup")
        if backup_dir.stat().st_mode & 0o777 != 0o700:
            fail("profile backup directory is not private")
        if backups[0].stat().st_mode & 0o777 != 0o600:
            fail("profile backup is not private")

    with tempfile.TemporaryDirectory(prefix="hard-eng-path-conflict-") as temporary:
        home = Path(temporary)
        profile = home / ".zshrc"
        malformed = f"keep\n{start_marker}\nunclosed\n"
        profile.write_text(malformed, encoding="utf-8")
        result = run_path_install(home, "zsh")
        if result.returncode == 0 or profile.read_text(encoding="utf-8") != malformed:
            fail("malformed managed PATH block was not preserved and rejected")

    with tempfile.TemporaryDirectory(prefix="hard-eng-path-concurrent-") as temporary:
        home = Path(temporary)
        profile = home / ".zshrc"
        original = "export USER_SETTING=keep\n"
        profile.write_text(original, encoding="utf-8")
        (home / ".hard-eng-path.lock").mkdir()
        result = run_path_install(home, "zsh")
        if result.returncode == 0 or profile.read_text(encoding="utf-8") != original:
            fail("concurrent PATH convergence was not rejected without mutation")

    with tempfile.TemporaryDirectory(prefix="hard-eng-path-stale-lock-") as temporary:
        home = Path(temporary)
        profile = home / ".zshrc"
        profile.write_text("export USER_SETTING=keep\n", encoding="utf-8")
        lock = home / ".hard-eng-path.lock"
        lock.mkdir()
        (lock / "owner.json").write_text(json.dumps({"pid": 99999999, "start": "stale"}) + "\n", encoding="utf-8")
        result = run_path_install(home, "zsh")
        if result.returncode != 0 or lock.exists():
            fail("stale PATH convergence lock did not recover safely")

    with tempfile.TemporaryDirectory(prefix="hard-eng-path-rollback-") as temporary:
        home = Path(temporary)
        profile = home / ".zshrc"
        original = "export USER_SETTING=keep\n"
        profile.write_text(original, encoding="utf-8")
        fake_bin = home / "fake-bin"
        fake_bin.mkdir()
        fake_mv = fake_bin / "mv"
        fake_mv.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
        fake_mv.chmod(0o755)
        result = run_path_install(home, "zsh", path_prefix=fake_bin)
        if result.returncode == 0 or profile.read_text(encoding="utf-8") != original:
            fail("failed PATH commit changed the original profile")

    with tempfile.TemporaryDirectory(prefix="hard-eng-path-user-edit-") as temporary:
        home = Path(temporary)
        profile = home / ".zshrc"
        original = "export USER_SETTING=keep\n"
        profile.write_text(original, encoding="utf-8")
        fake_bin = home / "fake-bin"
        fake_bin.mkdir()
        fake_cp = fake_bin / "cp"
        fake_cp.write_text(
            "#!/bin/sh\n/bin/cp \"$@\"\nprintf '%s\\n' 'export USER_EDIT=preserved' >> \"$HOME/.zshrc\"\n",
            encoding="utf-8",
        )
        fake_cp.chmod(0o755)
        result = run_path_install(home, "zsh", path_prefix=fake_bin)
        edited = profile.read_text(encoding="utf-8")
        if result.returncode == 0 or edited != original + "export USER_EDIT=preserved\n":
            fail("concurrent user profile edit was overwritten")


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


def run_setup_function(
    home: Path, body: str, *, path_prefix: Path | None = None, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["HOME"] = str(home)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"
    if extra_env:
        env.update(extra_env)
    script = (
        "set -eu\n"
        f"ROOT={shlex.quote(str(ROOT))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/common.sh'))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/binaries.sh'))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/npm-runtime.sh'))}\n"
        f"{body}\n"
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False, env=env)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_binary_activation() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-binary-conflict-") as temporary:
        home = Path(temporary)
        bin_dir = home / ".local/bin"
        bin_dir.mkdir(parents=True)
        destination = bin_dir / "jq"
        staged = bin_dir / ".hard-eng-jq.stage.test"
        destination.write_bytes(b"user-owned\n")
        staged.write_bytes(b"managed\n")
        result = run_setup_function(home, f"activate_binary jq {shlex.quote(str(staged))}")
        if result.returncode == 0:
            fail("unowned binary conflict was overwritten")
        if destination.read_bytes() != b"user-owned\n" or staged.read_bytes() != b"managed\n":
            fail("binary conflict changed existing or staged bytes")

    with tempfile.TemporaryDirectory(prefix="hard-eng-binary-adopt-") as temporary:
        home = Path(temporary)
        bin_dir = home / ".local/bin"
        bin_dir.mkdir(parents=True)
        destination = bin_dir / "jq"
        staged = bin_dir / ".hard-eng-jq.stage.test"
        destination.write_bytes(b"reviewed-pin\n")
        staged.write_bytes(b"reviewed-pin\n")
        result = run_setup_function(home, f"activate_binary jq {shlex.quote(str(staged))}")
        receipt = home / ".local/share/hard-eng/state/binary-jq.sha256"
        if result.returncode or not receipt.is_file():
            fail(result.stderr.strip() or "exact existing binary was not adopted")
        if receipt.read_text(encoding="ascii").strip() != file_sha256(destination):
            fail("adopted binary ownership receipt is incorrect")
        if staged.exists():
            fail("adopted binary left a staged file")

    with tempfile.TemporaryDirectory(prefix="hard-eng-binary-rollback-") as temporary:
        home = Path(temporary)
        bin_dir = home / ".local/bin"
        state_dir = home / ".local/share/hard-eng/state"
        bin_dir.mkdir(parents=True)
        state_dir.mkdir(parents=True)
        destination = bin_dir / "jq"
        staged = bin_dir / ".hard-eng-jq.stage.test"
        destination.write_bytes(b"previous-managed\n")
        staged.write_bytes(b"replacement\n")
        receipt = state_dir / "binary-jq.sha256"
        receipt.write_text(f"{file_sha256(destination)}\n", encoding="ascii")
        receipt.chmod(0o666)
        result = run_setup_function(home, f"activate_binary jq {shlex.quote(str(staged))}")
        if result.returncode == 0 or destination.read_bytes() != b"previous-managed\n":
            fail("failed binary receipt activation did not restore prior command")
        if receipt.read_text(encoding="ascii").strip() != file_sha256(destination):
            fail("failed binary activation changed the prior ownership receipt")


def write_runtime_receipt(home: Path, runtime: Path) -> None:
    digest = load_digest()(runtime)
    receipt = home / ".local/share/hard-eng/state/npm-runtime.sha256"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(f"{digest}\n", encoding="ascii")


def check_npm_activation() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-npm-rollback-") as temporary:
        home = Path(temporary)
        asset_dir = home / ".local/share/hard-eng"
        runtime = asset_dir / "npm-runtime"
        staged = asset_dir / ".hard-eng-npm-stage.test"
        fake_bin = home / "fake-bin"
        (home / ".local/bin").mkdir(parents=True)
        runtime.mkdir(parents=True)
        staged.mkdir()
        fake_bin.mkdir()
        (runtime / "owner").write_text("previous\n", encoding="utf-8")
        (staged / "owner").write_text("replacement\n", encoding="utf-8")
        write_runtime_receipt(home, runtime)
        fake_ln = fake_bin / "ln"
        fake_ln.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
        fake_ln.chmod(0o755)
        result = run_setup_function(home, f"activate_npm_runtime {shlex.quote(str(staged))}", path_prefix=fake_bin)
        if result.returncode == 0:
            fail("injected npm link activation failure passed")
        if (runtime / "owner").read_text(encoding="utf-8") != "previous\n":
            fail("failed npm activation did not restore prior runtime")
        if any((home / ".local/bin").iterdir()):
            fail("failed npm activation left managed command links")

    with tempfile.TemporaryDirectory(prefix="hard-eng-npm-conflict-") as temporary:
        home = Path(temporary)
        asset_dir = home / ".local/share/hard-eng"
        runtime = asset_dir / "npm-runtime"
        staged = asset_dir / ".hard-eng-npm-stage.test"
        bin_dir = home / ".local/bin"
        bin_dir.mkdir(parents=True)
        runtime.mkdir(parents=True)
        staged.mkdir()
        (runtime / "owner").write_text("previous\n", encoding="utf-8")
        (staged / "owner").write_text("replacement\n", encoding="utf-8")
        (bin_dir / "context-mode").write_text("user command\n", encoding="utf-8")
        write_runtime_receipt(home, runtime)
        result = run_setup_function(home, f"activate_npm_runtime {shlex.quote(str(staged))}")
        if result.returncode == 0:
            fail("unowned npm command conflict was overwritten")
        if (runtime / "owner").read_text(encoding="utf-8") != "previous\n":
            fail("npm command conflict changed the previous runtime")
        if (bin_dir / "context-mode").read_text(encoding="utf-8") != "user command\n":
            fail("npm command conflict changed user bytes")

    with tempfile.TemporaryDirectory(prefix="hard-eng-npm-activate-") as temporary:
        home = Path(temporary)
        asset_dir = home / ".local/share/hard-eng"
        runtime = asset_dir / "npm-runtime"
        staged = asset_dir / ".hard-eng-npm-stage.test"
        (home / ".local/bin").mkdir(parents=True)
        asset_dir.mkdir(parents=True)
        staged.mkdir()
        (staged / "owner").write_text("replacement\n", encoding="utf-8")
        result = run_setup_function(home, f"activate_npm_runtime {shlex.quote(str(staged))}")
        if result.returncode:
            fail(result.stderr.strip() or "npm activation failed")
        if (runtime / "owner").read_text(encoding="utf-8") != "replacement\n":
            fail("npm activation did not publish the staged runtime")
        for name in ("codebase-memory-mcp", "context-mode", "ctx7"):
            link = home / ".local/bin" / name
            expected = runtime / "node_modules/.bin" / name
            if not link.is_symlink() or os.readlink(link) != str(expected):
                fail(f"npm activation did not create the canonical {name} link")
        receipt = asset_dir / "state/npm-runtime.sha256"
        if receipt.read_text(encoding="ascii").strip() != load_digest()(runtime):
            fail("npm activation receipt does not match the published runtime")


def check_scoped_cleanup() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-cleanup-scope-") as temporary:
        home = Path(temporary)
        asset_dir = home / ".local/share/hard-eng"
        protected = home / "protected"
        asset_dir.mkdir(parents=True)
        protected.mkdir()
        sentinel = protected / "sentinel"
        sentinel.write_text("preserve\n", encoding="utf-8")
        traversal = asset_dir / ".hard-eng-stage/../../../protected"
        result = run_setup_function(home, f"safe_remove_setup_tree {shlex.quote(str(traversal))}")
        if result.returncode == 0 or sentinel.read_text(encoding="utf-8") != "preserve\n":
            fail("scoped setup cleanup accepted a traversal target")


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
    checker = workflow_paths[0].read_text(encoding="utf-8")
    required_checker = (
        "npm ci --ignore-scripts",
        "project_gate.py phase",
        "--phase ci",
        "fetch-depth: 0",
        "FALLOW_AUDIT_BASE",
        'PUSH_BEFORE" =~ ^0+$',
    )
    if any(anchor not in checker for anchor in required_checker):
        fail("contract CI omits pinned repository quality gates")

    updater = workflow_paths[1].read_text(encoding="utf-8")
    ordered = (
        "worktree.py --repo . --intent write",
        "./scripts/update-managed-skills.sh --ci",
        "git add -- .skill-lock.json skills",
        "git diff --cached --check",
        "./scripts/git-hooks/publish-gate.sh push",
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
    )
    missing = tuple(anchor for anchor in required if anchor not in aggregate)
    if missing:
        fail(f"aggregate gate wiring missing: {missing}")
    manifest = (ROOT / "hard-eng.gates.json").read_text(encoding="utf-8")
    required_tests = (
        '"skills/appwrite-backend/scripts/appwrite-query-contract.test.mjs"',
        '"skills/appwrite-backend/scripts/appwrite-schema-guard.test.mjs"',
        '"skills/appwrite-backend/scripts/skill-safety-contract.test.mjs"',
    )
    missing_tests = tuple(anchor for anchor in required_tests if anchor not in manifest)
    if missing_tests:
        fail(f"manifest test gate wiring missing: {missing_tests}")


def check_claude_output_style() -> None:
    style = (ROOT / "output-styles/plain-english.md").read_text(encoding="utf-8")
    front = style.split("---", 2)
    if len(front) < 3 or front[0].strip() != "":
        fail("canonical output style has no frontmatter block")
    skill_path = ROOT / "skills/plain-english/SKILL.md"
    if not skill_path.is_file():
        fail("canonical plain-English skill is missing")
    skill_front = skill_path.read_text(encoding="utf-8").split("---", 2)
    if len(skill_front) < 3 or skill_front[0].strip() != "":
        fail("canonical plain-English skill has no frontmatter block")
    if skill_front[2].strip() != front[2].strip():
        fail("plain-English skill and Claude output style differ")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    if "- Every user-facing reply → read + follow `plain-english`" not in agents:
        fail("global agent rules do not route replies through plain-english")
    declared = {
        key.strip(): value.strip()
        for key, _, value in (line.partition(":") for line in front[1].splitlines())
        if key.strip()
    }
    if declared.get("keep-coding-instructions") != "true":
        fail("canonical output style drops the built-in engineering instructions")
    name = declared.get("name")
    if not name:
        fail("canonical output style declares no name")
    settings = (ROOT / "scripts/setup/claude-settings.py").read_text(encoding="utf-8")
    if f'OUTPUT_STYLE = "{name}"' not in settings:
        fail(f"settings owner does not select the canonical output style: {name}")
    if '"outputStyle"' not in settings:
        fail("settings owner does not converge the outputStyle key")
    owner = (ROOT / "scripts/setup/claude.sh").read_text(encoding="utf-8")
    required = (
        "CANONICAL_OUTPUT_STYLES=$HOME/.agents/output-styles",
        '[ "$CANONICAL_OUTPUT_STYLES" -ef "$ROOT/output-styles" ]',
        'ln -s "$CANONICAL_OUTPUT_STYLES" "$CLAUDE_OUTPUT_STYLES"',
        'rm -f -- "$CLAUDE_OUTPUT_STYLES"',
        "claude_output_styles_status || return 1\n",
    )
    if any(anchor not in owner for anchor in required):
        fail("Claude output styles are not delivered as a rolled-back canonical link")


def node_stub(directory: Path, version: str) -> Path:
    real = shutil.which("node")
    if real is None:
        fail("node is required to prove the Node floor")
    directory.mkdir(parents=True, exist_ok=True)
    stub = directory / "node"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import subprocess, sys\n"
        f"prelude = \"Object.defineProperty(process.versions,'node',{{value:{version!r}}});\"\n"
        f"sys.exit(subprocess.run([{real!r}, '-e', prelude + sys.argv[2]]).returncode)\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return directory


def check_single_node_floor() -> None:
    manifest = json.loads((ROOT / "scripts/setup/manifest.json").read_text(encoding="utf-8"))
    floor = manifest["requirements"]["node_min"]
    major = floor.split(".")[0]
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    if package.get("engines", {}).get("node") != f">={floor}":
        fail(f"package.json states a Node floor other than the manifest one: >={floor}")
    lock = json.loads((ROOT / "package-lock.json").read_text(encoding="utf-8"))
    if lock["packages"][""].get("engines", {}).get("node") != f">={floor}":
        fail(f"package-lock root states a Node floor other than the manifest one: >={floor}")
    for name in ("check-skill-contracts.yml", "update-managed-skills.yml"):
        workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        if f"node-version: {major}\n" not in workflow:
            fail(f"{name} does not run the repository checks on Node {major}")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    if "process.versions.node" in setup:
        fail("setup.sh states its own Node floor instead of proving the manifest one")
    runtime = (ROOT / "scripts/setup/npm-runtime.sh").read_text(encoding="utf-8")
    if runtime.count("manifest get requirements.node_min") != 1:
        fail("the Node floor has more than one reader in the setup runtime")
    for owner in ("install_tools", "check_tools"):
        body = setup.partition(f"{owner}() {{")[2].partition("\n}\n")[0]
        if "check_node_version" not in body:
            fail(f"setup {owner} does not prove the Node floor")
    with tempfile.TemporaryDirectory(prefix="hard-eng-node-floor-") as temporary:
        home = Path(temporary)
        below = f"{int(major) - 1}.99.99"
        result = run_setup_function(home, "check_node_version", path_prefix=node_stub(home / "below", below))
        if not result.returncode or f"Node.js {floor}+ is required" not in result.stderr:
            fail(f"setup accepted Node {below}, under its own floor of {floor}")
        result = run_setup_function(home, "check_node_version", path_prefix=node_stub(home / "at", floor))
        if result.returncode:
            fail(f"setup rejected Node {floor}, exactly its own floor")


def check_external_commands_are_bounded() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-bounded-") as temporary:
        home = Path(temporary)
        started = time.monotonic()
        result = run_setup_function(home, "bounded_setup_run 1 sleep 120")
        if result.returncode != 124 or time.monotonic() - started > 20:
            fail("setup does not stop an external command that never answers")
        if "did not answer within 1s: sleep 120" not in result.stderr:
            fail("a stalled setup command is not named in the failure")
        result = run_setup_function(home, "bounded_setup_run 60 sh -c 'echo why >&2; exit 7'")
        if result.returncode != 7 or "why" not in result.stderr:
            fail("bounded setup runs discard the failing command's own diagnostics")
        result = run_setup_function(home, "bounded_setup_run 60 true")
        if result.returncode or result.stdout.strip() or result.stderr.strip():
            fail("bounded setup runs are not silent when the command succeeds")
    checks = (ROOT / "setup.sh").read_text(encoding="utf-8")
    body = checks.partition("check_tools() {")[2].partition("\n}\n")[0]
    if "check_npm_runtime" not in body:
        fail("could not read the setup check body")
    externals = {"node", "npm", "context-mode", "ctx7", "rtk", "codex", "curl", "tar", "jq"}
    for line in body.splitlines():
        statement = line.strip()
        if statement.startswith("#") or "bounded_setup_run" in statement:
            continue
        words = statement.split(maxsplit=1)
        if words and words[0] in externals:
            fail(f"setup check runs an unbounded external command: {statement}")
    runtime = (ROOT / "scripts/setup/npm-runtime.sh").read_text(encoding="utf-8")
    spawns = ("context-mode-runtime-check.mjs", "cli list_projects")
    for line in runtime.splitlines():
        statement = line.strip()
        if "bounded_setup_run" in statement:
            continue
        if any(spawn in statement for spawn in spawns):
            fail(f"npm runtime check runs an unbounded external command: {statement}")


def main() -> int:
    setup_scripts = (
        ROOT / "setup.sh",
        ROOT / "scripts/setup/common.sh",
        ROOT / "scripts/setup/binaries.sh",
        ROOT / "scripts/setup/npm-runtime.sh",
        ROOT / "scripts/setup/path.sh",
        ROOT / "scripts/setup/claude.sh",
        ROOT / "scripts/setup/copilot.sh",
    )
    for setup_script in setup_scripts:
        result = subprocess.run(["bash", "-n", str(setup_script)], check=False)
        if result.returncode:
            fail(f"{setup_script.relative_to(ROOT)} syntax")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    required_dispatch = (
        "scripts/setup/common.sh",
        "scripts/setup/binaries.sh",
        "scripts/setup/npm-runtime.sh",
        "scripts/setup/codex.sh",
        "scripts/setup/claude.sh",
        "scripts/setup/update.py",
        "PYTHONDONTWRITEBYTECODE=1",
        "install_npm_runtime",
        "npm ci --ignore-scripts",
        "check_node_version",
        "install_binary_pins",
        "install_codex_integration",
        "install_claude_integration",
        "install_copilot_integration",
        "install_managed_directories",
        "check_npm_runtime",
        "npm ls --all",
        "check_binary_pins",
        "check_codex_integration",
        "check_claude_integration",
        "check_copilot_integration",
        "check_managed_directories",
        '"$ROOT/DESIGN.md"',
        'python3 "$ROOT/scripts/setup/update.py" "$@"',
        '"$ROOT/scripts/setup/path.sh" "$PATH_ACTION"',
        "skills/deterministic-checks/scripts/bounded_run.py",
        "--timeout 600 -- python3",
    )
    if any(item not in setup for item in required_dispatch):
        fail("setup dispatcher is not wired to every component owner")
    component_source = "\n".join(path.read_text(encoding="utf-8") for path in setup_scripts[1:4])
    common_source = setup_scripts[1].read_text(encoding="utf-8")
    if 'setup_fail "download failed: $url"' in common_source or (
        'setup_fail "checksum mismatch: $url"' in common_source
    ):
        fail("setup download failure can disclose a credential-bearing URL")
    required_runtime = (
        "npm ci $offline --cache",
        "--offline",
        "runtime_tree_digest",
        "context-mode-runtime-check.mjs",
        "context-mode-runtime.py",
        "context_mode_runtime_patch",
        "npm-remove-paths",
        "activate_npm_runtime",
        "rollback_npm_activation",
        "validate_prepared_npm_runtime",
        "check_codebase_memory_cli",
        "validate_staged_binary",
        "activate_binary",
    )
    if any(item not in component_source for item in required_runtime):
        fail("transactional pinned component contract missing")
    manifest = json.loads((ROOT / "scripts/setup/manifest.json").read_text(encoding="utf-8"))
    context_package = next(
        package for package in manifest["npm_runtime"]["packages"] if package["name"] == "context-mode"
    )
    if "ensure-deps.mjs" not in context_package["tree_exclusions"]:
        fail("Context Mode runtime overlay is not excluded from archive comparison")
    overlay = ROOT / "scripts/setup/context-mode-runtime.py"
    overlay_source = overlay.read_text(encoding="utf-8")
    if "hasUsableBuiltinSqlite" not in overlay_source or "fts5(body)" not in overlay_source:
        fail("Context Mode runtime overlay does not prove built-in FTS5 support")
    if any(version in component_source for version in ("0.8.1", "1.0.169", "0.5.4", "0.43.0", "1.7.1")):
        fail("component owner duplicates a manifest version pin")
    install_order = (
        "\n    install_tools\n",
        '"$ROOT/scripts/git-hooks/install.sh" install',
        "\ncheck_tools\n",
        'node "$ROOT/scripts/check-managed-skills.js"',
        '"$ROOT/scripts/setup/path.sh" "$PATH_ACTION"',
        "printf 'setup: PASS\\n'",
    )
    positions = tuple(setup.find(anchor) for anchor in install_order)
    if any(position < 0 for position in positions) or positions != tuple(sorted(positions)):
        fail("managed PATH is not the final converged install step")
    required_reconstruction = (
        'prepare_npm_runtime "$staged" install "$NPM_CACHE_DIR"',
        'prepare_npm_runtime "$temporary" check "$cache"',
        'cp -R "$NPM_CACHE_DIR/." "$cache/"',
        'expected_tree=$(runtime_tree_digest "$temporary")',
        'actual_tree=$(runtime_tree_digest "$NPM_RUNTIME_DIR")',
    )
    npm_owner = (ROOT / "scripts/setup/npm-runtime.sh").read_text(encoding="utf-8")
    if any(item not in npm_owner for item in required_reconstruction):
        fail("runtime check does not reconstruct the complete locked tree")
    if 'prepare_npm_runtime "$temporary" check "$NPM_CACHE_DIR"' in npm_owner:
        fail("runtime check mutates the persistent npm cache")
    if "NPM_RUNTIME_MARKER" in npm_owner or "runtime_lock_digest" in npm_owner:
        fail("writable runtime marker is an authority")
    codex_owner = (ROOT / "scripts/setup/codex.sh").read_text(encoding="utf-8")
    if "rtk init" in codex_owner or "RTK.md" in codex_owner:
        fail("setup reintroduced RTK Codex init artifacts")
    if "codex_context_runtime_patch" not in codex_owner:
        fail("Codex Context Mode runtime overlay is not wired")
    if "codex --version" in setup:
        fail("read-only setup check launches Codex outside its scratch mirror")
    repository_policy = (ROOT / "AGENTS.override.md").read_text(encoding="utf-8")
    publish_gate = (ROOT / "scripts/git-hooks/publish-gate.sh").read_text(encoding="utf-8")
    if (
        "`scripts/git-hooks/publish-gate.sh commit|push` respectively" not in repository_policy
        or "--timeout 180 --phase commit" not in publish_gate
        or "--timeout 300 --phase push" not in publish_gate
    ):
        fail("publish contract invokes the aggregate without a whole-run timeout")
    contracts = sorted(ROOT.glob("scripts/setup-*-contract-check.*"))
    with ThreadPoolExecutor(max_workers=len(contracts)) as pool:
        pending = [pool.submit(run_captured, [str(contract)], 600, 2, str(ROOT)) for contract in contracts]
        check_lock()
        check_setup_manifest()
        check_tree_digest()
        check_plan_safe_write()
        check_path_convergence()
        check_corrupt_archive_rejected()
        check_binary_activation()
        check_npm_activation()
        check_scoped_cleanup()
        check_ci_contracts()
        check_claude_output_style()
        check_external_commands_are_bounded()
        check_single_node_floor()
    for contract, future in zip(contracts, pending):
        result = future.result()
        if result.returncode:
            fail(result.stderr.decode("utf-8", "replace").strip() or f"{contract.name} failed")
    runtime_check = ROOT / "scripts/context-mode-runtime-check.mjs"
    if not runtime_check.is_file() or "fts5" not in runtime_check.read_text(encoding="utf-8").lower():
        fail("context-mode functional SQLite/FTS5 proof missing")
    print("setup-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
