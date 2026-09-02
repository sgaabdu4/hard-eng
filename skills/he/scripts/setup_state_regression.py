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

import worktree
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


GLOBAL_CONFIG = os.devnull


def fixture_env(path: str = BASE_PATH) -> dict[str, str]:
    env = git_env()
    env["PATH"] = path
    env["GIT_CONFIG_GLOBAL"] = GLOBAL_CONFIG
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


def git_out(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=fixture_env(),
        timeout=RUN_TIMEOUT,
    ).stdout.strip()


def make_remote_repo(base: Path, name: str, branches: tuple[str, ...], env_files: tuple[str, ...]) -> Path:
    repo = make_repo(base, name)
    run_git(repo, "branch", "-M", "main")
    (repo / ".gitignore").write_text(".env\n.env.*\nnode_modules/\n", encoding="utf-8")
    post_checkout = repo / ".githooks" / "post-checkout"
    post_checkout.write_text(worktree.PROJECT_POST_CHECKOUT, encoding="utf-8")
    post_checkout.chmod(0o755)
    run_git(repo, "add", ".gitignore", ".githooks/post-checkout")
    run_git(repo, "commit", "-q", "-m", "ignore env")
    origin = base / f"{name}-origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(origin)],
        check=True,
        capture_output=True,
        env=fixture_env(),
        timeout=RUN_TIMEOUT,
    )
    run_git(repo, "remote", "add", "origin", str(origin))
    for branch in branches:
        if branch != "main":
            run_git(repo, "branch", branch, "main")
    run_git(repo, "push", "-q", "origin", *branches)
    run_git(repo, "remote", "set-head", "origin", "-a")
    for env_file in env_files:
        (repo / env_file).write_text(f"secret={env_file}\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / ".env").write_text("vendor=true\n", encoding="utf-8")
    return repo


def install_global_hooks(module, base: Path) -> None:
    global GLOBAL_CONFIG
    hooks = base / "global-hooks"
    hooks.mkdir()
    post_checkout = hooks / "post-checkout"
    post_checkout.write_text(f'#!/bin/sh\nexec bash "{module.COPY_HOOK}" "$@"\n', encoding="utf-8")
    post_checkout.chmod(0o755)
    config = base / "gitconfig"
    config.write_text(f"[core]\n\thooksPath = {hooks}\n", encoding="utf-8")
    GLOBAL_CONFIG = str(config)


def check_feature_checkout(module, base: Path) -> None:
    install_global_hooks(module, base)
    repo = make_remote_repo(base, "checkout-main", ("main",), (".env", ".env.local"))
    worktree = base / "checkout-main.worktrees" / "demo"

    code, values, output = run_state(repo, "run", "--feature-slug", "demo")
    require(code == 3 and values.get("result") == "choice-required", f"env candidates must ask once: {output}")
    require(values.get("choice_1") == "worktreeinclude", f"clean main must ask only the env question: {values}")
    require("choice_2" not in values, "clean main with one base must not ask about base or checkout")
    require(values.get("env_candidate_1") == ".env" and values.get("env_candidate_2") == ".env.local", str(values))
    require("env_candidate_3" not in values, "ignored directories must not be enumerated as env candidates")
    require(not worktree.exists(), "choice-required run must not create a worktree")

    code, values, output = run_state(repo, "run", "--feature-slug", "demo", "--include-env", ".env")
    require(code == 0 and values.get("result") == "pass", f"answered run must pass: {output}")
    require(values.get("repository_root") == str(worktree.resolve()), f"root must be the new worktree: {values}")
    require(values.get("checkout") == "linked:feature/demo", f"checkout must name the feature branch: {values}")
    require(values.get("base_ref") == "origin/main", f"base must be origin/main: {values}")
    require(git_out(worktree, "symbolic-ref", "--short", "HEAD") == "feature/demo", "worktree branch")
    require(git_out(worktree, "rev-parse", "HEAD~1") == git_out(repo, "rev-parse", "origin/main"), "base commit")
    require((worktree / ".worktreeinclude").read_text(encoding="utf-8") == ".env\n", "include list content")
    require(git_out(worktree, "status", "--porcelain") == "", "include list must be committed on the branch")
    require(git_out(worktree, "ls-files", ".worktreeinclude") == ".worktreeinclude", "include list tracked")
    require((worktree / ".env").read_text(encoding="utf-8") == "secret=.env\n", "env file copied")
    require(stat.S_IMODE((worktree / ".env").stat().st_mode) == 0o600, "copied env file must be private")
    require(not (worktree / ".env.local").exists(), "unselected env file must not be copied")
    require(git_out(repo, "status", "--porcelain") == "", "primary must stay clean")
    require(git_out(repo, "symbolic-ref", "--short", "HEAD") == "main", "primary must stay on main")
    require(not (repo / ".git" / module.RECEIPT_NAME).exists(), "receipt must not land in the primary")
    receipt = Path(git_out(worktree, "rev-parse", "--absolute-git-dir")) / module.RECEIPT_NAME
    require(receipt.is_file(), "receipt must land in the worktree git dir")
    code, values, output = run_state(worktree, "verify")
    require(code == 0 and values.get("result") == "current", f"worktree receipt must verify: {output}")

    code, values, output = run_state(repo, "run", "--feature-slug", "demo")
    require(code == 0 and values.get("result") == "current", f"resume from primary must not re-ask: {output}")
    require(values.get("repository_root") == str(worktree.resolve()), f"rerun reuses: {values}")

    code, values, output = run_state(repo, "run", "--include-env", "none")
    require(code == 4 and "feature-slug" in output, f"creation without a slug must fail closed: {output}")
    code, values, output = run_state(repo, "run", "--feature-slug", "../escape", "--include-env", "none")
    require(code == 4 and "feature-slug" in output, f"path-like slug must fail closed: {output}")
    require(not (base / "escape").exists(), "rejected slug must not touch the filesystem")

    adhoc = base / "checkout-main-codex"
    run_git(repo, "worktree", "add", "-q", "--detach", str(adhoc))
    code, values, output = run_state(adhoc, "run", "--feature-slug", "adhoc")
    require(code == 3 and values.get("choice_1") == "worktreeinclude", f"ad-hoc worktree asks env: {output}")
    require("choice_2" not in values, "ad-hoc worktree must not ask about base or checkout")
    code, values, output = run_state(adhoc, "run", "--feature-slug", "adhoc", "--include-env", ".env")
    require(code == 0 and values.get("repository_root") == str(adhoc.resolve()), f"ad-hoc stays put: {output}")
    require(git_out(adhoc, "diff", "--cached", "--name-only") == ".worktreeinclude", "staged, not committed")
    require((adhoc / ".env").read_text(encoding="utf-8") == "secret=.env\n", "env copied into ad-hoc worktree")
    require(stat.S_IMODE((adhoc / ".env").stat().st_mode) == 0o600, "ad-hoc copy must be private")
    require(not (base / "checkout-main.worktrees" / "adhoc").exists(), "ad-hoc worktree must not spawn another")

    both = make_remote_repo(base, "checkout-both", ("main", "develop"), ())
    run_git(both, "checkout", "-q", "-b", "topic")
    code, values, output = run_state(both, "run", "--feature-slug", "demo")
    require(code == 3 and values.get("choice_1") == "base-branch", f"two bases must ask: {output}")
    require(values.get("base_candidate_1") == "main" and values.get("base_candidate_2") == "develop", str(values))
    require("choice_2" not in values, "no env files means no env question")
    code, values, output = run_state(both, "run", "--feature-slug", "demo", "--base-branch", "develop")
    require(code == 0 and values.get("base_ref") == "origin/develop", f"chosen base must be used: {output}")
    both_worktree = base / "checkout-both.worktrees" / "demo"
    require(git_out(both_worktree, "rev-parse", "HEAD") == git_out(both, "rev-parse", "origin/develop"), "base")
    require(not (both_worktree / ".worktreeinclude").exists(), "no env files means no include list")

    run_git(both, "checkout", "-q", "develop")
    code, values, output = run_state(both, "run", "--feature-slug", "second")
    require(code == 0 and values.get("base_ref") == "origin/develop", f"current base branch needs no ask: {output}")

    dirty = make_remote_repo(base, "checkout-dirty", ("main",), (".env",))
    (dirty / "own.py").write_text("print('user work')\n", encoding="utf-8")
    code, values, output = run_state(dirty, "run", "--feature-slug", "demo")
    require(code == 3, f"dirty primary must ask: {output}")
    choices = {values.get("choice_1"), values.get("choice_2")}
    require(choices == {"checkout", "worktreeinclude"}, f"dirty primary batches both questions: {values}")
    code, values, output = run_state(
        dirty, "run", "--feature-slug", "demo", "--checkout-choice", "current", "--include-env", ".env"
    )
    require(code == 0 and values.get("checkout") == "primary", f"current choice stays put: {output}")
    require(git_out(dirty, "ls-files", ".worktreeinclude") == ".worktreeinclude", "include list staged in primary")
    require(git_out(dirty, "diff", "--cached", "--name-only") == ".worktreeinclude", "staged, not committed")
    require(not (base / "checkout-dirty.worktrees").exists(), "current choice must not create a worktree")


def main() -> int:
    module = load_setup_state()
    with tempfile.TemporaryDirectory(prefix="setup-state-regression-") as scratch:
        base = Path(scratch)
        check_receipt_lifecycle(module, base)
        check_manifest_gate(module, base)
        check_enforcement_gate(module, base)
        check_memory_and_policy(module, base)
        check_feature_checkout(module, base)
    print("setup-state regression: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
