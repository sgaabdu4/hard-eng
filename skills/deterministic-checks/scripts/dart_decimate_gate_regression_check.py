#!/usr/bin/env python3
"""Regression proof for full package-scoped Dart Decimate execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "skills/deterministic-checks/scripts/dart_decimate_gate.py"
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env, scrub_environ
from script_runner import ScriptResult, run_script

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> NoReturn:
    raise SystemExit(f"dart-decimate-gate-regressions: {message}")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False, env=git_env())
    if result.returncode:
        fail(result.stderr.strip() or "fixture git failed")
    return result.stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def invoke(package: Path, environment: dict[str, str], *extra: str, timeout: str = "10") -> ScriptResult:
    return run_script(GATE, ["--package", str(package), "--timeout", timeout, *extra], env=environment)


def main() -> int:
    contracts = {
        ROOT / "skills/deterministic-checks/SKILL.md": "one full owner scan + zero findings",
        ROOT / "skills/deterministic-checks/references/dart-decimate.md": "unchanged upstream exit",
    }
    for path, anchor in contracts.items():
        if anchor not in path.read_text(encoding="utf-8"):
            fail(f"canonical route missing: {path.relative_to(ROOT)}")

    with tempfile.TemporaryDirectory(prefix="dart-decimate-scope-") as temporary:
        temporary_root = Path(temporary)
        root = (temporary_root / "repo").resolve()
        package = root / "functions/worker"
        write(root / "pubspec.yaml", "name: workspace_root\n")
        write(package / "pubspec.yaml", "name: worker\n")
        write(package / "lib/main.dart", "void main() {}\n")
        run_git(root, "init", "-q", "-b", "main")

        fake_bin = temporary_root / "bin"
        capture = temporary_root / "capture.json"
        fake_npx = fake_bin / "npx"
        write(
            fake_npx,
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['DART_DECIMATE_CAPTURE']).write_text(json.dumps({"
            "'argv': sys.argv[1:], 'cwd': os.getcwd(), "
            "'git_dir': os.environ.get('GIT_DIR'), "
            "'git_work_tree': os.environ.get('GIT_WORK_TREE')}))\n"
            "print(os.environ.get('DART_DECIMATE_REPORT', ''))\n"
            "raise SystemExit(int(os.environ.get('DART_DECIMATE_EXIT', '0')))\n",
        )
        fake_npx.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "DART_DECIMATE_CAPTURE": str(capture),
            "GIT_DIR": str(temporary_root / "poison.git"),
            "GIT_WORK_TREE": str(temporary_root / "poison-tree"),
        }

        nested = invoke(package, environment)
        if nested.returncode:
            fail(nested.stderr.strip() or "nested package gate failed")
        expected = {
            "argv": ["--yes", "dart-decimate@latest", "json", str(root), "--workspace", "functions/worker"],
            "cwd": str(root),
            "git_dir": None,
            "git_work_tree": None,
        }
        if json.loads(capture.read_text()) != expected:
            fail("nested package lost full exact scope or inherited Git variables")

        root_gate = invoke(root, environment)
        if root_gate.returncode:
            fail("repository-root gate failed")
        root_invocation = json.loads(capture.read_text())
        if "--workspace" in root_invocation["argv"]:
            fail("repository-root package was incorrectly narrowed")

        for upstream_exit in (1, 2, 8):
            blocked = invoke(
                package,
                {**environment, "DART_DECIMATE_EXIT": str(upstream_exit), "DART_DECIMATE_REPORT": "upstream-report"},
            )
            if blocked.returncode != upstream_exit or blocked.stdout.strip() != "upstream-report":
                fail(f"upstream exit {upstream_exit} or output was weakened")

        for old_mode in (("--base", "HEAD"), ("--full",)):
            rejected = invoke(package, environment, *old_mode)
            if rejected.returncode != 2:
                fail(f"legacy scoped mode was accepted: {' '.join(old_mode)}")

        local_bin = root / "tools"
        local_npx = local_bin / "npx"
        write(local_npx, fake_npx.read_text(encoding="utf-8"))
        local_npx.chmod(0o755)
        local_environment = {**environment, "PATH": f"{local_bin}{os.pathsep}{os.environ.get('PATH', '')}"}
        rejected = invoke(package, local_environment)
        if rejected.returncode != 2 or "outside" not in rejected.stderr:
            fail("project-local npx resolution was accepted")

        package_manifest = root / "package.json"
        write(package_manifest, json.dumps({"devDependencies": {"dart-decimate": "latest"}}))
        rejected = invoke(package, environment)
        if rejected.returncode != 2 or "dependencies" not in rejected.stderr:
            fail("project-local Dart Decimate dependency was accepted")
        package_manifest.unlink()

        marker = temporary_root / "exclusive.locked"
        holder = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import pathlib,sys,time\n"
                    "from source_tree_coordination import source_tree_lock\n"
                    "root=pathlib.Path(sys.argv[1])\n"
                    "marker=pathlib.Path(sys.argv[2])\n"
                    "deadline=time.monotonic()+5\n"
                    "with source_tree_lock(root,exclusive=True,deadline=deadline):\n"
                    " marker.write_text('locked')\n"
                    " time.sleep(0.8)\n"
                ),
                str(root),
                str(marker),
            ],
            env={**os.environ, "PYTHONPATH": str(GIT_ENV_SCRIPTS)},
        )
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        if not marker.exists():
            holder.kill()
            fail("exclusive source-lock fixture did not start")
        blocked = invoke(package, environment, timeout="0.15")
        if blocked.returncode != 2 or "timeout" not in blocked.stderr:
            holder.kill()
            fail("Dart Decimate did not share source-tree coordination")
        if holder.wait(timeout=3):
            fail("exclusive source-lock fixture failed")

        for invalid_timeout in ("nan", "inf", "0", "-1"):
            rejected = invoke(package, environment, timeout=invalid_timeout)
            if rejected.returncode != 2 or "Traceback" in rejected.stderr:
                fail(f"invalid timeout was not rejected cleanly: {invalid_timeout}")

        outside = temporary_root / "outside"
        write(outside / "pubspec.yaml", "name: outside\n")
        rejected = invoke(outside, environment)
        if rejected.returncode != 2:
            fail("package outside a Git repository was not rejected")

    print("dart-decimate-gate-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
