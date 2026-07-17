#!/usr/bin/env python3
"""Integration proof for Hard Eng PLAN checkpoints and transfers."""

from __future__ import annotations

import importlib.util
import io
import fcntl
import select
import stat
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout
from pathlib import Path

sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
PLAN_STATE_PATH = SCRIPT_DIR / "plan_state.py"
AUDIT_SCRIPT_DIR = SCRIPT_DIR.parents[1] / "he-build/scripts"
if str(AUDIT_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(AUDIT_SCRIPT_DIR))
from audit_contract import finding_issue  # noqa: E402
from admission_regression_check import candidate_plan_text  # noqa: E402
from build_head_reconcile_regression import check_build_head_reconciliation  # noqa: E402
from legacy_migration_regression import check_legacy_migration  # noqa: E402
from learning_lifecycle_regression import check_learning_lifecycle_boundary  # noqa: E402


def fail(message: str) -> None:
    print(f"he-state-integration: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_plan_state():
    spec = importlib.util.spec_from_file_location("hard_eng_plan_state_integration", PLAN_STATE_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def quietly(action, *args, **kwargs) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        result = action(*args, **kwargs)
    return result, output.getvalue()


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "fixture@example.com"], check=True)
    (path / "PRODUCT.md").write_text("baseline\n", encoding="utf-8")
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "PRODUCT.md", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "fixture"], check=True)


def linked(source: Path, destination: Path) -> None:
    subprocess.run(
        ["git", "-C", str(source), "worktree", "add", "-q", "--detach", str(destination)],
        check=True,
    )


def transfer_direct(module, source, destination, plan, token, includes, fault_hook):
    return module.transfer_plan(
        str(source), str(destination), str(plan), token, includes,
        git_identity=module.git_identity, canonical_plan=module.canonical_plan,
        checkpoint_token=module.checkpoint_token, document_token=module.document_token,
        validate_document=module.validate_document, freshness_errors=module.freshness_errors,
        replace_state=module.replace_state, emit=module.emit, fault_hook=fault_hook,
    )


def check_checkpoint(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-checkpoint-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        result, _ = quietly(module.initialize, str(root), "fixture", None)
        if result != 0:
            fail("checkpoint fixture initialization failed")
        plan = root / "features/fixture/PLAN.md"
        original = plan.read_text(encoding="utf-8")
        token = module.checkpoint_token(original)
        result, output = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            token,
            ["next_action=Resolve issue."],
            [["issue", "Missing proof", "Approval blocked", "agent", "Gather evidence"]],
            [],
            [],
        )
        if result != 0 or "added_items=I-1" not in output:
            fail("atomic checkpoint add failed")
        added = plan.read_text(encoding="utf-8")
        if module.validate_document(plan, added)["open_issues"] != "I-1":
            fail("checkpoint item/state parity failed")
        result, _ = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            module.checkpoint_token(added),
            [],
            [],
            [],
            ["I-1"],
        )
        if result != 0:
            fail("atomic checkpoint close failed")
        closed = plan.read_text(encoding="utf-8")
        result, output = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            module.checkpoint_token(closed),
            [], [], [], [],
            [["false-gate", "build I-1", "Verified: false-pass gate", "context omission", "audit controller",
              "overflow fixture fails closed"]],
            [],
        )
        if result != 0 or "added_learning=L-1" not in output:
            fail("atomic learning candidate add failed")
        with_learning = plan.read_text(encoding="utf-8")
        if module.parse_learning_candidates(with_learning)["L-1"][8] != "open":
            fail("checkpoint lost open learning candidate")
        result, output = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            module.checkpoint_token(with_learning),
            [], [], [], [], [],
            [["L-1", "PASS: overflow fixture + full contracts"]],
        )
        if result != 0 or "resolved_learning=L-1" not in output:
            fail("atomic learning candidate resolution failed: " + output.strip())
        closed = plan.read_text(encoding="utf-8")
        row = list(module.parse_learning_candidates(closed)["L-1"])
        if not module.learning_pass_binding(row[7]):
            fail("learning resolution lacks proof/snapshot/artifact binding")
        row[6] = "different required proof"
        tampered = module.replace_learning_candidates(closed, {"L-1": tuple(row)})
        try: module.parse_learning_candidates(tampered)
        except module.PlanStateError: pass
        else: fail("learning receipt accepted a different required proof")
        result, _ = quietly(
            module.checkpoint,
            str(root), str(plan), module.checkpoint_token(closed), [], [], [], [],
            [["systemic-critical-gap", "build I-2", "Verified: external prevention", "global owner", "global plan", "destination proof"]],
            [], [],
        )
        if result != 0:
            fail("learning transfer source candidate add failed")
        transfer_source = plan.read_text(encoding="utf-8")
        result, _ = quietly(
            module.checkpoint,
            str(root), str(plan), module.checkpoint_token(transfer_source), [], [], [], [], [],
            [["L-2", "TRANSFER: destination/L-1"]], [],
        )
        if result != 4 or plan.read_text(encoding="utf-8") != transfer_source:
            fail("free-form learning transfer receipt changed PLAN")
        result, _ = quietly(module.initialize, str(root), "destination", "destination")
        if result != 0:
            fail("learning transfer destination init failed")
        destination = root / "features/destination/PLAN.md"
        destination_text = destination.read_text(encoding="utf-8")
        result, _ = quietly(
            module.checkpoint,
            str(root), str(destination), module.checkpoint_token(destination_text), [], [], [], [],
            [["systemic-critical-gap", "global flow", "Verified: source transfer", "global owner", "global plan", "global proof"]],
            [], [],
        )
        if result != 0:
            fail("learning transfer destination candidate add failed")
        unrelated_destination = destination.read_text(encoding="utf-8")
        result, _ = quietly(
            module.checkpoint,
            str(root), str(plan), module.checkpoint_token(transfer_source), [], [], [], [], [], [],
            [["L-2", str(destination), "L-1"]],
        )
        if result != 4 or plan.read_text(encoding="utf-8") != transfer_source:
            fail("unrelated destination learning candidate accepted")
        result, _ = quietly(
            module.checkpoint,
            str(root), str(destination), module.checkpoint_token(unrelated_destination), [], [], [], [],
            [["systemic-critical-gap", "TRANSFER: fixture/L-2", "Verified: external prevention", "global owner",
              "destination owner", "destination proof"]],
            [], [],
        )
        if result != 0:
            fail("linked learning transfer destination candidate add failed")
        result, output = quietly(
            module.checkpoint,
            str(root), str(plan), module.checkpoint_token(transfer_source), [], [], [], [], [], [],
            [["L-2", str(destination), "L-2"]],
        )
        if result != 0 or "resolved_learning=L-2" not in output:
            fail("validated learning transfer failed")
        transferred = module.parse_learning_candidates(plan.read_text(encoding="utf-8"))["L-2"]
        if transferred[7:9] != ("TRANSFER: destination/L-2", "closed"):
            fail("validated learning transfer receipt mismatch")
        closed = plan.read_text(encoding="utf-8")
        result, _ = quietly(
            module.checkpoint,
            str(root), str(plan), module.checkpoint_token(closed), [], [], [], [], [], [], [], True,
        )
        if result != 0 or module.parse_learning_candidates(plan.read_text(encoding="utf-8")):
            fail("atomic closed chronology prune failed")
        closed = plan.read_text(encoding="utf-8")
        result, _ = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            module.checkpoint_token(closed),
            ["lifecycle_status=build-ready"],
            [],
            [],
            [],
        )
        if result != 4 or plan.read_text(encoding="utf-8") != closed:
            fail("invalid transition changed PLAN")


def check_complete_slice(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-complete-slice-") as temporary:
        root = Path(temporary)
        init_repo(root)
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
        ).strip()
        plan = root / "features/fixture/PLAN.md"
        plan.parent.mkdir(parents=True)
        text = candidate_plan_text(root, head, module.repository_snapshot_id(root)).replace(
            "- artifact_id = sha256:" + "0" * 64,
            f"- artifact_id = {module.repository_artifact_id(root)}",
        )
        plan.write_text(text, encoding="utf-8")
        module.write_approval_receipt(root, module.parse_state(text))
        (root / "README.md").write_text("slice complete\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
        result, output = quietly(
            module.complete_active_slice, str(root), str(plan), module.checkpoint_token(text),
        )
        state = module.validate_document(plan, plan.read_text(encoding="utf-8"))
        if (result != 0 or "result=checkpointed" not in output
                or state["completed_slices"] != "S-1" or state["active_slice"] != "S-2"
                or state["next_action"] != "Admit and build S-2."
                or state["snapshot_id"] != module.repository_snapshot_id(root)
                or state["build_evidence"] != "stale"):
            fail("complete-slice did not atomically reconcile drift and advance the prefix")


def expect_rejected(module, source, destination, plan, token, includes, error: str) -> None:
    source_before = plan.read_bytes()
    destination_plan = destination / "features/fixture/PLAN.md"
    destination_before = destination_plan.read_bytes() if destination_plan.exists() else None
    result, output = quietly(
        module.transfer, str(source), str(destination), str(plan), token, includes
    )
    destination_after = destination_plan.read_bytes() if destination_plan.exists() else None
    if result != 4 or error not in output:
        fail(f"transfer rejection missed: {error}")
    if plan.read_bytes() != source_before or destination_after != destination_before:
        fail(f"rejected transfer mutated PLAN: {error}")


def check_transfer(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-transfer-") as temporary:
        fixture = Path(temporary)
        source = fixture / "source"
        target = fixture / "target"
        rollback_target = fixture / "rollback"
        different_head = fixture / "different-head"
        other = fixture / "other"
        init_repo(source)
        for destination in (target, rollback_target, different_head):
            linked(source, destination)
        result, _ = quietly(module.initialize, str(source), "fixture", None)
        if result != 0:
            fail("transfer PLAN initialization failed")
        plan = source / "features/fixture/PLAN.md"
        (source / "PRODUCT.md").write_text("approved context\n", encoding="utf-8")
        artifact = source / "features/fixture/DECISIONS.md"
        artifact.write_text("approved decision\n", encoding="utf-8")
        token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
        includes = ["PRODUCT.md", "features/fixture/DECISIONS.md"]

        expect_rejected(module, source, target, plan, "0" * 64, includes, "stale checkpoint token")
        for invalid, error in (
            ("../outside", "invalid include path"),
            ("*.md", "include path must be exact"),
            ("features", "must be a regular file"),
        ):
            expect_rejected(module, source, target, plan, token, [invalid], error)
        symlink = source / "linked-secret"
        symlink.symlink_to(source / "PRODUCT.md")
        expect_rejected(module, source, target, plan, token, ["linked-secret"], "symlink include path forbidden")
        symlink.unlink()

        (source / "collision.txt").write_text("source dirt\n", encoding="utf-8")
        (target / "collision.txt").write_text("destination dirt\n", encoding="utf-8")
        expect_rejected(
            module,
            source,
            target,
            plan,
            token,
            ["collision.txt"],
            "destination path is dirty or colliding",
        )
        (source / "collision.txt").unlink()
        (target / "collision.txt").unlink()

        (different_head / "README.md").write_text("new head\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(different_head), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(different_head), "commit", "-q", "-m", "different"], check=True)
        expect_rejected(module, source, different_head, plan, token, includes, "HEAD must match")

        init_repo(other)
        expect_rejected(
            module,
            source,
            other,
            plan,
            token,
            includes,
            "share one Git common directory",
        )

        rollback_source = plan.read_bytes()
        calls = 0

        def fail_write(_event):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("injected post-replacement write failure")
        result, output = quietly(
            transfer_direct,
            module,
            source,
            rollback_target,
            plan,
            token,
            includes,
            fail_write,
        )
        if result != 4 or "post-replacement" not in output or plan.read_bytes() != rollback_source:
            fail("post-replacement failure did not roll back source PLAN")
        if (rollback_target / "features/fixture/PLAN.md").exists():
            fail("write failure left destination PLAN")
        transfer_globals = module.transfer_plan.__globals__
        original_repo_write = transfer_globals["repo_write"]
        io_globals = original_repo_write.__globals__; original_fsync = io_globals["os"].fsync; fsync_calls = 0
        def fail_post_replace_fsync(descriptor):
            nonlocal fsync_calls
            fsync_calls += 1
            if fsync_calls == 2: raise OSError("injected post-replace fsync failure")
            return original_fsync(descriptor)
        io_globals["os"].fsync = fail_post_replace_fsync
        try: result, _ = quietly(transfer_direct, module, source, rollback_target, plan, token, includes, None)
        finally: io_globals["os"].fsync = original_fsync
        if result != 4 or plan.read_bytes() != rollback_source: fail("post-replace fsync failure escaped source rollback")
        def fail_source_restore(root, relative, content, mode, **kwargs):
            if root == source and content == rollback_source:
                raise OSError("injected restore failure")
            return original_repo_write(root, relative, content, mode, **kwargs)
        transfer_globals["repo_write"] = fail_source_restore
        calls = 0
        try:
            result, output = quietly(
                transfer_direct, module, source, rollback_target, plan, token, includes, fail_write
            )
        finally:
            transfer_globals["repo_write"] = original_repo_write
        common = Path(subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True
        ).strip())
        manifest = common / "hard-eng-plan-transfer.json"
        if result != 4 or "rollback failed" not in output or not manifest.is_file():
            fail("failed rollback retired its recovery manifest")
        original_repo_write(source, plan.relative_to(source), rollback_source, stat.S_IMODE(plan.stat().st_mode))
        transfer_globals["remove_manifest"](common)
        calls = 0
        def crash_write(_event):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise KeyboardInterrupt("injected crash")

        result, output = quietly(
            transfer_direct, module, source, target, plan, token, includes, crash_write
        )
        if result != 4 or "transfer interrupted: KeyboardInterrupt" not in output:
            fail("controlled interruption omitted structured failure: " + output.strip())
        if plan.read_bytes() != rollback_source or (target / "features/fixture/PLAN.md").exists():
            fail("controlled interruption did not roll back exact transfer state")
        result, output = quietly(module.transfer, str(source), str(target), str(plan), token, includes)
        if result != 0 or "resumed=no" not in output:
            fail("clean transfer failed after interruption rollback")

        destination_plan = target / "features/fixture/PLAN.md"
        destination_text = destination_plan.read_text(encoding="utf-8")
        destination_state = module.validate_document(destination_plan, destination_text)
        if destination_state["repository_root"] != str(target.resolve()):
            fail("transfer did not rebind repository_root")
        if plan.read_text(encoding="utf-8") != destination_text:
            fail("source PLAN does not point at destination owner")
        if (target / "PRODUCT.md").read_text(encoding="utf-8") != "approved context\n":
            fail("transfer omitted modified context")
        if (target / "features/fixture/DECISIONS.md").read_text(encoding="utf-8") != "approved decision\n":
            fail("transfer omitted untracked artifact")
        if quietly(module.inspect, str(source), str(plan))[0] != 5:
            fail("source remained a fresh PLAN writer")
        if quietly(module.inspect, str(target), str(destination_plan))[0] != 0:
            fail("destination is not the sole fresh PLAN writer")
        common_dir = Path(
            subprocess.check_output(
                ["git", "-C", str(source), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                text=True,
            ).strip()
        )
        lock = common_dir / "hard-eng-plan-transfer.lock"
        if not lock.is_file() or stat.S_IMODE(lock.stat().st_mode) != 0o600:
            fail("transfer lock is missing or not owner-only")


def check_kill_resume(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-transfer-kill-") as temporary:
        root = Path(temporary)
        source, target = root / "source", root / "target"
        init_repo(source)
        linked(source, target)
        if quietly(module.initialize, str(source), "fixture", None)[0] != 0:
            fail("kill-resume PLAN initialization failed")
        plan = source / "features/fixture/PLAN.md"
        (source / "PRODUCT.md").write_text("approved context\n", encoding="utf-8")
        decision = source / "features/fixture/DECISIONS.md"
        decision.write_text("approved decision\n", encoding="utf-8")
        includes = ["PRODUCT.md", "features/fixture/DECISIONS.md"]
        token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
        child = r'''
import sys
import time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import plan_state as module
def pause_after_source(event):
    if event == "source-written":
        print("SOURCE_STALE", flush=True)
        time.sleep(60)
raise SystemExit(module.transfer_plan(
    sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6:],
    git_identity=module.git_identity, canonical_plan=module.canonical_plan,
    checkpoint_token=module.checkpoint_token, document_token=module.document_token,
    validate_document=module.validate_document, freshness_errors=module.freshness_errors,
    replace_state=module.replace_state, emit=module.emit, fault_hook=pause_after_source,
))
'''
        process = subprocess.Popen(
            [sys.executable, "-c", child, str(SCRIPT_DIR), str(source), str(target), str(plan), token, *includes],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if process.stdout is None or not select.select([process.stdout], [], [], 10)[0]:
            process.kill()
            fail("kill-resume child never reached durable source-stale boundary")
        if process.stdout.readline().strip() != "SOURCE_STALE":
            process.kill()
            fail("kill-resume child emitted wrong boundary marker")
        process.kill()
        process.wait(timeout=10)
        common = Path(subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True
        ).strip())
        manifest = common / "hard-eng-plan-transfer.json"
        if not manifest.is_file() or stat.S_IMODE(manifest.stat().st_mode) != 0o600:
            fail("SIGKILL lost the durable owner-only transfer manifest")
        resumed_token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
        product = source / includes[0]
        product.write_text("tampered context\n", encoding="utf-8")
        result, output = quietly(
            module.transfer, str(source), str(target), str(plan), resumed_token, includes
        )
        if result != 4 or "bundle differ from manifest" not in output or not manifest.is_file():
            fail("resume accepted changed include content")
        product.write_text("approved context\n", encoding="utf-8")
        product.chmod(0o600)
        result, output = quietly(
            module.transfer, str(source), str(target), str(plan), resumed_token, includes
        )
        if result != 4 or "bundle differ from manifest" not in output or not manifest.is_file():
            fail("resume accepted changed include mode")
        product.chmod(0o644)
        result, output = quietly(
            module.transfer, str(source), str(target), str(plan), resumed_token, includes[:1]
        )
        if result != 4 or "bundle differ from manifest" not in output or not manifest.is_file():
            fail("resume accepted a reduced include bundle")
        result, output = quietly(
            module.checkpoint, str(source), str(plan), resumed_token, [], [], [], []
        )
        if result != 4 or "pending PLAN transfer" not in output:
            fail("checkpoint bypassed a durable pending transfer")
        result, output = quietly(
            module.transfer, str(source), str(target), str(plan), resumed_token, includes
        )
        if result != 0 or "resumed=yes" not in output or manifest.exists():
            fail("exact transfer did not resume and retire its manifest")
        destination_plan = target / "features/fixture/PLAN.md"
        if quietly(module.inspect, str(source), str(plan))[0] != 5:
            fail("kill-resume source remained fresh")
        if quietly(module.inspect, str(target), str(destination_plan))[0] != 0:
            fail("kill-resume destination did not become sole fresh owner")
        if (target / includes[0]).read_text(encoding="utf-8") != "approved context\n":
            fail("kill-resume omitted tracked context")
        if (target / includes[1]).read_text(encoding="utf-8") != "approved decision\n":
            fail("kill-resume omitted untracked context")


def check_concurrent_transfer(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-transfer-race-") as temporary:
        fixture = Path(temporary)
        source = fixture / "source"
        target_a = fixture / "target-a"
        target_b = fixture / "target-b"
        init_repo(source)
        linked(source, target_a)
        linked(source, target_b)
        result, _ = quietly(module.initialize, str(source), "fixture", None)
        if result != 0:
            fail("concurrent transfer PLAN initialization failed")
        plan = source / "features/fixture/PLAN.md"
        (source / "PRODUCT.md").write_text("approved context\n", encoding="utf-8")
        token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
        base = [
            sys.executable,
            str(PLAN_STATE_PATH),
            "transfer",
            "--repo",
            str(source),
            "--plan",
            str(plan),
            "--expect-token",
            token,
            "--include",
            "PRODUCT.md",
        ]
        processes = [
            subprocess.Popen(
                [*base, "--to-repo", str(target)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for target in (target_a, target_b)
        ]
        results = [(process.wait(), process.stdout.read(), process.stderr.read()) for process in processes]
        if sorted(result[0] for result in results) != [0, 4]:
            fail("concurrent transfer did not elect exactly one owner")
        fresh = 0
        for target in (target_a, target_b):
            target_plan = target / "features/fixture/PLAN.md"
            if target_plan.exists() and quietly(module.inspect, str(target), str(target_plan))[0] == 0:
                fresh += 1
        if fresh != 1 or quietly(module.inspect, str(source), str(plan))[0] != 5:
            fail("concurrent transfer left multiple fresh PLAN writers")


def check_transfer_checkpoint_race(module) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-writer-race-") as temporary:
        root = Path(temporary)
        source, target = root / "source", root / "target"
        init_repo(source)
        linked(source, target)
        if quietly(module.initialize, str(source), "fixture", None)[0] != 0:
            fail("writer race PLAN initialization failed")
        plan = source / "features/fixture/PLAN.md"
        (source / "PRODUCT.md").write_text("approved context\n", encoding="utf-8")
        token = module.checkpoint_token(plan.read_text(encoding="utf-8"))
        common = Path(subprocess.check_output(
            ["git", "-C", str(source), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True
        ).strip())
        lock_path = common / "hard-eng-plan-transfer.lock"
        with lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            transfer = subprocess.Popen([
                sys.executable, str(PLAN_STATE_PATH), "transfer", "--repo", str(source),
                "--to-repo", str(target), "--plan", str(plan), "--expect-token", token,
                "--include", "PRODUCT.md",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            checkpoint = subprocess.Popen([
                sys.executable, str(PLAN_STATE_PATH), "checkpoint", "--repo", str(source),
                "--plan", str(plan), "--expect-token", token, "--set", "next_action=Race checkpoint won.",
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            time.sleep(0.2)
            if transfer.poll() is not None or checkpoint.poll() is not None:
                fail("PLAN writer bypassed the common repository lock")
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        results = [transfer.communicate(timeout=10), checkpoint.communicate(timeout=10)]
        if sorted((transfer.returncode, checkpoint.returncode)) != [0, 4]:
            fail("transfer/checkpoint race did not elect one writer: " + repr(results))
        destination = target / "features/fixture/PLAN.md"
        source_fresh = quietly(module.inspect, str(source), str(plan))[0] == 0
        destination_fresh = destination.exists() and quietly(module.inspect, str(target), str(destination))[0] == 0
        if source_fresh == destination_fresh:
            fail("transfer/checkpoint race did not leave exactly one fresh owner")
        winner = plan if source_fresh else destination
        has_checkpoint = "Race checkpoint won." in winner.read_text(encoding="utf-8")
        if has_checkpoint != source_fresh:
            fail("transfer/checkpoint race lost or leaked the winning update")


def check_snapshot_reconciliation(module) -> None:
    state = {"lifecycle_status": "green", "snapshot_id": "sha256:" + "0" * 64,
             "artifact_id": "sha256:" + "0" * 64, "active_slice": "none", "build_round": "7"}
    actual, artifact = "sha256:" + "1" * 64, "sha256:" + "2" * 64
    updates = module.snapshot_reconciliation(state, actual, artifact)
    expected = {"lifecycle_status": "building", "active_slice": "final", "build_round": "8",
                "snapshot_id": actual, "artifact_id": artifact, "build_evidence": "stale", "build_readiness": "0"}
    if any(updates.get(key) != value for key, value in expected.items()):
        fail("repository snapshot drift did not invalidate evidence")
    if not module.snapshot_drift(state, actual, artifact) or module.snapshot_reconciliation(
        state, state["snapshot_id"], state["artifact_id"]
    ):
        fail("repository snapshot drift detection is inconsistent")
    building = {**state, "lifecycle_status": "building", "active_slice": "final"}
    if module.snapshot_reconciliation(building, actual, artifact)["build_round"] != "7":
        fail("ordinary build drift incremented the accepted-finding round")


def check_audit_finding_lifecycle(module) -> None:
    snapshot = "sha256:" + "1" * 64
    finding = {"id": "A-1", "axis": "standards", "severity": "critical",
               "evidence": "owner.py:1", "risk": "unsafe", "fix": "repair", "required": True}
    row = ("I-99", *finding_issue(finding, snapshot), "open")
    module.validate_audit_items({"I-99": row})
    closed = list(row)
    closed[5] = "disposition=fixed; proof=contracts-pass; re-audit=pending"
    closed[6] = "closed"
    module.validate_audit_items({"I-99": tuple(closed)})
    try:
        module.validate_audit_reaudit_complete({"I-99": tuple(closed)}, snapshot)
    except module.PlanStateError:
        pass
    else:
        fail("pending audit finding allowed post-build completion")
    closed[5] = f"disposition=fixed; proof=contracts-pass; re-audit=pass@{snapshot}"
    module.validate_audit_reaudit_complete({"I-99": tuple(closed)}, snapshot)
    try:
        module.validate_audit_reaudit_complete(
            {"I-99": tuple(closed)}, "sha256:" + "2" * 64
        )
    except module.PlanStateError:
        pass
    else:
        fail("stale audit receipt allowed post-build completion")
    closed[5] = "disposition=fixed; proof=pending; re-audit=pending"
    try:
        module.validate_audit_items({"I-99": tuple(closed)})
    except module.PlanStateError:
        return
    fail("audit finding closed without proof and re-audit provenance")


def main() -> int:
    module = load_plan_state()
    check_legacy_migration(module, fail, init_repo, quietly)
    check_checkpoint(module)
    check_complete_slice(module)
    check_transfer(module)
    check_kill_resume(module)
    check_concurrent_transfer(module)
    check_transfer_checkpoint_race(module)
    check_snapshot_reconciliation(module)
    check_build_head_reconciliation(module, fail, quietly)
    check_audit_finding_lifecycle(module)
    check_learning_lifecycle_boundary(module, fail, init_repo, quietly)
    print("he-state-integration: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
