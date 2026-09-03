#!/usr/bin/env python3
"""Static coverage for repository-owned process and network operations."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
MANAGED = {"skills/building-flutter-apps", "skills/vercel-react-best-practices"}
HARNESS_MARKERS = ("contract", "regression", "test", "fixture")
PYTHON_PROCESS_CALLS = {
    "run",
    "Popen",
    "call",
    "check_call",
    "check_output",
    "create_subprocess_exec",
    "create_subprocess_shell",
}
RUNTIME_ALLOWLIST = {
    "skills/adversarial-review/scripts/run_review.py",
    "skills/deterministic-checks/scripts/bounded_run.py",
    "skills/deterministic-checks/scripts/script_runner.py",
    "skills/he-plan/scripts/check.py",
    "scripts/rollout-shared.py",
}
NETWORK_ALLOWLIST = {
    "scripts/setup/update.py",
    "skills/he/scripts/tracker_probe.py",
    "skills/he/scripts/tracker_http.py",
}
JS_ALLOWLIST = {
    "skills/appwrite-backend/scripts/appwrite-schema-guard.mjs",
    "skills/deterministic-checks/scripts/check-design-md.js",
    "skills/product-walkthrough-video/scripts/convert-mp4.mjs",
    "skills/product-walkthrough-video/scripts/review-frames.mjs",
    "skills/product-walkthrough-video/tests/gesture-smoke.mjs",
}
SHELL_ALLOWLIST = {"scripts/setup/common.sh"}


def fail(message: str) -> NoReturn:
    raise SystemExit(f"bounded-operations-contract: FAIL: {message}")


def python_operations(source: str) -> set[str]:
    tree = ast.parse(source)
    module_aliases: dict[str, str] = {}
    direct_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name in {"subprocess", "asyncio", "urllib.request"}:
                    bound = name.asname or name.name.split(".", 1)[0]
                    module_aliases[bound] = name.name if name.asname else bound
        elif isinstance(node, ast.ImportFrom) and node.module in {"subprocess", "asyncio", "urllib.request"}:
            for name in node.names:
                direct_aliases[name.asname or name.name] = f"{node.module}.{name.name}"
    operations: set[str] = set()

    def qualified_name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return module_aliases.get(node.id, direct_aliases.get(node.id, node.id))
        if isinstance(node, ast.Attribute):
            parent = qualified_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = qualified_name(node.func)
        if name.rsplit(".", 1)[-1] in PYTHON_PROCESS_CALLS and name.startswith(("subprocess.", "asyncio.")):
            operations.add(name)
        if name == "urllib.request.urlopen":
            operations.add(name)
    return operations


def is_harness(relative: str) -> bool:
    name = Path(relative).name.lower()
    return any(marker in name for marker in HARNESS_MARKERS)


def under_managed(relative: str) -> bool:
    return any(relative == root or relative.startswith(f"{root}/") for root in MANAGED)


def required_anchors(relative: str, source: str) -> None:
    if relative == "skills/deterministic-checks/scripts/script_runner.py":
        for anchor in ("CHILD_TIMEOUT", "run_captured(", "def spawn_script", "PROCESS_STATE"):
            if anchor not in source:
                fail(f"script runner seam lost {anchor}")
    if relative == "skills/deterministic-checks/scripts/bounded_run.py":
        for anchor in ("start_new_session", "stop_group", "timeout"):
            if anchor not in source:
                fail(f"canonical bounded runner lost {anchor}")
    elif relative == "skills/adversarial-review/scripts/run_review.py":
        for anchor in ("start_new_session", "stop_process_group", "os.killpg", "timeout_seconds"):
            if anchor not in source:
                fail(f"adversarial reviewer lost {anchor}")
    elif relative == "scripts/rollout-shared.py":
        for anchor in ("start_new_session", "os.killpg", "TIMEOUT_SECONDS"):
            if anchor not in source:
                fail(f"shared rollout lost {anchor}")
    elif relative == "skills/he/scripts/tracker_probe.py":
        for anchor in ("PROBE_TIMEOUT", "timeout=timeout", "read(4096)"):
            if anchor not in source:
                fail(f"tracker probe lost {anchor}")
    elif relative == "skills/he/scripts/tracker_http.py":
        for anchor in ("REQUEST_TIMEOUT", "timeout=REQUEST_TIMEOUT", "read(MAX_BODY)", "redact("):
            if anchor not in source:
                fail(f"tracker HTTP client lost {anchor}")
    elif relative == "skills/appwrite-backend/scripts/appwrite-schema-guard.mjs":
        for anchor in ("function spawnBounded", "timeout:", "detached:", "stopProcessGroup"):
            if anchor not in source:
                fail(f"Appwrite bounded CLI owner lost {anchor}")
    elif relative == "skills/deterministic-checks/scripts/check-design-md.js":
        for anchor in ("bounded_run.py", '"--timeout"', "timeout:"):
            if anchor not in source:
                fail(f"design linter owner lost {anchor}")
    elif relative == "scripts/setup/update.py":
        for anchor in ("timeout=5", "deadline =", "MAX_ASSET_BYTES"):
            if anchor not in source:
                fail(f"setup update network owner lost {anchor}")
    elif relative == "scripts/setup/common.sh":
        for anchor in ("bounded_setup_run 120 curl", "--connect-timeout", "--max-time"):
            if anchor not in source:
                fail(f"setup download owner lost {anchor}")


def check_python(path: Path, relative: str, source: str) -> None:
    operations = python_operations(source)
    if not operations:
        return
    if is_harness(relative):
        return
    allowed = RUNTIME_ALLOWLIST | NETWORK_ALLOWLIST
    if relative not in allowed:
        fail(f"unclassified Python process/network operation: {relative}: {sorted(operations)}")
    required_anchors(relative, source)


def check_javascript(relative: str, source: str) -> None:
    if "child_process" not in source or not re.search(r"(?:spawn|exec|fork)(?:Sync)?\s*\(", source):
        return
    if is_harness(relative):
        return
    if relative not in JS_ALLOWLIST:
        fail(f"unclassified JavaScript child process: {relative}")
    required_anchors(relative, source)


def check_shell(relative: str, source: str) -> None:
    if not re.search(r"(?m)(?:^|[;&|]\s*)(?:curl|wget)\b", source):
        return
    if is_harness(relative):
        return
    if relative not in SHELL_ALLOWLIST:
        fail(f"unclassified shell network operation: {relative}")
    required_anchors(relative, source)


def self_test() -> None:
    samples = {
        "import subprocess as sp\nsp.run(['x'])": "subprocess.run",
        "from subprocess import Popen as launch\nlaunch(['x'])": "subprocess.Popen",
        "import asyncio as aio\naio.create_subprocess_exec('x')": "asyncio.create_subprocess_exec",
        "from urllib.request import urlopen as fetch\nfetch('https://example.invalid')": "urllib.request.urlopen",
        "import urllib.request\nurllib.request.urlopen('https://example.invalid')": "urllib.request.urlopen",
    }
    for source, expected in samples.items():
        if expected not in python_operations(source):
            fail(f"detector missed aliased operation: {expected}")


def main() -> int:
    self_test()
    for root in (ROOT / "scripts", ROOT / "skills"):
        for path in sorted(root.rglob("*")):
            if path.suffix not in {".py", ".js", ".mjs", ".sh"} or not path.is_file():
                continue
            if "node_modules" in path.parts:
                continue
            relative = path.relative_to(ROOT).as_posix()
            if under_managed(relative):
                continue
            source = path.read_text(encoding="utf-8")
            if path.suffix == ".py":
                check_python(path, relative, source)
            elif path.suffix in {".js", ".mjs"}:
                check_javascript(relative, source)
            else:
                check_shell(relative, source)
    print("bounded-operations-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
