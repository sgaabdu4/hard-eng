#!/usr/bin/env python3
"""Regression proof for package-scoped Dart Decimate execution."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "skills/deterministic-checks/scripts/dart_decimate_gate.py"


def fail(message: str) -> None:
    raise SystemExit(f"dart-decimate-gate-regressions: {message}")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    if result.returncode:
        fail(result.stderr.strip() or "fixture git failed")
    return result.stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def invoke(
    package: Path,
    environment: dict[str, str],
    *mode: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATE), "--package", str(package), *mode],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )


def main() -> int:
    contracts = {
        ROOT / "skills/deterministic-checks/SKILL.md": "[Dart Decimate]",
        ROOT
        / "skills/deterministic-checks/references/dart-decimate.md": "exact repo-relative `--workspace`",
    }
    for path, anchor in contracts.items():
        if anchor not in path.read_text(encoding="utf-8"):
            fail(f"canonical route missing: {path.relative_to(ROOT)}")

    with tempfile.TemporaryDirectory(prefix="dart-decimate-scope-") as temporary:
        temporary_root = Path(temporary)
        root = (temporary_root / "repo").resolve()
        package = root / "functions/worker"
        sibling = root / "apps/mobile"
        duplicate_name = root / "tmp/worker-copy"
        write(root / "pubspec.yaml", "name: workspace_root\n")
        write(package / "pubspec.yaml", "name: worker\n")
        write(package / "lib/main.dart", "void main() {}\n")
        write(sibling / "pubspec.yaml", "name: mobile\n")
        write(sibling / "lib/main.dart", "void main() {}\n")
        write(duplicate_name / "pubspec.yaml", "name: worker\n")
        write(duplicate_name / "lib/main.dart", "void main() {}\n")
        run_git(root, "init", "-q", "-b", "main")
        run_git(root, "config", "user.email", "fixture@example.invalid")
        run_git(root, "config", "user.name", "Fixture")
        run_git(root, "add", ".")
        run_git(root, "commit", "-q", "-m", "baseline")

        fake_bin = temporary_root / "bin"
        capture = temporary_root / "capture.json"
        fake_npx = fake_bin / "npx"
        write(
            fake_npx,
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['DART_DECIMATE_CAPTURE']).write_text("
            "json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}))\n"
            "if os.environ.get('DART_DECIMATE_REPORT'):\n"
            "    print(os.environ['DART_DECIMATE_REPORT'])\n"
            "raise SystemExit(int(os.environ.get('DART_DECIMATE_EXIT', '0')))\n",
        )
        fake_npx.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "DART_DECIMATE_CAPTURE": str(capture),
        }

        changed = invoke(package, environment, "--base", "HEAD")
        if changed.returncode:
            fail(changed.stderr.strip() or "nested package gate failed")
        expected_changed = [
            "--yes",
            "dart-decimate",
            "audit",
            str(root),
            "--base",
            "HEAD",
            "--format",
            "json",
            "--summary",
            "--gate",
            "new-only",
            "--workspace",
            "functions/worker",
        ]
        if json.loads(capture.read_text()) != {
            "argv": expected_changed,
            "cwd": str(root),
        }:
            fail("nested package lost exact workspace scope")

        full = invoke(package, environment, "--full")
        if full.returncode:
            fail("nested full gate failed")
        if json.loads(capture.read_text()) != {
            "argv": [
                "--yes",
                "dart-decimate",
                "json",
                str(root),
                "--workspace",
                "functions/worker",
            ],
            "cwd": str(root),
        }:
            fail("nested full gate lost exact workspace scope")

        root_gate = invoke(root, environment, "--base", "HEAD")
        if root_gate.returncode:
            fail("repository-root gate failed")
        root_invocation = json.loads(capture.read_text())
        if "--workspace" in root_invocation["argv"]:
            fail("repository-root package was incorrectly narrowed")

        blocked = invoke(
            package, {**environment, "DART_DECIMATE_EXIT": "8"}, "--base", "HEAD"
        )
        if blocked.returncode != 8:
            fail("upstream blocking exit was weakened")

        upstream_report = '{"command":"audit","verdict":"fail"}'
        upstream_failure = invoke(
            package,
            {
                **environment,
                "DART_DECIMATE_EXIT": "1",
                "DART_DECIMATE_REPORT": upstream_report,
            },
            "--base",
            "HEAD",
        )
        if upstream_failure.returncode != 1 or upstream_failure.stdout.strip() != (
            upstream_report
        ):
            fail("upstream report was reclassified or rewritten")

        outside = temporary_root / "outside"
        write(outside / "pubspec.yaml", "name: outside\n")
        rejected = invoke(outside, environment, "--base", "HEAD")
        if rejected.returncode != 2:
            fail("package outside a Git repository was not rejected")

    print("dart-decimate-gate-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
