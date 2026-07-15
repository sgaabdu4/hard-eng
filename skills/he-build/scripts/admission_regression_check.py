import io
import fcntl
import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def candidate_plan_text(root, base, snapshot, *, active="S-1", completed="none"):
    text = (
        "# Fixture\n\n## State\n- state_version = 4\n- plan_id = fixture\n"
        f"- feature_slug = fixture\n- repository_root = {root}\n- branch = main\n"
        f"- base_sha = {base}\n- head_sha = {base}\n- updated_at_utc = 2026-01-01T00:00:00Z\n"
        "- lifecycle_status = building\n- current_stage = build\n- plan_stage = none\n"
        "- approved_plan_stages = repository,research,feature,flows,contracts,technical,testing,rollout,slices,consistency,approval\n"
        "- skipped_plan_stages = ux\n- stage_status = in-progress\n"
        "- next_action = Verify active candidate.\n- waiting_for = agent\n- plan_approved = yes\n"
        "- approved_plan_digest = none\n"
        "- open_blockers = none\n- open_issues = none\n- open_unknowns = none\n"
        f"- active_slice = {active}\n- slice_count = 2\n- completed_slices = {completed}\n"
        f"- build_round = 0\n- snapshot_id = {snapshot}\n"
        f"- artifact_id = {'sha256:' + '0' * 64}\n"
        "- build_axes = intent-spec:pending,deterministic:pending,tests:pending,review:pending,security:pending,ui-design:pending,e2e-runtime:pending,docs-context:pending,unknowns:pending\n"
        "- build_readiness = 0\n- build_evidence = stale\n\n"
        "## Active items\n| ID | Type | Evidence | Impact | Owner | Next proof/action | Status |\n"
        "|---|---|---|---|---|---|---|\n\n"
        "## Learning Candidates\n| ID | Trigger | Source | Evidence | Cause | Owner | Required proof | Resolution | Status |\n"
        "|---|---|---|---|---|---|---|---|---|\n\n"
        "## Slices\n\n| ID | Outcome |\n|---|---|\n| S-1 | Owner |\n| S-2 | Caller |\n\n"
        "### S-1 — Owner\n- planned_paths = owner.py\n\n"
        "### S-2 — Caller\n- planned_paths = caller.py\n"
    )
    from plan_state import approved_plan_digest
    return text.replace(
        "- approved_plan_digest = none",
        f"- approved_plan_digest = {approved_plan_digest(text)}",
    )


def candidate_fixture(root, snapshot_id):
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    git(root, "config", "user.email", "fixture@example.com")
    git(root, "config", "user.name", "Fixture")
    for relative, content in {
        "AGENTS.md": "# Rules\n- Review only.\n",
        "PRODUCT.md": "# Product\n- Outcome = fixture.\n",
        "DESIGN.md": "# Design\n- UI = none.\n",
        "owner.py": "def public_api(value):\n    return value\n",
        "caller.py": "from owner import public_api\nvalue = public_api(1)\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "baseline")
    base = git(root, "rev-parse", "HEAD")
    plan = root / "features/fixture/PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(candidate_plan_text(root, base, snapshot_id(root)), encoding="utf-8")
    from plan_state import parse_state, write_approval_receipt
    write_approval_receipt(root, parse_state(plan.read_text(encoding="utf-8")))
    author = root.parent / "author"
    subprocess.run(["git", "clone", "-q", "--local", str(root), str(author)], check=True)
    (author / "owner.py").write_text(
        "def public_api(value):\n    return value.strip()\n", encoding="utf-8"
    )
    patch = root.parent / "candidate.patch"
    patch.write_bytes(subprocess.check_output(
        ["git", "-C", str(author), "diff", "--binary", "--full-index", "HEAD", "--", "."]
    ))
    return plan, patch


def gitlink_fixture(root, snapshot_id):
    module_root = root.parent / "module-source"
    subprocess.run(["git", "init", "-q", "-b", "main", str(module_root)], check=True)
    git(module_root, "config", "user.email", "fixture@example.com")
    git(module_root, "config", "user.name", "Fixture")
    (module_root / "value.txt").write_text("one\n", encoding="utf-8")
    git(module_root, "add", ".")
    git(module_root, "commit", "-q", "-m", "one")
    first = git(module_root, "rev-parse", "HEAD")
    (module_root / "value.txt").write_text("two\n", encoding="utf-8")
    git(module_root, "add", ".")
    git(module_root, "commit", "-q", "-m", "two")
    second = git(module_root, "rev-parse", "HEAD")
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    git(root, "config", "user.email", "fixture@example.com")
    git(root, "config", "user.name", "Fixture")
    for relative, content in {
        "AGENTS.md": "# Rules\n- Review only.\n",
        "PRODUCT.md": "# Product\n- Outcome = fixture.\n",
        "DESIGN.md": "# Design\n- UI = none.\n",
    }.items():
        (root / relative).write_text(content, encoding="utf-8")
    git(root, "add", ".")
    git(root, "update-index", "--add", "--cacheinfo", f"160000,{first},vendor/module")
    git(root, "commit", "-q", "-m", "baseline gitlink")
    base = git(root, "rev-parse", "HEAD")
    plan = root / "features/fixture/PLAN.md"
    plan.parent.mkdir(parents=True)
    text = candidate_plan_text(root, base, snapshot_id(root)).replace(
        "planned_paths = owner.py", "planned_paths = vendor/module"
    )
    plan.write_text(text, encoding="utf-8")
    from plan_state import parse_state, write_approval_receipt
    write_approval_receipt(root, parse_state(plan.read_text(encoding="utf-8")))
    git(root, "update-index", "--cacheinfo", f"160000,{second},vendor/module")
    patch = root.parent / "gitlink.patch"
    patch.write_bytes(subprocess.check_output(
        ["git", "-C", str(root), "diff", "--cached", "--binary", "--full-index", "HEAD"]
    ))
    git(root, "reset", "-q", "HEAD", "--", "vendor/module")
    return plan, patch


def check_admission_regressions(module, fail):
    required = (
        "ADMISSION_MAX_RELATED_SECTIONS",
        "ADMISSION_MAX_RELATED_BYTES",
        "ADMISSION_MAX_PACKET_BYTES",
        "evaluate_admission",
        "candidate_admission_report",
    )
    for name in required:
        if not hasattr(module, name):
            fail(f"admission owner missing: {name}")
    admission_owner = sys.modules[module.evaluate_admission.__module__]
    if not hasattr(admission_owner, "require_diagnostic_packet_limit"):
        fail("admission diagnostic packet ceiling owner missing")
    parameters = inspect.signature(module.review_packet_parts).parameters
    if parameters["related_max_sections"].default is not None or parameters["related_max_bytes"].default is not None:
        fail("final related-context ceilings have duplicate literal defaults")
    if (
        module.ADMISSION_MAX_RELATED_SECTIONS,
        module.ADMISSION_MAX_RELATED_BYTES,
        module.ADMISSION_MAX_PACKET_BYTES,
    ) != (96, 112 * 1024, 700 * 1024):
        fail("admission headroom limits drift")
    under = module.evaluate_admission(
        snapshot_id="sha256:" + "1" * 64,
        base_sha="a" * 40,
        changed_path_count=3,
        related_sections=96,
        related_bytes=112 * 1024,
        packet_bytes=700 * 1024,
        largest_units=(("owner.py", 200), ("caller.py", 100)),
    )
    if under["result"] != "pass" or under.get("error") is not None:
        fail("admission rejected exact headroom boundary")
    cases = (
        (97, 1, 1, "RELATED_CONTEXT_SECTIONS"),
        (96, 112 * 1024 + 1, 1, "RELATED_CONTEXT_BYTES"),
        (96, 112 * 1024, 700 * 1024 + 1, "PACKET_BYTES"),
    )
    for sections, context_bytes, packet_bytes, code in cases:
        report = module.evaluate_admission(
            snapshot_id="sha256:" + "2" * 64,
            base_sha="b" * 40,
            changed_path_count=4,
            related_sections=sections,
            related_bytes=context_bytes,
            packet_bytes=packet_bytes,
            largest_units=(("safe.py", 10),),
        )
        if report["result"] != "fail" or report.get("error", {}).get("code") != code:
            fail(f"admission did not reject {code}")
    many_units = tuple((f"owner-{index}.py", index) for index in range(20))
    bounded = module.evaluate_admission(
        snapshot_id="sha256:" + "3" * 64,
        base_sha="c" * 40,
        changed_path_count=20,
        related_sections=1,
        related_bytes=1,
        packet_bytes=1,
        largest_units=many_units,
    )
    if len(bounded["largestUnits"]) != 10 or bounded["largestUnits"][0]["bytes"] != 19:
        fail("admission largest-unit diagnostics are unbounded or unsorted")
    recurrence = module.evaluate_admission(
        snapshot_id="sha256:" + "4" * 64,
        base_sha="d" * 40,
        changed_path_count=188,
        related_sections=812,
        related_bytes=551678,
        packet_bytes=700 * 1024,
        largest_units=(("functions/payment-owner.dart", 400000), ("unsafe\nlabel", 151678)),
    )
    encoded_recurrence = json.dumps(recurrence, separators=(",", ":"))
    if (
        recurrence["result"] != "fail"
        or recurrence["error"]["code"] != "RELATED_CONTEXT_SECTIONS"
        or recurrence["relatedContext"]["bytes"] != 551678
        or recurrence["largestUnits"][0]["label"] != "functions/payment-owner.dart"
        or "\nlabel" in encoded_recurrence
    ):
        fail("high-cardinality recurrence did not fail with bounded sanitized ownership")
    context_headroom = module.evaluate_admission(
        snapshot_id="sha256:" + "5" * 64,
        base_sha="e" * 40,
        changed_path_count=2,
        related_sections=2,
        related_bytes=120000,
        packet_bytes=200000,
        largest_units=(("owner.py", 120000),),
    )
    packet_headroom = module.evaluate_admission(
        snapshot_id="sha256:" + "6" * 64,
        base_sha="f" * 40,
        changed_path_count=2,
        related_sections=2,
        related_bytes=1000,
        packet_bytes=750000,
        largest_units=(("owner.py", 749000),),
    )
    if context_headroom["error"]["code"] != "RELATED_CONTEXT_BYTES":
        fail("admission accepted context that only the final ceiling can fit")
    if packet_headroom["error"]["code"] != "PACKET_BYTES":
        fail("admission accepted packet that only the final ceiling can fit")
    owning_sections = tuple((f"owner-{index}.py", 1) for index in range(97))
    owning_overflow = module.evaluate_admission(
        snapshot_id="sha256:" + "7" * 64,
        base_sha="1" * 40,
        changed_path_count=97,
        related_sections=97,
        related_bytes=97,
        packet_bytes=1000,
        largest_units=owning_sections,
        related_units=owning_sections,
    )
    if owning_overflow["error"].get("owner") != "owner-96.py":
        fail("related-section overflow omitted the first threshold owner")
    try:
        admission_owner.require_diagnostic_packet_limit(
            admission_owner.DIAGNOSTIC_MAX_PACKET_BYTES + 1, module.AuditError
        )
    except module.AuditError:
        pass
    else:
        fail("full diagnostic packet ceiling was not enforced")
    if module.MAX_PACKET_BYTES != 800 * 1024:
        fail("admission changed the canonical final packet limit")
    with tempfile.TemporaryDirectory(prefix="he-candidate-gitlink-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch = gitlink_fixture(root, module.snapshot_id)
        before = module.snapshot_id(root)
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted an existing gitlink modification")
        helper = Path(module.__file__).with_name("apply_admitted_patch.py")
        rejected = subprocess.run(
            [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan),
             "--patch", str(patch), "--unit", "S-1", "--expect-base", before,
             "--expect-patch", "sha256:" + hashlib.sha256(patch.read_bytes()).hexdigest(),
             "--expect-candidate", "sha256:" + "0" * 64],
            capture_output=True, text=True, check=False,
        )
        rejection = json.loads(rejected.stdout) if rejected.stdout else {}
        if (rejected.returncode != 1
                or rejection.get("error", {}).get("code") != "INVALID_PATCH"
                or module.snapshot_id(root) != before):
            fail("apply accepted or mutated delivery for an existing gitlink patch")
    with tempfile.TemporaryDirectory(prefix="he-candidate-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        before = module.snapshot_id(root)
        original_argv = sys.argv
        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            sys.argv = [
                "audit.py", "--admission", "--candidate-patch", str(patch), "--unit", "S-1",
                "--repo", str(root), "--plan", str(plan),
            ]
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = module.main()
        finally:
            sys.argv = original_argv
        report = json.loads(stdout.getvalue())
        required = {
            "mode", "result", "unitId", "approvedPlanDigest", "completedSlices", "accumulatedPathCount",
            "accumulatedStateDigest", "baseSnapshotId", "baseSha", "candidateDigest",
            "candidateSnapshotId", "changedPathCount", "relatedContext", "packet",
            "largestUnits", "reviewShardCount", "error",
        }
        if (
            result != 0 or set(report) != required or report["result"] != "pass"
            or report["unitId"] != "S-1" or report["completedSlices"] != []
            or not report["approvedPlanDigest"].startswith("sha256:")
            or report["accumulatedPathCount"] != 0
            or report["reviewShardCount"] != 1
            or not report["candidateDigest"].startswith("sha256:")
            or not report["candidateSnapshotId"].startswith("sha256:")
            or module.snapshot_id(root) != before or stderr.getvalue()
        ):
            fail("immutable candidate CLI PASS/schema mutated delivery or drifted")
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-2")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted a non-active unit")
        original_plan = plan.read_text(encoding="utf-8")
        plan.write_text(original_plan.replace("planned_paths = owner.py", "planned_paths = caller.py"),
                        encoding="utf-8")
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted patch paths outside active manifest")
        finally:
            plan.write_text(original_plan, encoding="utf-8")
        state_owner = sys.modules[module.validate_document.__module__]
        forged = original_plan.replace("planned_paths = owner.py", "planned_paths = caller.py")
        forged = forged.replace(
            state_owner.parse_state(forged)["approved_plan_digest"],
            state_owner.approved_plan_digest(forged),
        )
        plan.write_text(forged, encoding="utf-8")
        forged_author = root.parent / "forged-author"
        subprocess.run(["git", "clone", "-q", "--local", str(root), str(forged_author)], check=True)
        (forged_author / "caller.py").write_text(
            "from owner import public_api\nvalue = public_api('forged')\n", encoding="utf-8"
        )
        forged_patch = subprocess.check_output(
            ["git", "-C", str(forged_author), "diff", "--binary", "--full-index", "HEAD", "--", "."]
        )
        try:
            module.candidate_admission_report(root, plan, forged_patch, "S-1")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted a manifest rewritten to fit candidate bytes")
        finally:
            plan.write_text(original_plan, encoding="utf-8")

        unsafe = module.candidate_error_report(
            module.AuditError("credential-assignment content blocks audit: functions/example/test/file.dart")
        )
        if unsafe["error"] != {
            "code": "UNSAFE_CONTENT",
            "marker": "credential-assignment",
            "path": "functions/example/test/file.dart",
        }:
            fail("candidate admission omitted safe structured failure diagnostics")
        missing = module.estimate_error_report(
            module.AuditError("invalid PLAN state: missing keys: approved_plan_digest")
        )["error"]
        if missing != {
            "code": "INVALID_PLAN", "reason": "MISSING_KEYS",
            "fields": "approved_plan_digest", "action": "migrate-state",
        }:
            fail("legacy PLAN missing-key diagnostic omitted migration action")
        version = module.estimate_error_report(
            module.AuditError("invalid PLAN state: unsupported state_version: 3; expected: 4")
        )["error"]
        if version != {
            "code": "INVALID_PLAN", "reason": "UNSUPPORTED_STATE_VERSION",
            "actual": "3", "expected": "4", "action": "migrate-state",
        }:
            fail("legacy PLAN version diagnostic omitted migration action")
        packet = module.estimate_error_report(
            module.AuditError("unresolved required local import: useFeature from ui/caller.ts")
        )["error"]
        if packet != {
            "code": "PACKET_BUILD", "reason": "UNRESOLVED_LOCAL_IMPORT",
            "symbol": "useFeature", "path": "ui/caller.ts",
        }:
            fail("packet failure omitted safe local-import diagnostics")
        module_import = module.estimate_error_report(
            module.AuditError(
                "unresolved local module import: ./AdminSteps.helpers from ui/modal.tsx"
            )
        )["error"]
        if module_import != {
            "code": "PACKET_BUILD", "reason": "UNRESOLVED_LOCAL_MODULE",
            "specifier": "./AdminSteps.helpers", "path": "ui/modal.tsx",
        }:
            fail("packet failure omitted safe local-module diagnostics")
        git(root, "add", plan.relative_to(root).as_posix())
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted a staged PLAN representation")
        finally:
            git(root, "reset", "-q", "HEAD", "--", plan.relative_to(root).as_posix())
        extra = root / "extra.py"
        extra.write_text("EXTRA = True\n", encoding="utf-8")
        git(root, "add", extra.name)
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted arbitrary staged accumulated state")
        finally:
            git(root, "reset", "-q", "HEAD", "--", extra.name)
            extra.unlink()
        extra.write_text("EXTRA = True\n", encoding="utf-8")
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted arbitrary untracked state")
        finally:
            extra.unlink()
        helper = Path(module.__file__).with_name("apply_admitted_patch.py")
        if not helper.is_file():
            fail("same-byte apply helper missing")
        applied = subprocess.run(
            [
                sys.executable, str(helper), "--repo", str(root), "--plan", str(plan), "--unit", "S-1",
                "--patch", str(patch), "--expect-base", report["baseSnapshotId"],
                "--expect-patch", report["candidateDigest"],
                "--expect-candidate", report["candidateSnapshotId"],
            ],
            capture_output=True, text=True, check=False,
        )
        receipt = json.loads(applied.stdout) if applied.stdout else {}
        if (
            applied.returncode != 0 or receipt.get("result") != "applied"
            or receipt.get("unitId") != "S-1" or receipt.get("completedSlices") != []
            or receipt.get("approvedPlanDigest") != report["approvedPlanDigest"]
            or receipt.get("accumulatedPathCount") != 0
            or receipt.get("accumulatedStateDigest") != report["accumulatedStateDigest"]
            or receipt.get("baseSnapshotId") != report["baseSnapshotId"]
            or receipt.get("candidateDigest") != report["candidateDigest"]
            or receipt.get("candidateSnapshotId") != report["candidateSnapshotId"]
            or receipt.get("appliedSnapshotId") != report["candidateSnapshotId"]
            or receipt.get("reviewShardCount") != report["reviewShardCount"]
            or git(root, "diff", "--cached", "--name-only") != "owner.py"
            or "value.strip()" not in (root / "owner.py").read_text(encoding="utf-8")
        ):
            fail("same-byte helper did not stage the admitted candidate exactly")
        plan.write_text(candidate_plan_text(root, git(root, "rev-parse", "HEAD"), module.snapshot_id(root),
                                            active="S-2", completed="S-1"), encoding="utf-8")
        author = root.parent / "author-s2"
        subprocess.run(["git", "clone", "-q", "--local", str(root), str(author)], check=True)
        (author / "caller.py").write_text(
            "from owner import public_api\nvalue = public_api('next')\n", encoding="utf-8"
        )
        patch_s2 = root.parent / "candidate-s2.patch"
        patch_s2.write_bytes(subprocess.check_output(
            ["git", "-C", str(author), "diff", "--binary", "--full-index", "HEAD", "--", "."]
        ))
        owner_bytes = (root / "owner.py").read_bytes()
        (root / "owner.py").write_bytes(owner_bytes + b"# tampered completed slice\n")
        git(root, "add", "owner.py")
        try:
            module.candidate_admission_report(root, plan, patch_s2.read_bytes(), "S-2")
        except (module.AuditError, module.CandidateError):
            pass
        else:
            fail("candidate admission accepted altered bytes on an accumulated manifest path")
        finally:
            (root / "owner.py").write_bytes(owner_bytes)
            git(root, "add", "owner.py")
        original_partition = module.partition_review_scopes
        admitted_primary_paths = []
        def capture_primary_paths(repo, candidate_plan, primary_paths, **kwargs):
            admitted_primary_paths.append(primary_paths)
            return original_partition(repo, candidate_plan, primary_paths, **kwargs)
        module.partition_review_scopes = capture_primary_paths
        try:
            report_s2 = module.candidate_admission_report(root, plan, patch_s2.read_bytes(), "S-2")
        finally:
            module.partition_review_scopes = original_partition
        if (report_s2["result"] != "pass" or report_s2["completedSlices"] != ["S-1"]
                or report_s2["accumulatedPathCount"] != 1 or report_s2["reviewShardCount"] != 1):
            fail("second candidate did not admit against accumulated first-slice state")
        if admitted_primary_paths != [("caller.py",)]:
            fail("candidate admission re-reviewed the accumulated completed-slice prefix")
        applied_s2 = subprocess.run(
            [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan),
             "--patch", str(patch_s2), "--unit", "S-2",
             "--expect-base", report_s2["baseSnapshotId"],
             "--expect-patch", report_s2["candidateDigest"],
             "--expect-candidate", report_s2["candidateSnapshotId"]],
            capture_output=True, text=True, check=False,
        )
        if (applied_s2.returncode != 0
                or git(root, "diff", "--cached", "--name-only").splitlines() != ["caller.py", "owner.py"]):
            fail("accumulated staged workflow deadlocked after the first slice")
    with tempfile.TemporaryDirectory(prefix="he-apply-negative-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        module_report = module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        helper = Path(module.__file__).with_name("apply_admitted_patch.py")
        before = module.snapshot_id(root)
        cases = (
            ("digest", module_report["baseSnapshotId"], "sha256:" + "0" * 64,
             module_report["candidateSnapshotId"], "INVALID_PATCH"),
            ("base", "sha256:" + "0" * 64, module_report["candidateDigest"],
             module_report["candidateSnapshotId"], "STALE_SNAPSHOT"),
            ("candidate", module_report["baseSnapshotId"], module_report["candidateDigest"],
             "sha256:" + "0" * 64, "INVALID_PATCH"),
        )
        for label, base, digest, candidate, code in cases:
            rejected = subprocess.run(
                [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan), "--unit", "S-1",
                 "--patch", str(patch), "--expect-base", base, "--expect-patch", digest,
                 "--expect-candidate", candidate],
                capture_output=True, text=True, check=False,
            )
            rejection = json.loads(rejected.stdout) if rejected.stdout else {}
            if (rejected.returncode != 1 or rejection.get("error", {}).get("code") != code
                    or module.snapshot_id(root) != before):
                fail(f"{label} rejection mutated delivery or returned wrong code")
        common = Path(git(root, "rev-parse", "--git-common-dir"))
        common = (root / common).resolve() if not common.is_absolute() else common
        descriptor = os.open(common / "hard-eng-candidate-apply.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = subprocess.run(
                [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan), "--unit", "S-1",
                 "--patch", str(patch), "--expect-base", module_report["baseSnapshotId"],
                 "--expect-patch", module_report["candidateDigest"],
                 "--expect-candidate", module_report["candidateSnapshotId"]],
                capture_output=True, text=True, check=False,
            )
        finally:
            os.close(descriptor)
        locked_report = json.loads(locked.stdout) if locked.stdout else {}
        if (locked.returncode != 1 or locked_report.get("error", {}).get("code") != "LOCKED"
                or module.snapshot_id(root) != before):
            fail("held apply lock did not fail closed before mutation")
    with tempfile.TemporaryDirectory(prefix="he-apply-rollback-") as temporary:
        import apply_admitted_patch as apply_module
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        report = module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        index_raw = subprocess.check_output(["git", "-C", str(root), "rev-parse", "--git-path", "index"],
                                            text=True).strip()
        index_path = Path(index_raw)
        if not index_path.is_absolute():
            index_path = (root / index_path).resolve()
        before_index = index_path.read_bytes()
        before_owner = (root / "owner.py").read_bytes()
        before_snapshot = module.snapshot_id(root)
        original_apply = apply_module.apply_bytes
        apply_module.apply_bytes = lambda target, data: (
            original_apply(target, data),
            (_ for _ in ()).throw(apply_module.ApplyError("APPLY_CONFLICT", "forced post-apply mismatch")),
        )[-1]
        try:
            try:
                apply_module.apply_candidate(
                    root=root, plan=plan, patch=patch, unit="S-1",
                    expect_base=report["baseSnapshotId"], expect_patch=report["candidateDigest"],
                    expect_candidate=report["candidateSnapshotId"],
                )
            except apply_module.ApplyError as error:
                if error.code != "APPLY_CONFLICT":
                    fail("post-apply failure returned the wrong code after rollback")
            else:
                fail("forced post-apply failure unexpectedly passed")
        finally:
            apply_module.apply_bytes = original_apply
        if (index_path.read_bytes() != before_index or (root / "owner.py").read_bytes() != before_owner
                or module.snapshot_id(root) != before_snapshot):
            fail("post-apply failure did not restore exact index/worktree preimages")
    with tempfile.TemporaryDirectory(prefix="he-apply-rollback-failed-") as temporary:
        import apply_admitted_patch as apply_module
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        report = module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        original_apply = apply_module.apply_bytes
        original_restore = apply_module.restore_preimage
        apply_module.apply_bytes = lambda target, data: (
            original_apply(target, data),
            (_ for _ in ()).throw(apply_module.ApplyError("APPLY_CONFLICT", "forced mismatch")),
        )[-1]
        apply_module.restore_preimage = lambda *_: (_ for _ in ()).throw(OSError("forced restore failure"))
        try:
            try:
                apply_module.apply_candidate(
                    root=root, plan=plan, patch=patch, unit="S-1",
                    expect_base=report["baseSnapshotId"], expect_patch=report["candidateDigest"],
                    expect_candidate=report["candidateSnapshotId"],
                )
            except apply_module.ApplyError as error:
                if error.code != "ROLLBACK_FAILED":
                    fail("restore failure did not emit the distinct hard-stop code")
            else:
                fail("forced restore failure unexpectedly passed")
        finally:
            apply_module.apply_bytes = original_apply
            apply_module.restore_preimage = original_restore
    with tempfile.TemporaryDirectory(prefix="he-apply-concurrent-drift-") as temporary:
        import apply_admitted_patch as apply_module
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        report = module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        original_apply = apply_module.apply_bytes
        caller = root / "caller.py"
        concurrent = "from owner import public_api\nvalue = public_api('concurrent')\n"
        def apply_with_external_drift(target, data):
            original_apply(target, data)
            caller.write_text(concurrent, encoding="utf-8")
            git(target, "add", "caller.py")
            raise apply_module.ApplyError("APPLY_CONFLICT", "forced concurrent drift")
        apply_module.apply_bytes = apply_with_external_drift
        try:
            try:
                apply_module.apply_candidate(
                    root=root, plan=plan, patch=patch, unit="S-1",
                    expect_base=report["baseSnapshotId"], expect_patch=report["candidateDigest"],
                    expect_candidate=report["candidateSnapshotId"],
                )
            except apply_module.ApplyError as error:
                if error.code != "ROLLBACK_FAILED":
                    fail("concurrent apply drift did not hard-stop rollback")
            else:
                fail("concurrent apply drift unexpectedly passed")
        finally:
            apply_module.apply_bytes = original_apply
        if (caller.read_text(encoding="utf-8") != concurrent
                or "caller.py" not in git(root, "diff", "--cached", "--name-only").splitlines()):
            fail("rollback overwrote concurrent external index/worktree state")
