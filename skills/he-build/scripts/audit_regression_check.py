import io
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path


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
    prompt = module.audit_prompt("sha256:" + "0" * 64, "sha256:" + "0" * 64, "packet")
    if "required only when retained in the reconstructed final artifact" not in prompt:
        fail("audit prompt lets superseded historical hunks block final state")
    units = [(f"## Unit {index}", f"PAYLOAD_{index}\n" + marker * 70000)
             for index, marker in enumerate(("A", "B", "C"), 1)]
    packets = module.partition_packets(["# Common", "rules"], units, 300000)
    if len(packets) < 2 or any(len(packet.encode()) > 192 * 1024 for packet in packets):
        fail("audit evidence was not partitioned into bounded units")
    for index in range(1, 4):
        if sum(packet.count(f"PAYLOAD_{index}\n") for packet in packets) != 1:
            fail("partitioned audit duplicated or omitted an evidence unit")
    snapshot = "sha256:" + "1" * 64
    clean = {"snapshot_id": snapshot, "verdict": "pass", "findings": [], "unknowns": [], "summary": "clean"}
    required = {"id": "A-1", "axis": "spec", "severity": "critical", "evidence": "a.py:1",
                "risk": "wrong", "fix": "repair", "required": True}
    vague = {**clean, "verdict": "fail", "findings": [{**required, "evidence": "some code is wrong"}]}
    try: module.validate_result(vague, snapshot)
    except module.AuditError: pass
    else: fail("audit accepted uncited finding evidence")
    aggregate = module.aggregate_results([clean, {**clean, "verdict": "fail", "findings": [required]}], snapshot)
    if aggregate["verdict"] != "fail" or aggregate["findings"][0]["id"] != "A-1":
        fail("partitioned audit aggregation did not fail closed")
    duplicated = {**clean, "verdict": "fail", "findings": [dict(required), dict(required)]}
    normalized = module.assign_finding_ids(duplicated)
    if [finding["id"] for finding in normalized["findings"]] != ["A-1", "A-2"]:
        fail("audit parent did not own deterministic finding IDs")
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
        fail("audit unit timeout ignored the whole-run deadline")
    try:
        module.bounded_timeout(module.time.monotonic() - 1, 3, module.AuditError)
    except module.AuditError:
        pass
    else:
        fail("audit accepted an exhausted whole-run deadline")
    intent = module.current_plan_intent(
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
        history = module.commit_history_evidence(root, base)
        if transient.name not in history or "TRANSIENT = True" not in history:
            fail("per-commit reconstruction omitted intermediate-only file")
        if "Parent-to-commit patch" not in history or "Parent-to-final" in history or "Commit-to-final" in history:
            fail("per-commit reconstruction did not use direct ordered patches")
        if "features/old/PLAN.md" in history or "HISTORICAL_PLAN_MARKER" in history:
            fail("per-commit reconstruction included historical PLAN content")
    with tempfile.TemporaryDirectory(prefix="he-deleted-secret-diff-") as tmp:
        root = Path(tmp); fixture(root)
        secret = root / "deleted.py"; secret.write_text("SERVICE_DEPLOY_TOKEN=" + "Ab12Cd34" * 4 + "\n")
        run(root, "add", secret.name); run(root, "commit", "-q", "-m", "secret base")
        parent = run(root, "rev-parse", "HEAD"); secret.unlink()
        try:
            module.scoped_diff(root, (parent,), (secret.name,))
        except module.AuditError:
            pass
        else:
            fail("historical deletion patch bypassed direct credential scan")
    with tempfile.TemporaryDirectory(prefix="he-staged-layer-") as tmp:
        root = Path(tmp); plan = fixture(root); source = root / "source.txt"
        source.write_text("staged-only\n", encoding="utf-8"); run(root, "add", source.name)
        packet = module.review_packet(root, plan)
        staged = packet.split("## Staged divergence", 1)[1].split("## Final HEAD-to-worktree diff", 1)[0]
        if "staged-only" not in staged:
            fail("audit packet omitted staged-only index evidence")
    with tempfile.TemporaryDirectory(prefix="he-same-file-helper-") as tmp:
        root = Path(tmp); fixture(root); source = root / "feature.py"
        source.write_text("def helper(value):\n    return value.strip()\n\ndef run(value):\n    return value\n")
        run(root, "add", source.name); run(root, "commit", "-q", "-m", "helper base")
        source.write_text("def helper(value):\n    return value.strip()\n\ndef run(value):\n    return helper(value)\n")
        context = module.related_context(root, (source.name,))
        if not any("helper@1" in label and "return value.strip()" in body
                   for _, label, body in context):
            fail("changed Python call omitted unchanged same-file helper owner")
    with tempfile.TemporaryDirectory(prefix="he-merge-history-") as tmp:
        root = Path(tmp); fixture(root); base = run(root, "rev-parse", "HEAD")
        run(root, "switch", "-q", "-c", "side")
        (root / "side.py").write_text("SIDE = True\n", encoding="utf-8")
        merge_plan = root / "features/side/PLAN.md"; merge_plan.parent.mkdir(parents=True)
        merge_plan.write_text("MERGE_PLAN_MARKER\n", encoding="utf-8")
        run(root, "add", "side.py", "features/side/PLAN.md"); run(root, "commit", "-q", "-m", "side")
        side = run(root, "rev-parse", "HEAD")
        run(root, "switch", "-q", "main")
        (root / "main.py").write_text("MAIN = True\n", encoding="utf-8")
        run(root, "add", "main.py"); run(root, "commit", "-q", "-m", "main")
        main = run(root, "rev-parse", "HEAD")
        run(root, "merge", "-q", "--no-ff", "side", "-m", "merge")
        history = module.commit_history_evidence(root, base)
        for expected in (f"parent = {main}", f"parent = {side}", "main.py", "side.py"):
            if expected not in history:
                fail(f"per-commit reconstruction omitted merge evidence: {expected}")
        merge = run(root, "rev-parse", "HEAD")
        if history.count(f"### {merge} ") != 2:
            fail("merge reconstruction omitted a direct parent patch")
        if "features/side/PLAN.md" in history or "MERGE_PLAN_MARKER" in history:
            fail("merge reconstruction included historical PLAN content")
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
    api_key_name = "APPWRITE_" + "API_KEY"
    oauth_secret_name = "GOOGLE_OAUTH_CLIENT_" + "SECRET"
    client_secret_name = "client_" + "secret"
    for reference in (
        f"{api_key_name}: process.env.APPWRITE_API_KEY",
        f"{api_key_name}: process.env['APPWRITE_API_KEY']",
        f"appwriteApiKey: import.meta.env.{api_key_name}",
        f"{oauth_secret_name}: Platform.environment['GOOGLE_OAUTH_CLIENT_SECRET'] ?? ''",
        f"{client_secret_name} = os.environ['CLIENT_SECRET']",
        f"{client_secret_name} = os.getenv('CLIENT_SECRET')",
        f'{client_secret_name} = os.Getenv("CLIENT_SECRET")',
        f'{client_secret_name} = System.getenv("CLIENT_SECRET")',
        f'{client_secret_name} = Deno.env.get("CLIENT_SECRET")',
        f'{client_secret_name} = ProcessInfo.processInfo.environment["CLIENT_SECRET"]',
        f"{client_secret_name} = String.fromEnvironment('CLIENT_SECRET')",
        f'{client_secret_name} = Environment.GetEnvironmentVariable("CLIENT_SECRET")',
        f'{client_secret_name} = std::env::var("CLIENT_SECRET")',
        f'{client_secret_name} = System.get_env("CLIENT_SECRET")',
        f"{client_secret_name} = ENV['CLIENT_SECRET']",
        f'{client_secret_name} = getenv("CLIENT_SECRET")',
        f"{api_key_name}: process.env.APPWRITE_API_KEY ?? null",
    ):
        if module.secret_marker(reference) is not None:
            fail("environment reference classified as literal credential")
    for mixed in (
        f'{api_key_name}: process.env.APPWRITE_API_KEY || "{opaque}"',
        f'{api_key_name}: process.env.APPWRITE_API_KEY + "{opaque}"',
        f'{api_key_name}: process.env.APPWRITE_API_KEY ?? "prefix-{opaque}"',
    ):
        if module.secret_marker(mixed) is None:
            fail("environment reference hid a literal credential expression")
    password_name = "pass" + "word"
    for literal in (
        f'{password_name}: "correct horse battery staple"',
        f'{client_secret_name} = "phrase with spaces !@#$%^&*()"',
    ):
        if module.secret_marker(literal) is None:
            fail("punctuation or whitespace credential literal bypassed scanner")
    if module.secret_marker(f'{api_key_name}: "{opaque}"') is None:
        fail("literal credential bypassed environment-reference exception")
    if module.secret_marker('{"client_secret":"' + opaque + '"}') is None:
        fail("quoted JSON credential key bypassed scanner")
    if not module.sensitive_path(".env") or module.sensitive_path(".env.example"):
        fail("environment-file path policy drift")
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
            module.require_safe_bytes(encoded_secret.encode(encoding), encoding)
        except module.AuditError:
            pass
        else:
            fail(f"BOM-less {encoding} credential bypassed raw-byte scan")
    text, is_text = module.safe_payload("SAFE=fixture\n".encode("utf-16"))
    if not is_text or "SAFE=fixture" not in text:
        fail("safe encoded text was reduced to opaque binary evidence")
    try:
        module.require_safe_bytes(b"\xff\xfe\x00", "malformed-utf16")
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
            except module.RelatedContextError:
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
