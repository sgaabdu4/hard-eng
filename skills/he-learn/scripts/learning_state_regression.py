#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "skills/he-learn/scripts/learning_state.py"
SETUP = ROOT / "setup.sh"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(TOOL), *args], cwd=ROOT, text=True, capture_output=True, check=False)


def run_setup(
    *args: str, home: Path | None = None, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    environment = None
    if home is not None:
        environment = dict(os.environ)
        environment["HOME"] = str(home)
        environment.update(extra_env or {})
    return subprocess.run(
        ["bash", str(SETUP), *args], cwd=ROOT, text=True, capture_output=True, check=False, env=environment
    )


def write(path: Path, content: str = "fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_record(repo: Path, record: dict[str, object]) -> Path:
    path = repo / ".agents/learning" / f"{record['learning_id']}.json"
    write(path, json.dumps(record, sort_keys=True) + "\n")
    return path


def base_record(kind: str = "deterministic") -> dict[str, object]:
    owner = "scripts/check-sync.py" if kind == "deterministic" else ".agents/skills/sync-recovery"
    return {
        "schema_version": 1,
        "learning_id": "sync-recovery",
        "status": "resolved",
        "trigger": "recurrence",
        "failure": "The same sync recovery path failed twice.",
        "evidence": ["attempt-1", "attempt-2"],
        "root_cause": "The repository had no check at the recovery boundary.",
        "occurrences": 2,
        "prevention": {
            "kind": kind,
            "owner": owner,
            "deterministic_limit": ""
            if kind == "deterministic"
            else "The decision depends on repository-specific operational context.",
            "violation_fixture": "tests/learning/violation.txt",
            "valid_fixture": "tests/learning/valid.txt",
            "proof": "receipts/learning-proof.json",
        },
        "next_action": "none",
    }


def prepare_repo(root: Path) -> Path:
    repo = root / "repo"
    (repo / ".git").mkdir(parents=True)
    write(repo / "tests/learning/violation.txt")
    write(repo / "tests/learning/valid.txt")
    write(repo / "receipts/learning-proof.json", "{}\n")
    return repo


def start_args(
    repo: Path, learning_id: str, trigger: str, *, occurrences: int = 1, historical: bool = False
) -> list[str]:
    result = [
        "start",
        "--repo",
        str(repo),
        "--learning-id",
        learning_id,
        "--trigger",
        trigger,
        "--failure",
        f"Verified process failure for {learning_id}.",
        "--evidence",
        f"receipt:{learning_id}",
        "--root-cause",
        "The repository lacked durable prevention.",
        "--occurrences",
        str(occurrences),
        "--next-action",
        "Select and prove the closest deterministic prevention.",
    ]
    if historical:
        result.append("--historical")
    return result


def trigger_and_helper_flow(root: Path) -> None:
    candidates = {
        "recurrence": 2,
        "engineering-correction": 1,
        "false-passing-check": 1,
        "protected-boundary-gap": 1,
        "repeated-manual-waste": 2,
    }
    for trigger, occurrences in candidates.items():
        repo = prepare_repo(root / f"trigger-{trigger}")
        learning_id = f"gap-{trigger}"
        first = run(*start_args(repo, learning_id, trigger, occurrences=occurrences))
        require(first.returncode == 0, first.stderr)
        require("CREATED" in first.stdout and "helper=he-learn" in first.stdout, first.stdout)
        second = run(*start_args(repo, learning_id, trigger, occurrences=occurrences))
        require(second.returncode == 0, second.stderr)
        require("EXISTS" in second.stdout and "helper=none" in second.stdout, second.stdout)
        listed = run("list-open", "--repo", str(repo))
        require(f".agents/learning/{learning_id}.json" in listed.stdout, listed.stdout)
        closure = run("validate", "--closure", "--repo", str(repo))
        require(closure.returncode != 0, "open learning incorrectly passed closure")
        record_path = repo / ".agents/learning" / f"{learning_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["status"] = "deferred"
        record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        unassigned = run("validate", "--closure", "--repo", str(repo))
        require(unassigned.returncode != 0, "deferred learning without an owner passed")
        record["deferred_owner"] = "repository maintainer"
        record_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
        assigned = run("validate", "--closure", "--repo", str(repo))
        require(assigned.returncode == 0, assigned.stderr)

    for trigger in ("personal-correction", "one-off-implementation"):
        repo = prepare_repo(root / f"non-candidate-{trigger}")
        result = run(*start_args(repo, f"gap-{trigger}", trigger))
        require(result.returncode == 0, result.stderr)
        require("NON_CANDIDATE" in result.stdout and "helper=none" in result.stdout, result.stdout)
        require(not (repo / ".agents/learning").exists(), f"{trigger} created repository learning")

    repo = prepare_repo(root / "insufficient-recurrence")
    result = run(*start_args(repo, "insufficient-recurrence", "recurrence"))
    require(result.returncode != 0, "one occurrence incorrectly triggered recurrence")


def historical_seed_is_safe_and_idempotent(root: Path) -> None:
    repo = prepare_repo(root / "historical")
    args = start_args(repo, "safe-rebase-guard", "engineering-correction", historical=True)
    first = run(*args)
    second = run(*args)
    require(first.returncode == 0 and "CREATED" in first.stdout, first.stderr)
    require(second.returncode == 0 and "EXISTS" in second.stdout, second.stderr)
    record = json.loads((repo / ".agents/learning/safe-rebase-guard.json").read_text(encoding="utf-8"))
    require(record.get("source_kind") == "historical", repr(record))
    conflict = list(args)
    conflict[conflict.index("Verified process failure for safe-rebase-guard.")] = "Different failure."
    rejected = run(*conflict)
    require(rejected.returncode != 0, "conflicting historical seed overwrote the record")


def deterministic_record_passes(root: Path) -> None:
    repo = prepare_repo(root / "deterministic")
    write(repo / "scripts/check-sync.py", "print('ok')\n")
    write_record(repo, base_record())
    result = run("validate", "--repo", str(repo))
    require(result.returncode == 0, result.stderr)
    require("learning-state: PASS" in result.stdout, "deterministic record did not pass")
    require(not (repo / ".agents/skills").exists(), "deterministic prevention created a skill")


def lifecycle_only_proof_fails(root: Path) -> None:
    repo = prepare_repo(root / "lifecycle-proof")
    write(repo / "scripts/check-sync.py", "print('ok')\n")
    write(repo / "features/local/receipts/proof.json", "{}\n")
    record = base_record()
    prevention = cast(dict[str, object], record["prevention"])
    prevention["proof"] = "features/local/receipts/proof.json"
    write_record(repo, record)
    result = run("validate", "--repo", str(repo))
    require(result.returncode != 0, "lifecycle-only proof incorrectly passed")
    require("lifecycle-only features path" in result.stderr, result.stderr)


def skill_fallback_is_shared(root: Path) -> None:
    repo = prepare_repo(root / "skill")
    skill = repo / ".agents/skills/sync-recovery"
    write(
        skill / "SKILL.md",
        "---\nname: sync-recovery\ndescription: Recover repeated repository sync failures.\n---\n\n# Sync Recovery\n",
    )
    write_record(repo, base_record("skill"))
    installed = run_setup("repo-install", str(repo))
    require(installed.returncode == 0, installed.stderr)
    link = repo / ".claude/skills/sync-recovery"
    require(link.is_symlink(), "Claude skill link was not created")
    require(link.resolve() == skill.resolve(), "Claude skill link has the wrong target")
    require(not (repo / ".codex/skills").exists(), "Codex shadow skill path was created")
    require(not (repo / ".copilot/skills").exists(), "Copilot shadow skill path was created")
    checked = run_setup("repo-check", str(repo))
    require(checked.returncode == 0, checked.stderr)
    second = run_setup("repo-install", str(repo))
    require(second.returncode == 0, second.stderr)


def skill_requires_recurrence_and_limit(root: Path) -> None:
    repo = prepare_repo(root / "skill-invalid")
    write(
        repo / ".agents/skills/sync-recovery/SKILL.md",
        "---\nname: sync-recovery\ndescription: Recover repeated repository sync failures.\n---\n",
    )
    record = base_record("skill")
    record["occurrences"] = 1
    prevention = cast(dict[str, object], record["prevention"])
    prevention["deterministic_limit"] = ""
    write_record(repo, record)
    result = run("validate", "--repo", str(repo))
    require(result.returncode != 0, "one occurrence incorrectly admitted a skill")
    require("at least two occurrences" in result.stderr, "missing recurrence error")
    require("deterministic_limit" in result.stderr, "missing deterministic limit error")


def copied_claude_skill_fails(root: Path) -> None:
    repo = prepare_repo(root / "copied")
    skill = repo / ".agents/skills/sync-recovery"
    write(
        skill / "SKILL.md",
        "---\nname: sync-recovery\ndescription: Recover repeated repository sync failures.\n---\n\n# Sync Recovery\n",
    )
    write_record(repo, base_record("skill"))
    write(repo / ".claude/skills/sync-recovery/SKILL.md", "copy\n")
    result = run_setup("repo-check", str(repo))
    require(result.returncode != 0, "copied Claude skill incorrectly passed")
    require("must be a symlink" in result.stderr, "copied skill error was unclear")


def repository_link_drift_and_rollback(root: Path) -> None:
    repo = prepare_repo(root / "link-drift")
    skill = repo / ".agents/skills/sync-recovery"
    write(
        skill / "SKILL.md",
        "---\nname: sync-recovery\ndescription: Recover repeated repository sync failures.\n---\n\n# Sync Recovery\n",
    )
    write_record(repo, base_record("skill"))
    missing = run_setup("repo-check", str(repo))
    require(missing.returncode != 0 and "missing" in missing.stderr, missing.stderr)
    installed = run_setup("repo-install", str(repo))
    require(installed.returncode == 0, installed.stderr)
    link = repo / ".claude/skills/sync-recovery"
    link.unlink()
    link.symlink_to("../../missing-skill")
    broken = run_setup("repo-check", str(repo))
    require(broken.returncode != 0 and "wrong target" in broken.stderr, broken.stderr)
    link.unlink()
    link.symlink_to(os.path.relpath(skill, link.parent))
    write(repo / ".codex/skills/sync-recovery/SKILL.md", "shadow\n")
    shadow = run_setup("repo-check", str(repo))
    require(shadow.returncode != 0 and "shadow skill" in shadow.stderr, shadow.stderr)
    shadow_root = repo / ".codex/skills/sync-recovery"
    for child in shadow_root.iterdir():
        child.unlink()
    shadow_root.rmdir()
    removed = run_setup("repo-uninstall", str(repo))
    require(removed.returncode == 0, removed.stderr)
    require(not link.exists() and not link.is_symlink(), "repository rollback left the Claude link")
    require(skill.is_dir(), "repository rollback removed the canonical skill")


def global_adapters_are_canonical(root: Path) -> None:
    home = root / "home"
    installed = run_setup("learning-install", home=home)
    require(installed.returncode == 0, installed.stderr)
    expected = {
        home / ".codex/agents/he-learn.toml": ROOT / "agents/he-learn/codex.toml",
        home / ".claude/agents/he-learn.md": ROOT / "agents/he-learn/claude.md",
        home / ".copilot/agents/he-learn.agent.md": ROOT / "agents/he-learn/copilot.agent.md",
    }
    for link, source in expected.items():
        require(link.is_symlink(), f"missing adapter link: {link}")
        require(link.resolve() == source.resolve(), f"wrong adapter target: {link}")
    checked = run_setup("learning-check", home=home)
    require(checked.returncode == 0, checked.stderr)
    copied = home / ".copilot/agents/he-learn.agent.md"
    copied.unlink()
    copied.write_text((ROOT / "agents/he-learn/copilot.agent.md").read_text(encoding="utf-8"), encoding="utf-8")
    rejected = run_setup("learning-check", home=home)
    require(rejected.returncode != 0, "copied global adapter incorrectly passed")
    require("must be a symlink" in rejected.stderr, "copied adapter error was unclear")
    require(not (home / ".agents/learning").exists(), "repository learning leaked into global home")


def global_adapters_survive_aliased_home(root: Path) -> None:
    real = root / "deep" / "real-home"
    real.mkdir(parents=True)
    alias = root / "alias-home"
    alias.symlink_to(real, target_is_directory=True)
    aliased = {
        "CODEX_HOME": str(alias / ".codex"),
        "CLAUDE_CONFIG_DIR": str(alias / ".claude"),
        "COPILOT_HOME": str(alias / ".copilot"),
    }
    installed = run_setup("learning-install", home=alias, extra_env=aliased)
    require(installed.returncode == 0, installed.stderr)
    link = alias / ".codex/agents/he-learn.toml"
    require(link.resolve() == (ROOT / "agents/he-learn/codex.toml").resolve(), f"aliased home link is wrong: {link}")
    checked = run_setup("learning-check", home=alias, extra_env=aliased)
    require(checked.returncode == 0, checked.stderr)


def route_contract_covers_every_lifecycle() -> None:
    contract = (ROOT / "skills/he-learn/SKILL.md").read_text(encoding="utf-8")
    require(
        "Any route = Direct + Diagnose + Feature Loop + Build + Ship" in contract,
        "learning trigger is not defined for every lifecycle route",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        trigger_and_helper_flow(root)
        historical_seed_is_safe_and_idempotent(root)
        deterministic_record_passes(root)
        lifecycle_only_proof_fails(root)
        skill_fallback_is_shared(root)
        skill_requires_recurrence_and_limit(root)
        copied_claude_skill_fails(root)
        repository_link_drift_and_rollback(root)
        global_adapters_are_canonical(root)
        global_adapters_survive_aliased_home(root)
        route_contract_covers_every_lifecycle()
    print("learning-state regression: PASS")


if __name__ == "__main__":
    main()
