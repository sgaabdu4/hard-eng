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
    opaque = "Ab12Cd34" * 4
    for layer in ("committed", "cached", "unstaged", "untracked"):
        with tempfile.TemporaryDirectory(prefix="he-secret-") as tmp:
            root, plan = Path(tmp), None
            plan = fixture(root)
            target = root / ("tracked.env" if layer == "unstaged" else f"{layer}.txt")
            target.write_text(f"SERVICE_DEPLOY_TOKEN={opaque}\n", encoding="utf-8")
            if layer in {"committed", "cached"}: run(root, "add", target.name)
            if layer == "committed": run(root, "commit", "-q", "-m", "secret")
            rejects(module, root, plan, fail, f"prefixed secret in {layer} evidence")
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
