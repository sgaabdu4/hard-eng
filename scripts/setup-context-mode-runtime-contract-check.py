#!/usr/bin/env python3
"""Behavioural contract for the pinned Context Mode runtime overlay.

The Codex plugin manager owns the plugin cache and restores the vendor hook on
every reinstall, so apply must be idempotent and check must tell the operator
which of the two failures happened: recoverable drift, or a vendor rewrite that
invalidates the overlay itself.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / "scripts/setup/context-mode-runtime.py"
VERSION = "1.0.169"

VENDOR_HOOK = """import { createRequire } from "node:module";

const NATIVE_DEPS = ["better-sqlite3"];

function hasModernSqlite() {
  if (typeof globalThis.Bun !== "undefined") return true;
  const [major, minor] = process.versions.node.split(".").map(Number);
  return major > 22 || (major === 22 && minor >= 5);
}

export async function ensureDeps() {
  if (typeof globalThis.Bun !== "undefined") return;
  for (const pkg of NATIVE_DEPS) {
    install(pkg);
  }
}
"""


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-context-mode-runtime-contract: FAIL: {message}")


def plugin_root(directory: Path, *, hook: str, version: str = VERSION) -> Path:
    root = directory / "context-mode"
    (root / "hooks").mkdir(parents=True)
    (root / "package.json").write_text(
        json.dumps({"name": "context-mode", "version": version}), encoding="utf-8"
    )
    (root / "hooks/ensure-deps.mjs").write_text(hook, encoding="utf-8")
    return root


def run(operation: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OVERLAY), operation, str(root), VERSION],
        capture_output=True,
        text=True,
        check=False,
    )


def case(label: str, hook: str, operation: str, expect: str | None) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-ctx-overlay-") as temporary:
        root = plugin_root(Path(temporary), hook=hook)
        result = run(operation, root)
        output = (result.stdout + result.stderr).strip()
        if expect is None:
            if result.returncode:
                fail(f"{label}: expected success, got {output}")
            return
        if not result.returncode:
            fail(f"{label}: expected failure, {operation} succeeded")
        if expect not in output:
            fail(f"{label}: expected {expect!r}, got {output}")


def check_apply_is_idempotent_and_effective() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-ctx-overlay-") as temporary:
        root = plugin_root(Path(temporary), hook=VENDOR_HOOK)
        hook_file = root / "hooks/ensure-deps.mjs"
        if run("check", root).returncode == 0:
            fail("check accepted an unpatched vendor hook")
        if run("apply", root).returncode:
            fail("apply rejected the pinned vendor hook")
        once = hook_file.read_text(encoding="utf-8")
        if "hasUsableBuiltinSqlite" not in once or "fts5(body)" not in once:
            fail("apply did not install the built-in SQLite probe")
        if once.index("if (hasUsableBuiltinSqlite()) return;") < once.index(
            "export async function ensureDeps()"
        ):
            fail("bootstrap guard is not inside ensureDeps")
        if run("apply", root).returncode:
            fail("second apply rejected an already-patched hook")
        if hook_file.read_text(encoding="utf-8") != once:
            fail("apply is not idempotent")
        if run("check", root).returncode:
            fail("check rejected the hook it just patched")


def check_reports_recoverable_drift() -> None:
    # The exact state a Codex plugin reinstall leaves behind.
    case(
        "plugin manager restored the vendor hook",
        VENDOR_HOOK,
        "check",
        "re-run ./setup.sh install",
    )


def check_reports_vendor_rewrite() -> None:
    rewritten = VENDOR_HOOK.replace(
        "export async function ensureDeps() {", "export async function ensureDeps(options) {"
    )
    case("vendor renamed the bootstrap anchor", rewritten, "check", "needs updating")
    case("vendor renamed the bootstrap anchor", rewritten, "apply", "bootstrap anchor")
    dropped = VENDOR_HOOK.replace("function hasModernSqlite() {", "function hasSqlite() {")
    case("vendor renamed the capability anchor", dropped, "check", "needs updating")
    case("vendor renamed the capability anchor", dropped, "apply", "SQLite capability anchor")


def check_rejects_a_tampered_overlay() -> None:
    patched = VENDOR_HOOK.replace(
        "function hasModernSqlite() {\n"
        '  if (typeof globalThis.Bun !== "undefined") return true;\n'
        "  const [major, minor] = process.versions.node.split(\".\").map(Number);\n"
        "  return major > 22 || (major === 22 && minor >= 5);\n"
        "}\n\n",
        "function hasModernSqlite() {\n"
        '  if (typeof globalThis.Bun !== "undefined") return true;\n'
        "  const [major, minor] = process.versions.node.split(\".\").map(Number);\n"
        "  return major > 22 || (major === 22 && minor >= 5);\n"
        "}\n\n"
        "// hard-eng managed runtime: use built-in SQLite when it provides FTS5\n",
    )
    case("marker without the probe body", patched, "check", "overlay is incomplete")
    disarmed = patched.replace(
        "// hard-eng managed runtime: use built-in SQLite when it provides FTS5\n",
        "// hard-eng managed runtime: use built-in SQLite when it provides FTS5\n"
        "function hasUsableBuiltinSqlite() { return true; }\n",
    )
    case("probe replaced with a stub", disarmed, "check", "overlay is incomplete")


def check_rejects_a_foreign_package() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-ctx-overlay-") as temporary:
        root = plugin_root(Path(temporary), hook=VENDOR_HOOK, version="9.9.9")
        result = run("apply", root)
        if not result.returncode or "unexpected Context Mode package identity" not in (
            result.stdout + result.stderr
        ):
            fail("apply patched a package whose version is not the pinned one")
    with tempfile.TemporaryDirectory(prefix="hard-eng-ctx-overlay-") as temporary:
        # A readable hook with no manifest beside it: only the identity guard can reject this.
        root = plugin_root(Path(temporary), hook=VENDOR_HOOK)
        (root / "package.json").unlink()
        result = run("apply", root)
        if not result.returncode or "could not read Context Mode package metadata" not in (
            result.stdout + result.stderr
        ):
            fail("apply accepted a package root with no metadata")
    with tempfile.TemporaryDirectory(prefix="hard-eng-ctx-overlay-") as temporary:
        root = plugin_root(Path(temporary), hook=VENDOR_HOOK)
        (root / "hooks/ensure-deps.mjs").unlink()
        (root / "hooks/ensure-deps.mjs").symlink_to("/etc/hosts")
        result = run("apply", root)
        if not result.returncode or "is not a regular file" not in (
            result.stdout + result.stderr
        ):
            fail("apply followed a symlinked dependency hook")


def main() -> int:
    check_apply_is_idempotent_and_effective()
    check_reports_recoverable_drift()
    check_reports_vendor_rewrite()
    check_rejects_a_tampered_overlay()
    check_rejects_a_foreign_package()
    print("setup-context-mode-runtime-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
