#!/usr/bin/env python3
"""Check Hard Eng ship routing, state return, and commit adoption."""

from __future__ import annotations

import importlib.util
import hashlib
import io
import fcntl
import os
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
SKILL = ROOT / "skills/he-ship"
AXES_PASS = "intent-spec:pass,deterministic:pass,tests:pass,review:pass,security:pass,ui-design:na,e2e-runtime:pass,docs-context:pass,unknowns:pass"
AXES_PENDING = "intent-spec:pending,deterministic:pending,tests:pending,review:pending,security:pending,ui-design:pending,e2e-runtime:pending,docs-context:pending,unknowns:pending"


def fail(message: str) -> None:
    print(f"he-ship-contracts: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_state():
    spec = importlib.util.spec_from_file_location("hard_eng_ship_state", STATE_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quietly(action, *args) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        result = action(*args)
    return result, output.getvalue()


def check_skill() -> None:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    workflow = (SKILL / "references/workflow.md").read_text(encoding="utf-8")
    metadata = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
    for anchor in ("green hard eng plan", "sync", "publish", "git delivery", "ci"):
        if anchor not in skill.split("---", 2)[1].lower():
            fail(f"description route missing: {anchor}")
    for anchor in ("$he-build", "$deterministic-checks", "$he-learn", "reconcile-head", "force push"):
        if anchor not in skill:
            fail(f"ship invariant missing: {anchor}")
    for anchor in (
        "Sync ⇄ Build", "CI ⇄ Build", "git push --dry-run", "Checkpoint `shipped`",
        "zero open candidate",
    ):
        if anchor not in workflow:
            fail(f"ship workflow missing: {anchor}")
    if "allow_implicit_invocation: true" not in metadata:
        fail("he-ship must route only through $he")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    for anchor in (
        "codebase-memory-mcp@0.8.1", "context-mode@1.0.168", "ctx7@0.5.4",
        "npm ci $offline --cache", "--offline", "runtime_tree_digest",
        "check_npm_runtime", "verified_download", "JQ_VERSION=1.7.1", "RTK_VERSION=0.43.0",
        "canonical_command", "check_jq_pin", "check_rtk_pin",
        "codebase-memory-mcp cli list_projects",
    ):
        if anchor not in setup:
            fail(f"setup missing pinned verified install route: {anchor}")
    with tempfile.TemporaryDirectory(prefix="hard-eng-spoof-") as temporary:
        home = Path(temporary)
        binary = home / ".local/bin"
        binary.mkdir(parents=True)
        for name, version in (("jq", "jq-1.7.1"), ("rtk", "rtk 0.43.0")):
            path = binary / name
            path.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n", encoding="utf-8")
            path.chmod(0o755)
        environment = {**os.environ, "HOME": str(home), "PATH": f"{binary}:{os.environ['PATH']}"}
        spoof = subprocess.run([str(ROOT / "setup.sh"), "binary-check"], env=environment, capture_output=True)
        if spoof.returncode == 0:
            fail("setup accepted canonical same-version binaries with unverified bytes")
    for package in ("codebase-memory-mcp@0.8.1", "context-mode@1.0.168", "ctx7@0.5.4"):
        if package not in setup or f"{package}) printf" not in setup:
            fail(f"setup missing npm archive integrity owner: {package}")
    with tempfile.TemporaryDirectory(prefix="hard-eng-npm-integrity-") as temporary:
        root = Path(temporary); source = root / "source/package"; installed = root / "installed"
        source.mkdir(parents=True); installed.mkdir()
        (source / "cli.js").write_text("safe\n", encoding="utf-8")
        (installed / "cli.js").write_text("safe\n", encoding="utf-8")
        archive = root / "fixture.tgz"
        subprocess.run(["tar", "-czf", str(archive), "-C", str(root / "source"), "package"], check=True)
        digest = hashlib.sha512(archive.read_bytes()).hexdigest()
        command = [str(ROOT / "setup.sh"), "npm-tree-check", str(archive), digest, str(installed), "none"]
        if subprocess.run(command, capture_output=True).returncode != 0:
            fail("npm archive integrity rejected exact installed tree")
        (installed / "cli.js").write_text("corrupt\n", encoding="utf-8")
        if subprocess.run(command, capture_output=True).returncode == 0:
            fail("npm archive integrity accepted corrupted installed CLI")


def shipping_state(module, root: Path, head: str, snapshot: str, artifact: str) -> dict[str, str]:
    complete = ",".join(module.PLAN_STAGES)
    return {
        "state_version": "3",
        "plan_id": "fixture",
        "feature_slug": "fixture",
        "repository_root": str(root),
        "branch": "main",
        "base_sha": head,
        "head_sha": head,
        "updated_at_utc": "2026-01-01T00:00:00Z",
        "lifecycle_status": "shipping",
        "current_stage": "ship",
        "plan_stage": "none",
        "approved_plan_stages": complete,
        "skipped_plan_stages": "none",
        "stage_status": "in-progress",
        "next_action": "commit",
        "waiting_for": "agent",
        "plan_approved": "yes",
        "open_blockers": "none",
        "open_issues": "none",
        "open_unknowns": "none",
        "active_slice": "none",
        "slice_count": "1",
        "completed_slices": "S-1",
        "build_round": "1",
        "snapshot_id": snapshot,
        "artifact_id": artifact,
        "build_axes": AXES_PASS,
        "build_readiness": "100",
        "build_evidence": "current",
    }


def check_return(module, shipping: dict[str, str]) -> None:
    building = {
        **shipping,
        "lifecycle_status": "building",
        "current_stage": "build",
        "stage_status": "in-progress",
        "active_slice": "final",
        "build_round": "2",
        "build_axes": AXES_PENDING,
        "build_readiness": "0",
        "build_evidence": "stale",
    }
    module.validate_values(building)
    module.validate_transition(building)
    module.validate_state_change(shipping, building)
    try:
        module.validate_state_change(shipping, {**building, "build_round": "3"})
    except module.PlanStateError:
        pass
    else:
        fail("ship return accepted a skipped build round")


def check_drift_checkpoint(module) -> None:
    for lifecycle in ("green", "shipping"):
        with tempfile.TemporaryDirectory(prefix=f"hard-eng-drift-{lifecycle}-") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "F"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "f@x"], check=True)
            readme = root / "README.md"
            readme.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True)
            head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            if quietly(module.initialize, str(root), "fixture", None)[0] != 0:
                fail("drift PLAN initialization failed")
            plan = root / "features/fixture/PLAN.md"
            state = shipping_state(
                module, root, head, module.repository_snapshot_id(root), module.repository_artifact_id(root)
            )
            if lifecycle == "green":
                state.update(lifecycle_status="green", stage_status="pending")
            text = module.replace_state(plan.read_text(encoding="utf-8"), state)
            text += "\n## Slices\n\n| ID | Outcome |\n|---|---|\n| S-1 | Fixture |\n"
            plan.write_text(text, encoding="utf-8")
            readme.write_text("changed\n", encoding="utf-8")
            token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
            result, output = quietly(module.checkpoint, str(root), str(plan), token, [], [], [], [])
            if result != 0:
                fail(f"{lifecycle} drift checkpoint failed: {output.strip()}")
            updated = module.validate_document(plan, plan.read_text(encoding="utf-8"))
            if updated["lifecycle_status"] != "building" or updated["build_round"] != "2":
                fail(f"{lifecycle} drift did not return to one new build round")


def check_reconciliation_mode(module, mode: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"hard-eng-ship-{mode}-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.com"], check=True)
        (root / "README.md").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "baseline"], check=True)
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        result, _ = quietly(module.initialize, str(root), "fixture", None)
        if result != 0:
            fail("ship PLAN initialization failed")
        plan = root / "features/fixture/PLAN.md"
        change = root / "change.py"
        if mode in {"staged", "untracked", "mixed", "race", "learning"}:
            change.write_text("value = 1\n", encoding="utf-8")
        if mode in {"unstaged", "mixed"}:
            (root / "README.md").write_text("working\n", encoding="utf-8")
        if mode in {"staged", "learning"}:
            subprocess.run(["git", "-C", str(root), "add", "change.py"], check=True)
        if mode == "mixed":
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            (root / "README.md").write_text("working-again\n", encoding="utf-8")
        snapshot = module.repository_snapshot_id(root)
        artifact = module.repository_artifact_id(root)
        original = plan.read_text(encoding="utf-8")
        state = shipping_state(module, root, head, snapshot, artifact)
        text = module.replace_state(original, state)
        if mode == "learning":
            from plan_items import bound_learning_receipt
            proof = "artifact-identical commit preserves closed learning receipt"
            receipt = bound_learning_receipt("PASS: reconciliation fixture", proof, snapshot, artifact)
            text = module.replace_learning_candidates(text, {"L-1": (
                "L-1", "false-gate", "ship reconciliation", "Verified: closed proof fixture",
                "snapshot identity concern", "$he-ship", proof, receipt, "closed",
            )})
        text += "\n## Slices\n\n| ID | Outcome |\n|---|---|\n| S-1 | Fixture |\n"
        module.validate_document(plan, text)
        plan.write_text(text, encoding="utf-8")
        check_return(module, state)
        subprocess.run(
            ["git", "-C", str(root), "add", "-A", "--", ".", ":(exclude,glob)features/*/PLAN.md"], check=True
        )
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "change"], check=True)

        token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
        if mode == "learning" and module.repository_snapshot_id(root) == snapshot:
            fail("learning reconciliation fixture did not produce snapshot representation drift")
        if mode == "staged":
            extra = root / "extra.txt"
            extra.write_text("uncommitted\n", encoding="utf-8")
            if quietly(module.reconcile_head, str(root), str(plan), token)[0] != 4:
                fail("reconcile-head accepted uncommitted artifact")
            extra.unlink()
        if mode == "race":
            globals_ = module.reconcile_committed_head.__globals__
            original_write = globals_["repo_write"]
            writes = 0
            def racing_write(repo_root, relative, content, file_mode):
                nonlocal writes
                writes += 1
                original_write(repo_root, relative, content, file_mode)
                if writes == 1:
                    (root / "concurrent.txt").write_text("race\n", encoding="utf-8")
            globals_["repo_write"] = racing_write
            try:
                result, output = quietly(module.reconcile_head, str(root), str(plan), token)
            finally:
                globals_["repo_write"] = original_write
            if result != 4 or "untracked non-PLAN" not in output:
                fail("reconcile-head accepted a concurrent artifact mutation")
            if module.checkpoint_token(plan.read_text(encoding="utf-8")) != token:
                fail("reconcile-head race did not restore the original PLAN")
            return
        result, output = quietly(module.reconcile_head, str(root), str(plan), token)
        if result != 0 or "result=reconciled" not in output:
            fail("reconcile-head rejected exact committed artifact: " + output.strip())
        reconciled = module.validate_document(plan, plan.read_text(encoding="utf-8"))
        current = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if reconciled["head_sha"] != current or reconciled["artifact_id"] != artifact:
            fail("reconcile-head lost commit or artifact identity")
        if reconciled["snapshot_id"] != module.repository_snapshot_id(root):
            fail("reconcile-head did not normalize committed evidence identity")
        if quietly(module.inspect, str(root), str(plan))[0] != 0:
            fail("reconciled PLAN is not fresh")


def check_reconciliation(module) -> None:
    for mode in ("staged", "unstaged", "untracked", "mixed", "race", "learning"):
        check_reconciliation_mode(module, mode)


def check_pre_ship_reconciliation_rejected(module) -> None:
    for lifecycle in ("building", "green"):
        with tempfile.TemporaryDirectory(prefix=f"hard-eng-{lifecycle}-reconcile-") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "F"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "f@x"], check=True)
            readme = root / "README.md"
            readme.write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True)
            head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            if quietly(module.initialize, str(root), "fixture", None)[0] != 0:
                fail(f"{lifecycle} reconciliation PLAN initialization failed")
            plan = root / "features/fixture/PLAN.md"
            readme.write_text("built\n", encoding="utf-8")
            state = shipping_state(
                module, root, head, module.repository_snapshot_id(root), module.repository_artifact_id(root)
            )
            if lifecycle == "building":
                state.update(
                    lifecycle_status="building", current_stage="build", stage_status="in-progress",
                    active_slice="S-1", completed_slices="none", build_axes=AXES_PENDING,
                    build_readiness="0", build_evidence="stale",
                )
            else:
                state.update(lifecycle_status="green", stage_status="pending")
            text = module.replace_state(plan.read_text(encoding="utf-8"), state)
            plan.write_text(text + "\n## Slices\n\n| ID | Outcome |\n|---|---|\n| S-1 | Fixture |\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "built"], check=True)
            token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
            result, output = quietly(module.reconcile_head, str(root), str(plan), token)
            if result != 4 or "requires shipping state" not in output:
                fail(f"reconcile-head accepted {lifecycle} state: {output.strip()}")


def check_rejected_commit_ranges(module) -> None:
    for mode in ("plan-commit", "intermediate"):
        with tempfile.TemporaryDirectory(prefix=f"hard-eng-range-{mode}-") as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "F"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "f@x"], check=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True)
            head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            if quietly(module.initialize, str(root), "fixture", None)[0] != 0:
                fail("commit-range PLAN initialization failed")
            plan = root / "features/fixture/PLAN.md"
            if mode == "plan-commit":
                (root / "change.py").write_text("value = 1\n", encoding="utf-8")
            state = shipping_state(
                module, root, head, module.repository_snapshot_id(root), module.repository_artifact_id(root)
            )
            text = module.replace_state(plan.read_text(encoding="utf-8"), state)
            text += "\n## Slices\n\n| ID | Outcome |\n|---|---|\n| S-1 | Fixture |\n"
            plan.write_text(text, encoding="utf-8")
            if mode == "plan-commit":
                subprocess.run(["git", "-C", str(root), "add", "change.py", str(plan)], check=True)
                subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "bad plan commit"], check=True)
                expected = "implementation commit contains PLAN state"
            else:
                transient = root / "transient.secret"
                transient.write_text("temporary\n", encoding="utf-8")
                subprocess.run(["git", "-C", str(root), "add", transient.name], check=True)
                subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "add transient"], check=True)
                transient.unlink()
                subprocess.run(["git", "-C", str(root), "add", "-u"], check=True)
                subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "remove transient"], check=True)
                expected = "exactly one implementation commit"
            token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
            result, output = quietly(module.reconcile_head, str(root), str(plan), token)
            if result != 4 or expected not in output:
                fail(f"reconcile-head accepted {mode} range: {output.strip()}")


def check_reconcile_checkpoint_lock(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-adopt-race-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "F"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "f@x"], check=True)
        (root / "README.md").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True)
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if quietly(module.initialize, str(root), "fixture", None)[0] != 0:
            fail("adopt race PLAN initialization failed")
        plan = root / "features/fixture/PLAN.md"
        change = root / "change.py"
        change.write_text("value = 1\n", encoding="utf-8")
        state = shipping_state(
            module, root, head, module.repository_snapshot_id(root), module.repository_artifact_id(root)
        )
        text = module.replace_state(plan.read_text(encoding="utf-8"), state)
        plan.write_text(text + "\n## Slices\n\n| ID | Outcome |\n|---|---|\n| S-1 | Fixture |\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "change.py"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "change"], check=True)
        token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
        common = Path(subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True
        ).strip())
        lock_path = common / "hard-eng-plan-transfer.lock"
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            reconcile = subprocess.Popen([
                sys.executable, str(STATE_PATH), "reconcile-head", "--repo", str(root),
                "--plan", str(plan), "--expect-token", token,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            checkpoint = subprocess.Popen([
                sys.executable, str(STATE_PATH), "checkpoint", "--repo", str(root),
                "--plan", str(plan), "--expect-token", token, "--set", "next_action=Race checkpoint.",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.2)
            if reconcile.poll() is not None or checkpoint.poll() is not None:
                reconcile.kill(); checkpoint.kill()
                fail("reconcile/checkpoint bypassed the shared PLAN-writer lock")
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        results = [reconcile.communicate(timeout=10), checkpoint.communicate(timeout=10)]
        if sorted((reconcile.returncode, checkpoint.returncode)) != [0, 4]:
            fail("reconcile/checkpoint race did not elect one writer: " + repr(results))
        reconciled = module.validate_document(plan, plan.read_text(encoding="utf-8"))
        current = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if reconciled["head_sha"] != current or quietly(module.inspect, str(root), str(plan))[0] != 0:
            fail("reconcile/checkpoint race lost the fresh state")


def check_base_ancestry(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-base-ancestry-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "F"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "f@x"], check=True)
        (root / "README.md").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "base"], check=True)
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        tree = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], text=True).strip()
        unrelated = subprocess.check_output(
            ["git", "-C", str(root), "commit-tree", tree, "-m", "unrelated"], text=True
        ).strip()
        if quietly(module.initialize, str(root), "fixture", None)[0] != 0:
            fail("base ancestry PLAN initialization failed")
        plan = root / "features/fixture/PLAN.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(f"- base_sha = {head}", f"- base_sha = {unrelated}"),
            encoding="utf-8",
        )
        result, output = quietly(module.inspect, str(root), str(plan))
        if result != 5 or "stale_fields=base_sha" not in output:
            fail("existing unrelated base commit passed freshness")


def main() -> int:
    module = load_state()
    check_skill()
    check_drift_checkpoint(module)
    check_reconciliation(module)
    check_pre_ship_reconciliation_rejected(module)
    check_rejected_commit_ranges(module)
    check_reconcile_checkpoint_lock(module)
    check_base_ancestry(module)
    print("he-ship-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
