#!/usr/bin/env python3
"""Prove the shared rollout: one command clones a repository, shares Hard Eng, commits, and pushes the default branch
or falls back to a branch when the push is refused."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from repository_native_contract_loader import load_contract

ROOT = Path(__file__).resolve().parents[1]
ROLLOUT = ROOT / "scripts/rollout-shared.py"
SHARED_FILES = (
    "AGENTS.override.md",
    ".github/instructions/hard-eng.instructions.md",
    ".hard-eng/bootstrap.sh",
    ".hard-eng/hook.sh",
    ".codex/hooks.json",
    ".codex/config.toml",
    ".claude/settings.json",
    ".github/hooks/hard-eng.json",
)
FALLBACK_BRANCH = "hard-eng-shared-wiring"
PROTECT_MAIN = """#!/bin/sh
while read old new ref; do
  if [ "$ref" = "refs/heads/main" ]; then
    echo "main is protected" >&2
    exit 1
  fi
done
exit 0
"""


contract = load_contract()
TAG = contract.TAG


def bare_origin(root: Path, name: str, *, marked: bool = True, claude: str | None = None) -> Path:
    seed = root / f"{name}-seed"
    contract.init_repository(seed, marked=marked)
    contract.write(seed / ".gitignore", ".github\n.codex\n.claude/settings.json\n")
    contract.commit_all(seed, [".gitignore"])
    if claude is not None:
        contract.write(seed / "CLAUDE.md", claude)
        contract.commit_all(seed, ["CLAUDE.md"])
    origin = root / f"{name}.git"
    contract.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], cwd=root)
    contract.run(["git", "push", "-q", str(origin), "main"], cwd=seed)
    return origin


def origin_head(origin: Path, ref: str) -> str | None:
    result = contract.run(
        ["git", "--git-dir", str(origin), "rev-parse", "--verify", "-q", ref], cwd=origin, check=False
    )
    return result.stdout.strip() or None


def origin_tree(origin: Path, ref: str) -> set[str]:
    output = contract.run(["git", "--git-dir", str(origin), "ls-tree", "-r", "--name-only", ref], cwd=origin).stdout
    return set(output.split())


def origin_message(origin: Path, ref: str) -> str:
    return contract.run(["git", "--git-dir", str(origin), "log", "-1", "--format=%B", ref], cwd=origin).stdout


def rollout(root: Path, env: dict[str, str], origin: Path, name: str, *extra: str, check: bool = True):
    command = [
        sys.executable,
        str(ROLLOUT),
        "--repository",
        str(origin),
        "--work-dir",
        str(root / name),
        "--launcher",
        str(contract.LAUNCHER),
        "install",
        "--home",
        str(root / "home"),
        *extra,
    ]
    return contract.run(command, cwd=root, environment=env, check=check)


def rollout_json(root: Path, env: dict[str, str], origin: Path, name: str) -> dict:
    return json.loads(rollout(root, env, origin, name, "--json").stdout)


def assert_push(root: Path, env: dict[str, str]) -> Path:
    origin = bare_origin(root, "push")
    before = origin_head(origin, "main")
    result = rollout_json(root, env, origin, "push-work")
    assert result["changed"] and result["pushed"] and result["pushed_branch"] == "main", result
    assert result["pull_request"] is None and result["version"] == TAG and result["branch"] == "main", result
    assert origin_head(origin, "main") == result["commit"] != before
    tree = origin_tree(origin, "main")
    assert set(SHARED_FILES) <= tree, tree
    assert "CLAUDE.local.md" not in tree and not any(path.startswith(".agents/") for path in tree), tree
    assert origin_message(origin, "main") == f"chore: share Hard Eng {TAG} with every clone\n\n"
    clone = Path(result["clone"])
    assert json.loads((clone / "hard-eng.gates.json").read_text())["hard_eng"]["pin"]["tag"] == TAG
    return origin


def assert_idempotent(root: Path, env: dict[str, str], origin: Path) -> None:
    head = origin_head(origin, "main")
    result = rollout_json(root, env, origin, "again-work")
    assert not result["changed"] and not result["pushed"] and result["commit"] is None, result
    assert origin_head(origin, "main") == head
    plain = rollout(root, env, origin, "plain-work").stdout
    assert f"already shared at {TAG}; nothing to push" in plain, plain


def assert_protected(root: Path, env: dict[str, str]) -> None:
    origin = bare_origin(root, "protected")
    contract.write(origin / "hooks/pre-receive", PROTECT_MAIN, 0o755)
    contract.run(["git", "--git-dir", str(origin), "config", "core.hooksPath", str(origin / "hooks")], cwd=origin)
    before = origin_head(origin, "main")
    result = rollout_json(root, env, origin, "protected-work")
    assert result["changed"] and not result["pushed"] and result["pushed_branch"] == FALLBACK_BRANCH, result
    assert result["pull_request"] is None, result
    assert origin_head(origin, "main") == before
    assert origin_head(origin, FALLBACK_BRANCH) == result["commit"]
    plain = rollout(root, env, origin, "protected-plain").stdout
    assert f"pushed {FALLBACK_BRANCH}; open a pull request into main" in plain, plain


def assert_refused(root: Path, env: dict[str, str]) -> None:
    origin = bare_origin(root, "refused", claude="# Other rules\n")
    before = origin_head(origin, "main")
    result = rollout(root, env, origin, "refused-work", check=False)
    assert result.returncode == 1 and "CLAUDE.md" in result.stderr, result.stderr
    assert origin_head(origin, "main") == before and origin_head(origin, FALLBACK_BRANCH) is None


def assert_unmarked(root: Path, env: dict[str, str]) -> None:
    origin = bare_origin(root, "unmarked", marked=False)
    result = rollout_json(root, env, origin, "unmarked-work")
    assert result["pushed"] and result["version"] == TAG, result
    tree = origin_tree(origin, "main")
    assert "hard-eng.gates.json" in tree and set(SHARED_FILES) <= tree, tree


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-rollout-") as temporary:
        root = Path(temporary)
        assets, release = contract.release_assets(root / "release")
        fake_bin = root / "fake-bin"
        fake_bin.mkdir()
        contract.fake_gh(fake_bin, [release])
        contract.fake_agents(fake_bin, ("codex",))
        env = contract.environment(fake_bin, assets)
        env.update(
            GIT_AUTHOR_NAME="Hard Eng Test",
            GIT_AUTHOR_EMAIL="hard-eng@example.invalid",
            GIT_COMMITTER_NAME="Hard Eng Test",
            GIT_COMMITTER_EMAIL="hard-eng@example.invalid",
        )
        (root / "home").mkdir()
        origin = assert_push(root, env)
        assert_idempotent(root, env, origin)
        assert_protected(root, env)
        assert_refused(root, env)
        assert_unmarked(root, env)
    print("rollout-shared-contract: PASS push idempotent protected refused unmarked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
