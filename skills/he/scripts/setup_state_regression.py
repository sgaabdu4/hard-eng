#!/usr/bin/env python3
"""Regression contract for setup_state.py: probes, receipt lifecycle, memory refresh, checkout policy."""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SETUP_STATE = SCRIPT_DIR / "setup_state.py"
DETERMINISTIC_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(DETERMINISTIC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

from git_env import git_env, scrub_environ

scrub_environ()

BASE_PATH = "/usr/bin:/bin"
RUN_TIMEOUT = 120

FAKE_MEMORY_TOOL = """#!{python}
import json, subprocess, sys
from pathlib import Path

state = Path({state_file!r})
tool = sys.argv[2] if len(sys.argv) > 2 else ""
payload = json.loads(sys.stdin.read() or "{{}}")
if tool == "list_projects":
    projects = json.loads(state.read_text()) if state.is_file() else []
    print(json.dumps({{"projects": projects}}))
elif tool == "index_repository":
    root = payload.get("repo_path", "")
    head = subprocess.run(
        ["git", "-C", root, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    state.write_text(json.dumps([{{"root_path": root, "git": {{"head_sha": head}}}}]))
    print(json.dumps({{"status": "indexed"}}))
else:
    print("{{}}")
"""

VALID_MANIFEST = {
    "schema_version": 1,
    "enforcement": {"schema_version": 1, "required_paths": ["own.py"]},
    "families": {"targeted": ["python3", "own.py"]},
    "phases": {"commit": ["targeted"], "push": ["targeted"], "ci": ["targeted"]},
}


def load_setup_state():
    spec = importlib.util.spec_from_file_location("hard_eng_setup_state", SETUP_STATE)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL: cannot load setup_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition: object, label: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {label}")


def fixture_env(path: str = BASE_PATH) -> dict[str, str]:
    env = git_env()
    env["PATH"] = path
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return env


def run_git(repo: Path, *arguments: str, path: str = BASE_PATH) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", *arguments],
        check=True,
        capture_output=True,
        env=fixture_env(path),
        timeout=RUN_TIMEOUT,
    )


def run_state(repo: Path, *arguments: str, path: str = BASE_PATH) -> tuple[int, dict[str, str], str]:
    completed = subprocess.run(
        [sys.executable, str(SETUP_STATE), *arguments, "--repo", str(repo)],
        check=False,
        capture_output=True,
        text=True,
        env=fixture_env(path),
        timeout=RUN_TIMEOUT,
    )
    values: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values.setdefault(key, value)
    return completed.returncode, values, completed.stdout + completed.stderr


def make_repo(base: Path, name: str, manifest: dict | None = VALID_MANIFEST) -> Path:
    repo = base / name
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", str(repo)], check=True, capture_output=True, env=fixture_env(), timeout=RUN_TIMEOUT
    )
    (repo / "own.py").write_text("print('fixture')\n", encoding="utf-8")
    if manifest is not None:
        (repo / "hard-eng.gates.json").write_text(json.dumps(manifest), encoding="utf-8")
    hooks = repo / ".githooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    hook.chmod(0o755)
    run_git(repo, "config", "core.hooksPath", ".githooks")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "fixture")
    return repo


def receipt_file(module, repo: Path) -> Path:
    return repo / ".git" / module.RECEIPT_NAME


def check_receipt_lifecycle(module, base: Path) -> None:
    repo = make_repo(base, "lifecycle")
    receipt = receipt_file(module, repo)

    (repo / "own.py").write_text("print('dirty')\n", encoding="utf-8")
    code, values, output = run_state(repo, "run")
    require(code == 3, f"dirty selectable auto run must exit 3, got {code}: {output}")
    require(values.get("result") == "choice-required", "dirty selectable auto run must emit choice-required")
    require(not receipt.exists(), "choice-required run must not write a receipt")

    code, values, output = run_state(repo, "run", "--checkout-choice", "current")
    require(code == 0, f"checkout-choice current run must exit 0, got {code}: {output}")
    require(values.get("result") == "pass", "current-choice run must emit result=pass")
    require(values.get("checkout") == "primary", "fixture checkout must be primary")
    require(values.get("worktree_write") == "PASS", "worktree probe must PASS")
    require(values.get("gate_manifest") == "PASS", "manifest probe must PASS")
    require(values.get("memory_index") == "WARN", "memory probe without the tool must WARN")
    require("warning_1" in values, "memory WARN must emit a warning line")
    require(stat.S_IMODE(receipt.stat().st_mode) == 0o600, "receipt mode must be 0600")
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    require(payload["probes"]["memory_index"] == {"verdict": "WARN", "indexed_head_sha": None}, "WARN stores no head")

    baseline = receipt.read_bytes()
    code, values, output = run_state(repo, "verify")
    require(code == 0 and values.get("result") == "current", f"verify on current receipt must pass: {output}")
    code, values, output = run_state(repo, "run")
    require(code == 0 and values.get("result") == "current", f"repeat run must short-circuit current: {output}")
    require(receipt.read_bytes() == baseline, "verify and repeat run must leave receipt bytes unmutated")

    receipt.chmod(0o644)
    code, values, _ = run_state(repo, "verify")
    require(code == 4 and values.get("result") == "invalid", "0644 receipt must verify invalid")
    receipt.chmod(0o600)
    code, _, _ = run_state(repo, "verify")
    require(code == 0, "restored 0600 receipt must verify current")

    aside = receipt.with_name(f"{receipt.name}.real")
    receipt.rename(aside)
    receipt.symlink_to(aside)
    code, values, _ = run_state(repo, "verify")
    require(code == 4 and values.get("result") == "invalid", "symlinked receipt must verify invalid")
    receipt.unlink()
    aside.rename(receipt)
    code, _, _ = run_state(repo, "verify")
    require(code == 0, "restored real receipt must verify current")

    manifest = repo / "hard-eng.gates.json"
    manifest.write_text(json.dumps(VALID_MANIFEST, indent=2), encoding="utf-8")
    code, values, _ = run_state(repo, "verify")
    require(code == 4, "manifest byte change must invalidate the receipt")
    require("inputs changed" in values.get("detail", ""), "fingerprint mismatch must name changed inputs")
    code, values, output = run_state(repo, "run", "--checkout-choice", "current")
    require(code == 0 and values.get("result") == "pass", f"run must rewrite after input change: {output}")
    require(receipt.read_bytes() != baseline, "rewritten receipt must differ from the stale one")

    receipt.unlink()
    blocked = module.require_setup(repo)
    require(
        isinstance(blocked, str) and "run setup_state.py run" in blocked, "require_setup must block without receipt"
    )
    seeded = module.seed_receipt_for_fixture(repo)
    require(
        seeded.resolve() == receipt.resolve() and receipt.is_file(), "seed_receipt_for_fixture must write the receipt"
    )
    require(module.require_setup(repo) is None, "require_setup must pass on a seeded receipt")


def check_manifest_gate(module, base: Path) -> None:
    repo = make_repo(base, "manifest", manifest=None)
    receipt = receipt_file(module, repo)
    manifest = repo / "hard-eng.gates.json"

    code, values, output = run_state(repo, "run")
    require(code == 4 and values.get("result") == "invalid", f"missing manifest run must exit 4: {output}")
    require("gate-migration" in output, "missing manifest must direct to gate-migration")
    require(values.get("gate_manifest") == "FAIL", "missing manifest probe must FAIL")
    require(not receipt.exists(), "failed run must not write a receipt")

    manifest.write_text(json.dumps({**VALID_MANIFEST, "families": {}}), encoding="utf-8")
    code, _, output = run_state(repo, "run")
    require(code == 4 and "gate-migration" in output, f"empty families must exit 4 with directive: {output}")

    broken = {**VALID_MANIFEST, "phases": {"commit": ["targeted"], "push": ["tests"], "ci": ["tests"]}}
    manifest.write_text(json.dumps(broken), encoding="utf-8")
    code, _, output = run_state(repo, "run")
    require(code == 4 and "gate-migration" in output, f"undeclared phase family must exit 4: {output}")
    require(not receipt.exists(), "statically invalid manifest must leave no receipt")

    manifest.write_text(json.dumps(VALID_MANIFEST), encoding="utf-8")
    code, values, output = run_state(repo, "run", "--checkout-choice", "current")
    require(code == 0 and values.get("result") == "pass", f"repaired manifest must pass: {output}")


def check_enforcement_gate(module, base: Path) -> None:
    repo = make_repo(base, "enforcement-wiring")
    receipt = receipt_file(module, repo)

    run_git(repo, "config", "--unset", "core.hooksPath")
    code, values, output = run_state(repo, "run")
    require(code == 4 and values.get("result") == "invalid", f"unwired manifest repo must fail setup: {output}")
    require(values.get("gate_enforcement") == "FAIL", "unwired repo must emit gate_enforcement FAIL")
    require("hooks" in output, "unwired failure must direct to hook wiring")
    require(not receipt.exists(), "unwired run must not write a receipt")

    native = repo / ".git" / "hooks" / "pre-commit"
    native.parent.mkdir(exist_ok=True)
    native.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    native.chmod(0o755)
    code, values, output = run_state(repo, "run")
    require(code == 0 and values.get("gate_enforcement") == "PASS", f"native hook wiring must pass setup: {output}")

    native.chmod(0o644)
    code, values, _ = run_state(repo, "verify")
    require(code == 4, "losing hook wiring must invalidate the receipt")

    run_git(repo, "config", "core.hooksPath", ".githooks")
    code, values, output = run_state(repo, "run")
    require(code == 0 and values.get("gate_enforcement") == "PASS", f"hooksPath wiring must pass setup: {output}")

    both = make_repo(base, "enforcement-both", manifest=None)
    run_git(both, "config", "--unset", "core.hooksPath")
    code, values, output = run_state(both, "run")
    require(code == 4 and values.get("gate_manifest") == "FAIL", f"missing manifest must FAIL: {output}")
    require(values.get("gate_enforcement") == "FAIL", "missing manifest with no hooks must also FAIL enforcement")
    require("error_2" in values, "manifest and enforcement failures must both be reported")


def check_memory_and_policy(module, base: Path) -> None:
    repo = make_repo(base, "memory")
    receipt = receipt_file(module, repo)
    fake_bin = base / "fake-bin"
    fake_bin.mkdir()
    tool = fake_bin / module.MEMORY_TOOL
    tool.write_text(
        FAKE_MEMORY_TOOL.format(python=sys.executable, state_file=str(base / "memory-state.json")), encoding="utf-8"
    )
    tool.chmod(0o755)
    fake_path = f"{fake_bin}:{BASE_PATH}"

    code, values, output = run_state(repo, "run", path=fake_path)
    require(code == 0 and values.get("memory_index") == "PASS", f"fake memory tool run must PASS: {output}")
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=fixture_env(),
        timeout=RUN_TIMEOUT,
    ).stdout.strip()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    require(payload["probes"]["memory_index"]["indexed_head_sha"] == head, "PASS must store the indexed head")

    (repo / "own.py").write_text("print('advance')\n", encoding="utf-8")
    run_git(repo, "commit", "-q", "-am", "advance")
    code, values, _ = run_state(repo, "verify", path=fake_path)
    require(code == 5 and values.get("result") == "stale-memory", "HEAD advance must verify stale-memory")

    (repo / "own.py").write_text("print('dirty-refresh')\n", encoding="utf-8")
    code, values, output = run_state(repo, "run", path=fake_path)
    require(code == 0 and values.get("refresh") == "memory-only", f"stale-memory run must refresh only: {output}")
    require("choice" not in values, "memory-only refresh must not re-run the checkout probe")
    new_head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        env=fixture_env(),
        timeout=RUN_TIMEOUT,
    ).stdout.strip()
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    require(payload["probes"]["memory_index"]["indexed_head_sha"] == new_head, "refresh must store the new head")
    code, values, _ = run_state(repo, "verify", path=fake_path)
    require(code == 0 and values.get("result") == "current", "refreshed receipt must verify current")

    (repo / "AGENTS.override.md").write_text("# Fixture\n\n- checkout_policy = primary-only\n", encoding="utf-8")
    run_git(repo, "add", "AGENTS.override.md")
    run_git(repo, "commit", "-q", "-m", "policy")
    (repo / "own.py").write_text("print('dirty-policy')\n", encoding="utf-8")
    code, values, output = run_state(repo, "run", path=fake_path)
    require(code == 0 and values.get("result") == "pass", f"primary-only dirty run must never ask: {output}")
    require(values.get("checkout") == "primary", "primary-only run must record the primary checkout")


def main() -> int:
    module = load_setup_state()
    with tempfile.TemporaryDirectory(prefix="setup-state-regression-") as scratch:
        base = Path(scratch)
        check_receipt_lifecycle(module, base)
        check_manifest_gate(module, base)
        check_enforcement_gate(module, base)
        check_memory_and_policy(module, base)
    print("setup-state regression: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
