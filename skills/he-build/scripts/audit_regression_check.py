import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
STATE_SCRIPT_DIR = SCRIPT_DIR.parents[1] / "he/scripts"
if str(STATE_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(STATE_SCRIPT_DIR))
import audit_packet
import audit_result
import related_context as related_context_owner
from audit_performance_regression_check import check_audit_performance_regressions
from audit_result_regression_check import check_audit_result_regressions
from secret_scanner_regression_check import check_assignment_matrix

def run(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def fixture(root):
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    run(root, "config", "user.email", "f@x")
    run(root, "config", "user.name", "F")
    files = {"AGENTS.md": "# Rules\n- Review.\n", "PRODUCT.md": "# Product\n- Outcome = fixture.\n",
             "DESIGN.md": "# Design\n- UI = none.\n", "tracked.env": "DEPLOY_TOKEN=fixture\n"}
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    run(root, "add", ".")
    run(root, "commit", "-q", "-m", "baseline")
    plan = root / "features/fixture/PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(f"# Fixture\n- base_sha = {run(root, 'rev-parse', 'HEAD')}\n", encoding="utf-8")
    return plan


def rejects(module, root, plan, fail, label):
    try:
        module.review_packet(root, plan)
    except module.AuditError:
        return
    fail(f"audit accepted {label}")


def check_audit_regressions(module, fail):
    check_audit_performance_regressions(module, fail)
    rules = audit_packet.applicable_rule_paths(
        ("AGENTS.md", "AGENTS.override.md", "pkg/AGENTS.md", "pkg/AGENTS.override.md", "other/AGENTS.md"),
        ("pkg/owner.py",),
    )
    if rules != ("AGENTS.md", "AGENTS.override.md", "pkg/AGENTS.md", "pkg/AGENTS.override.md"):
        fail("audit rule discovery omitted or mis-scoped AGENTS override precedence")
    error_event = '{"type":"item.completed","item":{"type":"error"}}'
    recovering = module.new_event_state()
    module.consume_event(error_event, recovering, False)
    if recovering.stage != "transport-recovering" or recovering.completed_items != 0:
        fail("recoverable transport event changed review evidence state")
    post_evidence = module.new_event_state(); post_evidence.completed_items = 1
    module.consume_event(error_event, post_evidence, False)
    if post_evidence.completed_items != 1:
        fail("recoverable transport event replaced completed review evidence")
    reasoning = module.new_event_state()
    module.consume_event('{"type":"item.completed","item":{"type":"reasoning"}}', reasoning, False)
    if reasoning.completed_items != 0:
        fail("reasoning incorrectly consumed the zero-review retry boundary")
    with tempfile.TemporaryDirectory(prefix="he-missing-auth-") as temporary:
        try:
            module.isolated_environment(Path(temporary), Path(temporary) / "missing")
        except module.AuditError:
            pass
        else:
            fail("audit accepted missing controller auth")
    prompt = module.audit_prompt("sha256:" + "0" * 64, "sha256:" + "0" * 64, "packet")
    prompt_contract = ("Current-state authority = `## Authoritative final base-to-worktree diff`", "Commit provenance = metadata only",
                       "Every finding object must include the boolean `required`", "Uncertain blockingness => unknowns, never an incomplete finding")
    for required_prompt in prompt_contract:
        if required_prompt not in prompt:
            fail(f"audit prompt missing final-artifact contract: {required_prompt}")
    if "Finding without required disposition" in prompt:
        fail("audit prompt advertises parent recovery as a valid child output")
    snapshot = "sha256:" + "1" * 64
    clean = {"snapshot_id": snapshot, "verdict": "pass", "findings": [], "unknowns": [], "summary": "clean"}
    check_audit_result_regressions(module, fail, snapshot)
    required = {"id": "A-1", "axis": "spec", "severity": "critical", "evidence": "a.py:1",
                "risk": "wrong", "fix": "repair", "required": True}
    vague = {**clean, "verdict": "fail", "findings": [{**required, "evidence": "some code is wrong"}]}
    try: module.validate_result(vague, snapshot)
    except module.AuditError: pass
    else: fail("audit accepted uncited finding evidence")
    root_hunk = {**clean, "verdict": "fail", "findings": [{**required, "evidence": "package.json changed hunk"}]}
    if module.validate_result(root_hunk, snapshot)["findings"][0]["evidence"] != "package.json changed hunk":
        fail("audit rejected an exact root-file hunk citation")
    duplicated = {**clean, "verdict": "fail", "findings": [dict(required), dict(required)]}
    normalized = audit_result.assign_finding_ids(duplicated)
    if [finding["id"] for finding in normalized["findings"]] != ["A-1", "A-2"]:
        fail("audit parent did not own deterministic finding IDs")
    extra = audit_result.assign_finding_ids({**clean, "verdict": "fail", "findings": [{**required, "title": "display only"}]})
    if module.validate_result(extra, snapshot)["findings"][0].get("title") is not None:
        fail("audit retained non-canonical finding fields")
    missing = {key: value for key, value in required.items() if key != "risk"}
    try:
        module.validate_result(audit_result.assign_finding_ids({**clean, "verdict": "fail", "findings": [missing]}), snapshot)
    except module.AuditError as error:
        if "missing=risk; extra=none" not in str(error):
            fail("audit missing-field diagnostic is not actionable")
    else:
        fail("audit normalization accepted missing canonical finding field")
    shard_pass = dict(clean)
    shard_fail = {**clean, "verdict": "fail", "findings": [dict(required)]}
    combined = audit_result.aggregate_audit_results(snapshot, (shard_pass, shard_fail, shard_fail))
    if (combined["verdict"] != "fail" or len(combined["findings"]) != 1
            or combined["findings"][0]["id"] != "A-1"):
        fail("audit shard aggregation lost the strictest verdict or deterministic deduplication")
    attempts = []
    def flaky():
        attempts.append(1)
        if len(attempts) == 1:
            raise module.RetryableAuditError("transport")
        return "pass"
    if module.one_infrastructure_retry(flaky, module.RetryableAuditError, lambda: None) != "pass" or len(attempts) != 2:
        fail("audit did not bound an evidence-qualified infrastructure retry")
    attempts.clear()
    try:
        module.one_infrastructure_retry(lambda: (_ for _ in ()).throw(module.RetryableAuditError("stall")),
                                        module.RetryableAuditError, lambda: attempts.append(1))
    except module.RetryableAuditError:
        pass
    else:
        fail("audit accepted a second infrastructure stall")
    if len(attempts) != 1:
        fail("audit retried an infrastructure stall more than once")
    if module.bounded_timeout(module.time.monotonic() + 10, 3, module.AuditError) != 3:
        fail("audit timeout ignored the whole-run deadline")
    if module.bounded_timeout(
        module.time.monotonic() + 4, 4, module.AuditError, reserve_retry=True
    ) != 1:
        fail("audit first attempt did not reserve the retry deadline")
    timed_attempts = []
    def timed_retry():
        timed_attempts.append(1)
        budget = module.bounded_timeout(
            timed_deadline, 4, module.AuditError, reserve_retry=len(timed_attempts) == 1
        )
        if len(timed_attempts) == 1:
            return module.run_codex_stream(
                [sys.executable, "-c", "import sys,time;sys.stdin.read();time.sleep(2)"], "packet", budget
            )
        return "pass"
    timed_deadline = module.time.monotonic() + 4
    if module.one_infrastructure_retry(
        timed_retry, module.RetryableAuditError, lambda: None
    ) != "pass" or len(timed_attempts) != 2:
        fail("timed-out first audit attempt did not start and complete its reserved retry")
    try:
        module.bounded_timeout(module.time.monotonic() - 1, 3, module.AuditError)
    except module.AuditError:
        pass
    else:
        fail("audit accepted an exhausted whole-run deadline")
    intent = related_context_owner.current_plan_intent(
        "## State\n- transient\n## UX\n- accepted UX\n## Technical\n- accepted owner\n"
        "## Build Progress\n- transient progress\n## Testing\n- accepted proof\n"
    )
    if "accepted UX" not in intent or "accepted owner" not in intent or "accepted proof" not in intent:
        fail("accepted UX/Technical intent omitted from audit")
    if "transient" in intent:
        fail("transient PLAN state leaked into audit intent")
    with tempfile.TemporaryDirectory(prefix="he-final-diff-") as tmp:
        root = Path(tmp); fixture(root); base = run(root, "rev-parse", "HEAD")
        transient = root / "transient.py"
        transient.write_text("TRANSIENT = True\n", encoding="utf-8")
        historical_plan = root / "features/old/PLAN.md"; historical_plan.parent.mkdir(parents=True)
        historical_plan.write_text("HISTORICAL_PLAN_MARKER\n", encoding="utf-8")
        run(root, "add", transient.name, "features/old/PLAN.md"); run(root, "commit", "-q", "-m", "transient")
        transient.unlink(); historical_plan.unlink()
        if transient.name in module.changed_paths(root, base):
            fail("final path set retained a historically added then removed file")
        packet = module.review_packet(root, root / "features/fixture/PLAN.md")
        if (transient.name in packet or "TRANSIENT = True" in packet
                or "features/old/PLAN.md" in packet or "HISTORICAL_PLAN_MARKER" in packet):
            fail("final artifact packet exposed intermediate-only code or PLAN state")
    with tempfile.TemporaryDirectory(prefix="he-review-shards-") as tmp:
        root = Path(tmp); plan = fixture(root)
        paths = ("alpha.py", "beta.py")
        for path, marker in zip(paths, ("A", "B")):
            (root / path).write_text(f"VALUE = '{marker * 32000}'\n", encoding="utf-8")
        index = audit_packet.repository_source_index(root)
        singles = tuple(audit_packet._measure_review_scope(
            root, plan, (path,), full_files=False, planned_unit_id=None,
            repository_index=index,
        ) for path in paths)
        together = audit_packet._measure_review_scope(
            root, plan, paths, full_files=False, planned_unit_id=None,
            repository_index=index,
        )
        packet_limit = max(scope.packet_bytes for scope in singles) + 64
        if together.packet_bytes <= packet_limit:
            fail("review-shard regression fixture does not cross its packet boundary")
        scopes = audit_packet.partition_review_scopes(
            root, plan, paths, max_related_sections=4096,
            max_related_bytes=8 * 1024 * 1024, max_packet_bytes=packet_limit,
            repository_index=index,
        )
        covered = tuple(path for scope in scopes for path in scope.primary_paths)
        if (len(scopes) != 2 or covered != paths or len(set(covered)) != len(paths)
                or any(scope.packet_bytes > packet_limit for scope in scopes)):
            fail("bounded review shards omitted, duplicated, reordered, or overflowed primary coverage")
    with tempfile.TemporaryDirectory(prefix="he-deleted-secret-diff-") as tmp:
        root = Path(tmp); fixture(root)
        secret = root / "deleted.py"; secret.write_text("SERVICE_DEPLOY_TOKEN=" + "Ab12Cd34" * 4 + "\n")
        run(root, "add", secret.name); run(root, "commit", "-q", "-m", "secret base")
        parent = run(root, "rev-parse", "HEAD"); secret.unlink()
        try:
            audit_packet.scoped_diff(root, (parent,), (secret.name,))
        except module.AuditError:
            pass
        else:
            fail("historical deletion patch bypassed direct credential scan")
    with tempfile.TemporaryDirectory(prefix="he-final-artifact-") as tmp:
        root = Path(tmp); plan = fixture(root); source = root / "source.txt"
        source.write_text("staged-defect\n", encoding="utf-8"); run(root, "add", source.name)
        source.write_text("final-fixed\n", encoding="utf-8"); packet = module.review_packet(root, plan)
        if ("## Authoritative final base-to-worktree diff" not in packet or
                "+final-fixed" not in packet or "staged-defect" in packet or
                "## Staged divergence" in packet):
            fail("audit packet exposed a staged defect reversed by the final worktree")
        run(root, "add", source.name); staged_packet = module.review_packet(root, plan)
        if "+final-fixed" not in staged_packet: fail("authoritative final artifact omitted a current staged change")
    with tempfile.TemporaryDirectory(prefix="he-same-file-helper-") as tmp:
        root = Path(tmp); fixture(root); source = root / "feature.py"
        source.write_text("def helper(value):\n    return value.strip()\n\ndef run(value):\n    return value\n")
        run(root, "add", source.name); run(root, "commit", "-q", "-m", "helper base")
        source.write_text("def helper(value):\n    return value.strip()\n\ndef run(value):\n    return helper(value)\n")
        context = module.related_context(root, (source.name,))
        if not any("helper@1" in label and "return value.strip()" in body
                   for _, label, body in context):
            fail("changed Python call omitted unchanged same-file helper owner")
    with tempfile.TemporaryDirectory(prefix="he-merge-final-") as tmp:
        root = Path(tmp); plan = fixture(root)
        run(root, "switch", "-q", "-c", "side")
        (root / "side.py").write_text("SIDE = True\n", encoding="utf-8")
        merge_plan = root / "features/side/PLAN.md"; merge_plan.parent.mkdir(parents=True)
        merge_plan.write_text("MERGE_PLAN_MARKER\n", encoding="utf-8")
        run(root, "add", "side.py", "features/side/PLAN.md"); run(root, "commit", "-q", "-m", "side")
        run(root, "switch", "-q", "main")
        (root / "main.py").write_text("MAIN = True\n", encoding="utf-8")
        run(root, "add", "main.py"); run(root, "commit", "-q", "-m", "main")
        run(root, "merge", "-q", "--no-ff", "side", "-m", "merge")
        packet = module.review_packet(root, plan)
        for expected in ("main.py", "side.py", "MAIN = True", "SIDE = True"):
            if expected not in packet: fail(f"final merge artifact omitted: {expected}")
        if ("parent = " in packet or "Parent-to-commit patch" in packet
                or "features/side/PLAN.md" in packet or "MERGE_PLAN_MARKER" in packet):
            fail("final merge artifact exposed parent patches or historical PLAN state")
    opaque = "Ab12Cd34" * 4
    with tempfile.TemporaryDirectory(prefix="he-historical-secret-") as tmp:
        root = Path(tmp); plan = fixture(root); historical = root / "historical_secret.py"
        historical.write_text(f"SERVICE_DEPLOY_TOKEN={opaque}\n", encoding="utf-8")
        run(root, "add", historical.name); run(root, "commit", "-q", "-m", "historical secret")
        historical.unlink()
        rejects(module, root, plan, fail, "credential in intermediate-only commit")
    with tempfile.TemporaryDirectory(prefix="he-historical-json-secret-") as tmp:
        root = Path(tmp); plan = fixture(root); historical = root / "settings.json"
        historical.write_text('{"client_secret":"' + opaque + '"}\n', encoding="utf-8")
        run(root, "add", historical.name); run(root, "commit", "-q", "-m", "historical JSON secret")
        historical.unlink()
        rejects(module, root, plan, fail, "quoted JSON credential in intermediate-only commit")
    check_assignment_matrix(module, fail)
    for layer in ("committed", "cached", "unstaged", "untracked"):
        with tempfile.TemporaryDirectory(prefix="he-secret-") as tmp:
            root, plan = Path(tmp), None
            plan = fixture(root)
            target = root / ("tracked.env" if layer == "unstaged" else f"{layer}.txt")
            target.write_text(f"SERVICE_DEPLOY_TOKEN={opaque}\n", encoding="utf-8")
            if layer in {"committed", "cached"}: run(root, "add", target.name)
            if layer == "committed": run(root, "commit", "-q", "-m", "secret")
            rejects(module, root, plan, fail, f"prefixed secret in {layer} evidence")
        with tempfile.TemporaryDirectory(prefix="he-json-secret-") as tmp:
            root = Path(tmp); plan = fixture(root); target = root / "settings.json"
            if layer == "unstaged":
                target.write_text('{"safe":"fixture"}\n', encoding="utf-8")
                run(root, "add", target.name); run(root, "commit", "-q", "-m", "JSON baseline")
            target.write_text('{"client_secret":"' + opaque + '"}\n', encoding="utf-8")
            if layer in {"committed", "cached"}: run(root, "add", target.name)
            if layer == "committed": run(root, "commit", "-q", "-m", "JSON secret")
            rejects(module, root, plan, fail, f"quoted JSON credential in {layer} evidence")
    encoded_secret = f"SERVICE_DEPLOY_TOKEN={opaque}\n"
    for encoding in ("utf-16", "utf-32"):
        for layer in ("committed", "cached", "unstaged", "untracked"):
            with tempfile.TemporaryDirectory(prefix="he-encoded-secret-") as tmp:
                root = Path(tmp); plan = fixture(root); target = root / "encoded.txt"
                if layer == "unstaged":
                    target.write_text("SAFE=fixture\n", encoding="utf-8")
                    run(root, "add", target.name); run(root, "commit", "-q", "-m", "encoded baseline")
                target.write_bytes(encoded_secret.encode(encoding))
                if layer in {"committed", "cached"}: run(root, "add", target.name)
                if layer == "committed": run(root, "commit", "-q", "-m", "encoded secret")
                rejects(module, root, plan, fail, f"{encoding} secret in {layer} evidence")
    for encoding in ("utf-16-le", "utf-32-be"):
        try:
            audit_packet.require_safe_bytes(encoded_secret.encode(encoding), encoding)
        except module.AuditError:
            pass
        else:
            fail(f"BOM-less {encoding} credential bypassed raw-byte scan")
    text, is_text = audit_packet.safe_payload("SAFE=fixture\n".encode("utf-16"))
    if not is_text or "SAFE=fixture" not in text:
        fail("safe encoded text was reduced to opaque binary evidence")
    try:
        audit_packet.require_safe_bytes(b"\xff\xfe\x00", "malformed-utf16")
    except module.AuditError:
        pass
    else:
        fail("malformed encoded text bypassed fail-closed scan")
    for name in ("AGENTS.md", "PRODUCT.md", "DESIGN.md"):
        with tempfile.TemporaryDirectory(prefix="he-link-") as tmp:
            root = Path(tmp); plan = fixture(root); target = root / f"{name}.target"
            target.write_text("# Replacement\n", encoding="utf-8"); (root / name).unlink(); os.symlink(target.name, root / name)
            run(root, "add", name, target.name)
            rejects(module, root, plan, fail, f"symlinked {name}")
    with tempfile.TemporaryDirectory(prefix="he-link-") as tmp:
        root = Path(tmp); plan = fixture(root); os.symlink("/Users/example/.env", root / "ordinary.txt")
        rejects(module, root, plan, fail, "changed symlink target")
    with tempfile.TemporaryDirectory(prefix="he-related-link-") as tmp:
        parent = Path(tmp); root = parent / "repo"; root.mkdir(); plan = fixture(root)
        source = root / "source.py"; source.write_text("def transform(value):\n    return value\n", encoding="utf-8")
        external = parent / "transform-private"; external.write_text("private-content\n", encoding="utf-8")
        os.symlink("../transform-private", root / "caller.py")
        run(root, "add", "source.py", "caller.py"); run(root, "commit", "-q", "-m", "related link")
        plan.write_text(f"# Fixture\n- base_sha = {run(root, 'rev-parse', 'HEAD')}\n", encoding="utf-8")
        source.write_text("def transform(value):\n    return value.strip()\n", encoding="utf-8")
        from related_context import RelatedContextError, context_slice
        try:
            context_slice(root, "caller.py", 1)
        except RelatedContextError:
            pass
        else:
            fail("related context followed an unchanged escaping symlink")
    with tempfile.TemporaryDirectory(prefix="he-call-context-") as tmp:
        root = Path(tmp); plan = fixture(root)
        files = {
            "validator.py": "def validate(value):\n    return value.strip()\n",
            "consumer.py": "from validator import (\n    validate,\n)\n\ndef consume(value):\n    return value\n",
            "other_caller.py": "from validator import validate\n\nresult = validate('x')\n",
            "tests/test_validator.py": "from validator import validate\n\ndef test_validate():\n    assert validate(' x ') == 'x'\n",
            "flutter/lib/validator.dart": "String validate(String value) => value.trim();\n",
        }
        for relative, content in files.items():
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "call context")
        plan.write_text(f"# Fixture\n- base_sha = {run(root, 'rev-parse', 'HEAD')}\n", encoding="utf-8")
        (root / "consumer.py").write_text(files["consumer.py"].replace("return value", "return validate(value)"), encoding="utf-8")
        labels = tuple(label for _, label, _ in module.related_context(root, ("consumer.py",)))
        for expected in ("Related owner: validator.py", "Related caller: other_caller.py", "Related test: tests/test_validator.py"):
            if not any(expected in label for label in labels):
                fail(f"call-site change omitted {expected}")
        if any("flutter/" in label for label in labels):
            fail("generic symbol crossed the changed source language family")
    with tempfile.TemporaryDirectory(prefix="he-qualified-python-") as tmp:
        root = Path(tmp); fixture(root)
        files = {
            "owner.py": "def public_api(value):\n    return value.strip()\n",
            "consumer.py": "import owner\nfrom owner import public_api as check\n\ndef consume(value):\n    return value\n",
            "tests/test_owner.py": "from owner import public_api\n\ndef test_public_api():\n    assert public_api(' x ') == 'x'\n",
        }
        for relative, content in files.items():
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "qualified Python")
        (root / "consumer.py").write_text(
            files["consumer.py"].replace("return value", "return check(owner.public_api(value))"),
            encoding="utf-8",
        )
        labels = tuple(label for _, label, _ in module.related_context(root, ("consumer.py",)))
        for expected in ("Related owner: owner.py", "Related test: tests/test_owner.py"):
            if not any(expected in label for label in labels):
                fail(f"qualified Python call omitted {expected}")
    with tempfile.TemporaryDirectory(prefix="he-aliased-ts-") as tmp:
        root = Path(tmp); fixture(root)
        files = {
            "owner.ts": "export function publicApi(value: string) { return value.trim(); }\n",
            "consumer.ts": "import { publicApi as check } from './owner';\nexport const consume = (value: string) => value;\n",
            "owner.test.ts": "import { publicApi } from './owner';\ntest('api', () => expect(publicApi(' x ')).toBe('x'));\n",
        }
        for relative, content in files.items(): (root / relative).write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "aliased TypeScript")
        (root / "consumer.ts").write_text(files["consumer.ts"].replace("=> value", "=> check(value)"), encoding="utf-8")
        labels = tuple(label for _, label, _ in module.related_context(root, ("consumer.ts",)))
        for expected in ("Related owner: owner.ts", "Related test: owner.test.ts"):
            if not any(expected in label for label in labels): fail(f"aliased TypeScript call omitted {expected}")
    for unsafe in ("symlink", "invalid-utf8"):
        with tempfile.TemporaryDirectory(prefix=f"he-related-{unsafe}-") as tmp:
            root = Path(tmp); fixture(root)
            (root / "consumer.py").write_text("def consume(value):\n    return value\n", encoding="utf-8")
            if unsafe == "symlink":
                os.symlink("AGENTS.md", root / "unsafe.py")
            else:
                (root / "unsafe.py").write_bytes(
                    b"def public_api():\n    return " + bytes((255,)) + b"\n"
                )
            run(root, "add", "consumer.py", "unsafe.py"); run(root, "commit", "-q", "-m", unsafe)
            (root / "consumer.py").write_text(
                "def consume(value):\n    return public_api(value)\n", encoding="utf-8"
            )
            try:
                module.related_context(root, ("consumer.py",))
            except related_context_owner.RelatedContextError:
                pass
            else:
                fail(f"related context accepted tracked {unsafe} source")
    with tempfile.TemporaryDirectory(prefix="he-signature-owner-") as tmp:
        root = Path(tmp); fixture(root)
        files = {
            "owner.py": "def public_owner(value: str):\n    marker = 'owner-body'\n    return marker + value\n",
            "caller.py": "from owner import public_owner\n\nvalue = public_owner('x')\n",
            "tests/test_owner.py": "from owner import public_owner\n\ndef test_owner():\n    assert public_owner('x')\n",
        }
        for relative, content in files.items():
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "signature owner")
        (root / "owner.py").write_text(files["owner.py"].replace("value: str", "value: object"), encoding="utf-8")
        context = module.related_context(root, ("owner.py",))
        labels = tuple(label for _, label, _ in context)
        nearby = next((content for _, label, content in context if label.startswith("## Nearby owner:")), "")
        for expected in ("Related caller: caller.py", "Related test: tests/test_owner.py"):
            if not any(expected in label for label in labels):
                fail(f"signature-only change omitted {expected}")
        if "owner-body" not in nearby or "return marker + value" not in nearby:
            fail("signature-only change omitted unchanged owner body")
        if "value: object" in nearby:
            fail("nearby owner duplicated a changed signature already present in the diff")
    with tempfile.TemporaryDirectory(prefix="he-byte-budget-context-") as tmp:
        root = Path(tmp); fixture(root)
        owner = root / "owner.py"
        caller = root / "caller.py"
        owner.write_text("def public_api(value):\n    return value\n", encoding="utf-8")
        caller.write_text(
            "\n".join(
                line
                for index in range(40)
                for line in (
                    f"value_{index} = public_api({index})",
                    f"# padding-{index}-" + ("x" * 4096),
                )
            ) + "\n",
            encoding="utf-8",
        )
        run(root, "add", "."); run(root, "commit", "-q", "-m", "byte budget context")
        owner.write_text("def public_api(value):\n    return value + 1\n", encoding="utf-8")
        context = module.related_context(root, ("owner.py",))
        labels = tuple(label for _, label, _ in context)
        rendered_bytes = sum(
            len(value.encode("utf-8")) for entry in context for value in entry
        )
        if not any(label == "## Related caller exact-line index" for label in labels):
            fail("byte-heavy related context did not collapse below the section-count limit")
        if rendered_bytes > 128 * 1024:
            fail("byte-heavy related context exceeded its deterministic packet budget")
    with tempfile.TemporaryDirectory(prefix="he-package-context-") as tmp:
        root = Path(tmp); plan = fixture(root)
        files = {
            "backend/pubspec.yaml": "name: backend\n",
            "backend/lib/settings.dart": "const APPWRITE_ENDPOINT = 'backend';\n",
            "backend/lib/consumer.dart": "String consume() => 'safe';\n",
            "flutter/pubspec.yaml": "name: flutter_app\n",
            "flutter/lib/settings.dart": "const APPWRITE_ENDPOINT = 'flutter';\n",
        }
        for relative, content in files.items():
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "package context")
        (root / "backend/lib/consumer.dart").write_text(
            "String consume() => APPWRITE_ENDPOINT;\n", encoding="utf-8"
        )
        labels = tuple(label for _, label, _ in module.related_context(root, ("backend/lib/consumer.dart",)))
        if not any("backend/lib/settings.dart" in label for label in labels):
            fail("same-package dependency owner omitted")
        if any("flutter/lib/settings.dart" in label for label in labels):
            fail("generic symbol crossed package-manifest boundary")
    language_owners = {
        ".c": "const char *transform_c(const char *value) {\n    return value;\n}\n",
        ".cc": "const char *transform_cc(const char *value) {\n    return value;\n}\n",
        ".cpp": "const char *transform_cpp(const char *value) {\n    return value;\n}\n",
        ".dart": "String transform_dart(String value) {\n  return value;\n}\n",
        ".go": "func transform_go(value string) string {\n    return value\n}\n",
        ".java": "public static String transform_java(String value) {\n    return value;\n}\n",
        ".kt": "fun transform_kt(value: String): String {\n    return value\n}\n",
        ".swift": "func transform_swift(_ value: String) -> String {\n    return value\n}\n",
    }
    for suffix, owner_text in language_owners.items():
        with tempfile.TemporaryDirectory(prefix="he-language-owner-") as tmp:
            root = Path(tmp); fixture(root); name = f"transform_{suffix.lstrip('.')}"
            package = root / "package"; tests = package / "tests"; tests.mkdir(parents=True)
            if suffix == ".dart": (package / "pubspec.yaml").write_text("name: fixture\n", encoding="utf-8")
            owner = package / f"owner{suffix}"; caller = package / f"caller{suffix}"
            test = tests / f"test_owner{suffix}"
            owner.write_text(owner_text, encoding="utf-8")
            caller.write_text(f"value = {name}(value)\n", encoding="utf-8")
            test.write_text(f"value = {name}(value)\n", encoding="utf-8")
            run(root, "add", "."); run(root, "commit", "-q", "-m", f"{suffix} owner")
            owner.write_text(owner_text.replace("return value", "return value + value"), encoding="utf-8")
            labels = tuple(label for _, label, _ in module.related_context(root, (owner.relative_to(root).as_posix(),)))
            for expected in ("Nearby owner:", f"Related caller: {caller.relative_to(root).as_posix()}",
                             f"Related test: {test.relative_to(root).as_posix()}"):
                if not any(expected in label for label in labels):
                    fail(f"{suffix} body-only change omitted {expected}")
    with tempfile.TemporaryDirectory(prefix="he-symbol-context-") as tmp:
        root = Path(tmp); plan = fixture(root)
        files = {
            "settings.py": "MAX_RETRIES = 3\nCONFIG = {'timeout': 5}\nROUTE = '/users'\n",
            "consumer.py": "from settings import MAX_RETRIES, CONFIG, ROUTE\n\ndef consume():\n    return None\n",
            "other_consumer.py": "from settings import MAX_RETRIES, CONFIG, ROUTE\n\nvalue = (MAX_RETRIES, CONFIG['timeout'], ROUTE)\n",
            "tests/test_settings.py": "from settings import MAX_RETRIES, CONFIG, ROUTE\n\ndef test_settings():\n    assert (MAX_RETRIES, CONFIG['timeout'], ROUTE) == (3, 5, '/users')\n",
        }
        for relative, content in files.items():
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "symbol context")
        plan.write_text(f"# Fixture\n- base_sha = {run(root, 'rev-parse', 'HEAD')}\n", encoding="utf-8")
        replacement = "return (MAX_RETRIES, CONFIG['timeout'], '/users')"
        (root / "consumer.py").write_text(files["consumer.py"].replace("return None", replacement), encoding="utf-8")
        context = module.related_context(root, ("consumer.py",))
        labels = tuple(label for _, label, _ in context)
        for expected in ("Related owner: settings.py", "Related caller: other_consumer.py", "Related test: tests/test_settings.py"):
            if not any(expected in label for label in labels):
                fail(f"non-callable change omitted {expected}")
        coverage = next((content for _, label, content in context if label == "## Related coverage"), "")
        if not all(token in coverage for token in ("MAX_RETRIES", "timeout", "/users")):
            fail("non-callable coverage manifest incomplete")
    with tempfile.TemporaryDirectory(prefix="he-unresolved-local-import-") as tmp:
        root = Path(tmp); plan = fixture(root)
        (root / "owner.py").write_text("def different_owner():\n    return True\n", encoding="utf-8")
        consumer = root / "consumer.py"
        consumer.write_text("from owner import required_owner\n\ndef use():\n    return None\n", encoding="utf-8")
        run(root, "add", "owner.py", "consumer.py"); run(root, "commit", "-q", "-m", "local import")
        plan.write_text(f"# Fixture\n- base_sha = {run(root, 'rev-parse', 'HEAD')}\n", encoding="utf-8")
        consumer.write_text(
            "from owner import required_owner\n\ndef use():\n    return required_owner()\n", encoding="utf-8"
        )
        rejects(module, root, plan, fail, "unresolved required local import")
    with tempfile.TemporaryDirectory(prefix="he-js-default-import-") as tmp:
        root = Path(tmp); plan = fixture(root)
        files = {
            "named.ts": "export default function publicApi(value: string) {\n  return value;\n}\n",
            "anonymous.ts": "export default function (value: string) {\n  return value;\n}\n",
            "consumer.ts": "import renamed from './named';\nimport other from './anonymous';\n\nexport function use() {\n  return '';\n}\n",
        }
        for relative, content in files.items():
            (root / relative).write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "default imports")
        plan.write_text(f"# Fixture\n- base_sha = {run(root, 'rev-parse', 'HEAD')}\n", encoding="utf-8")
        (root / "consumer.ts").write_text(
            files["consumer.ts"].replace("return '';", "return renamed(other('x'));"), encoding="utf-8"
        )
        context = module.related_context(root, ("consumer.ts",))
        labels = tuple(label for _, label, _ in context)
        if not any("Nearby owner: named.ts" in label and "publicApi" in label for label in labels):
            fail("renamed named-default import omitted its exported owner")
        if not any("Nearby owner: anonymous.ts" in label and "default@anonymous.ts" in label for label in labels):
            fail("anonymous default import omitted its module owner")
    with tempfile.TemporaryDirectory(prefix="he-relative-import-") as tmp:
        from related_context import local_imported_symbols
        root = Path(tmp); plan = fixture(root)
        files = {
            "pkg/owner.py": "def api():\n    return True\n",
            "pkg/sub/consumer.py": "from ..owner import api\n\ndef consume():\n    return None\n",
            "pkg/deep/leaf/consumer.py": "from ...owner import api\n\ndef consume_deep():\n    return None\n",
            "pkg/other.py": "from .owner import api\n\nvalue = api()\n",
            "tests/test_owner.py": "from pkg.owner import api\n\ndef test_api():\n    assert api()\n",
        }
        for relative, content in files.items():
            path = root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        run(root, "add", "."); run(root, "commit", "-q", "-m", "relative imports")
        plan.write_text(f"# Fixture\n- base_sha = {run(root, 'rev-parse', 'HEAD')}\n", encoding="utf-8")
        for relative, level in (("pkg/sub/consumer.py", 2), ("pkg/deep/leaf/consumer.py", 3)):
            path = root / relative; lines = path.read_text(encoding="utf-8").splitlines()
            if local_imported_symbols(root, relative, lines, ".py") != {"api"}:
                fail(f"level-{level} Python relative import resolved from wrong directory")
            path.write_text(path.read_text(encoding="utf-8").replace("return None", "return api()"), encoding="utf-8")
        labels = tuple(label for _, label, _ in module.related_context(
            root, ("pkg/sub/consumer.py", "pkg/deep/leaf/consumer.py"), run(root, "rev-parse", "HEAD")
        ))
        for expected in ("Related owner: pkg/owner.py", "Related caller: pkg/other.py", "Related test: tests/test_owner.py"):
            if not any(expected in label for label in labels):
                fail(f"relative import graph omitted {expected}")
    child = "import os,time; os.close(0); time.sleep(.05)"
    try:
        module.run_codex_stream([sys.executable, "-c", child], "x" * 2097152, 5)
    except module.AuditError as exc:
        if "input pipe closed" not in str(exc): fail("broken pipe returned wrong failure")
    else: fail("broken pipe escaped fail-closed handling")
    events = [error_event, '{"type":"item.completed","item":{"type":"agent_message"}}',
              '{"type":"turn.completed","usage":{"input_tokens":1,"cached_input_tokens":0,"output_tokens":1}}']
    child = "import sys; sys.stdin.read(); print(" + repr("\n".join(events)) + ")"
    if module.run_codex_stream([sys.executable, "-c", child], "packet", 5) != ({"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}, 1):
        fail("successful transport recovery did not preserve the final usage boundary")
    with tempfile.TemporaryDirectory(prefix="he-invalid-result-") as temporary:
        result_path = Path(temporary) / "result.json"
        uncited = {
            "snapshot_id": snapshot, "verdict": "fail", "unknowns": [],
            "summary": "one finding",
            "findings": [{
                "id": "A-1", "axis": "spec", "severity": "critical",
                "evidence": "skills/he-build/scripts/audit_result.py drops the completed review",
                "risk": "review deadlocks", "fix": "normalize citation only", "required": True,
            }],
        }
        result_path.write_text(json.dumps(uncited), encoding="utf-8")
        repaired = module.load_audit_result(
            result_path, snapshot, 1, ("skills/he-build/scripts/audit_result.py",)
        )
        if not repaired["findings"][0]["evidence"].endswith(
            "skills/he-build/scripts/audit_result.py changed hunk"
        ):
            fail("unique packet-proven changed path did not receive citation-only normalization")
        ambiguous = {**uncited, "findings": [{
            **uncited["findings"][0],
            "evidence": "a.py and b.py both participate in the defect",
        }]}
        result_path.write_text(json.dumps(ambiguous), encoding="utf-8")
        preserved = module.load_audit_result(result_path, snapshot, 1, ("a.py", "b.py"))
        preserved_evidence = "\n".join(preserved["unknowns"])
        if (preserved["verdict"] != "concerns" or preserved["findings"]
                or "a.py and b.py both participate in the defect" not in preserved_evidence
                or "review deadlocks" not in preserved_evidence
                or "normalize citation only" not in preserved_evidence
                or audit_result.EVIDENCE_CITATION.search(preserved_evidence)):
            fail("ambiguous completed finding was lost, accepted, or assigned a guessed citation")
        missing_finding = {key: value for key, value in uncited["findings"][0].items() if key != "required"}
        missing_finding.update(severity="low", evidence="audit_result.py preserves evidence")
        missing_required = {**uncited, "findings": [missing_finding]}
        result_path.write_text(json.dumps(missing_required), encoding="utf-8")
        preserved = module.load_audit_result(result_path, snapshot, 1, ("audit_result.py",))
        preserved_evidence = "\n".join(preserved["unknowns"])
        if (preserved["verdict"] != "concerns" or preserved["findings"]
                or "preserves evidence" not in preserved_evidence
                or "review deadlocks" not in preserved_evidence
                or "normalize citation only" not in preserved_evidence
                or '"required"' in preserved_evidence
                or "changed hunk" in preserved_evidence):
            fail("completed finding missing required was lost or assigned guessed blockingness")
        try: module.load_audit_result(result_path, snapshot, 0)
        except module.RetryableAuditError: pass
        else: fail("zero-item missing-required result skipped its bounded infrastructure retry")
        result_path.write_text(json.dumps(uncited), encoding="utf-8")
        unattributed = module.load_audit_result(result_path, snapshot, 1, ("other.py",))
        if unattributed["verdict"] != "concerns" or not unattributed["unknowns"]:
            fail("completed finding without packet-proven path was discarded")
        try: module.load_audit_result(result_path, snapshot, 0, ("other.py",))
        except module.RetryableAuditError: pass
        else: fail("zero-item uncited result skipped its bounded infrastructure retry")
        result_path.write_text("{}", encoding="utf-8")
        try: module.load_audit_result(result_path, snapshot, 1)
        except module.AuditError as error:
            if isinstance(error, module.RetryableAuditError): fail("completed invalid review was retried")
        else: fail("completed invalid review result was accepted")
        try: module.load_audit_result(result_path, snapshot, 0)
        except module.RetryableAuditError: pass
        else: fail("zero-evidence invalid result skipped bounded retry")
    child = "import sys; sys.stdin.read(); print(" + repr(error_event) + "); raise SystemExit(1)"
    try: module.run_codex_stream([sys.executable, "-c", child], "packet", 5)
    except module.RetryableAuditError: pass
    else: fail("error-only audit exit did not enter the bounded retry path")
    reasoning_only = '{"type":"item.completed","item":{"type":"reasoning"}}'
    child = "import sys; sys.stdin.read(); print(" + repr(reasoning_only) + "); raise SystemExit(1)"
    try: module.run_codex_stream([sys.executable, "-c", child], "packet", 5)
    except module.RetryableAuditError: pass
    else: fail("reasoning-only audit exit consumed the zero-review retry path")
    original_argv, original_run = sys.argv, module.run_audit
    module.run_audit = lambda *a, **k: (_ for _ in ()).throw(module.AuditError("input pipe closed"))
    try:
        with tempfile.TemporaryDirectory(prefix="he-blocked-") as tmp:
            root = Path(tmp); fixture(root); sys.argv = ["audit.py", "--repo", str(root), "--plan", "x"]
            stream = io.StringIO()
            with redirect_stderr(stream): result = module.main()
            if result != 1 or '"stage":"blocked"' not in stream.getvalue(): fail("pipe failure omitted blocked status")
    finally:
        sys.argv, module.run_audit = original_argv, original_run

def standalone_fail(message):
    print(f"audit-regressions: {message}", file=sys.stderr)
    raise SystemExit(1)


def main():
    import audit

    check_audit_regressions(audit, standalone_fail)
    print("audit-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
