#!/usr/bin/env python3
"""Regression proof for repository-root Dart Decimate attribution."""

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


def main() -> int:
    if not GATE.is_file():
        fail("canonical gate runner missing")
    contracts = {
        ROOT
        / "skills/deterministic-checks/SKILL.md": "repository-root [Dart Decimate]",
        ROOT
        / "skills/deterministic-checks/references/dart-decimate.md": "dart_decimate_gate.py",
        ROOT
        / "skills/building-flutter-apps/references/dart-decimate.md": "dart_decimate_gate.py",
    }
    for path, anchor in contracts.items():
        if anchor not in path.read_text(encoding="utf-8"):
            fail(f"canonical route missing: {path.relative_to(ROOT)}")
    with tempfile.TemporaryDirectory(prefix="dart-decimate-nested-") as temporary:
        root = (Path(temporary) / "repo").resolve()
        package = root / "functions/worker"
        shared = package / "ff_shared/lib/shared.dart"
        write(package / "pubspec.yaml", "name: worker\n")
        write(package / "lib/main.dart", "void main() {}\n")
        write(shared, "const sharedValue = 1;\n")
        run_git(root, "init", "-q", "-b", "main")
        run_git(root, "config", "user.email", "fixture@example.invalid")
        run_git(root, "config", "user.name", "Fixture")
        run_git(root, "add", ".")
        run_git(root, "commit", "-q", "-m", "baseline")
        write(shared, "const sharedValue = 2;\n")
        tracked = run_git(root, "diff", "--name-only", "HEAD", "--")
        if tracked != "functions/worker/ff_shared/lib/shared.dart":
            fail("fixture lost repository-relative nested attribution")

        fake_bin = Path(temporary) / "bin"
        capture = Path(temporary) / "capture.json"
        fake_npx = fake_bin / "npx"
        write(
            fake_npx,
            "#!/usr/bin/env python3\n"
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "Path(os.environ['DART_DECIMATE_CAPTURE']).write_text("
            "json.dumps({'argv': sys.argv[1:], 'cwd': os.getcwd()}))\n"
            "raise SystemExit(int(os.environ.get('DART_DECIMATE_EXIT', '0')))\n",
        )
        fake_npx.chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            "DART_DECIMATE_CAPTURE": str(capture),
        }
        result = subprocess.run(
            [
                sys.executable,
                str(GATE),
                "--package",
                str(package),
                "--base",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        if result.returncode:
            fail(result.stderr.strip() or "nested package gate failed")
        invoked = json.loads(capture.read_text(encoding="utf-8"))
        expected = [
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
        ]
        if invoked != {"argv": expected, "cwd": str(root)}:
            fail(f"nested package was not mapped to repository root: {invoked}")

        blocked_environment = {**environment, "DART_DECIMATE_EXIT": "8"}
        blocked = subprocess.run(
            [
                sys.executable,
                str(GATE),
                "--package",
                str(package),
                "--base",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            env=blocked_environment,
            check=False,
        )
        if blocked.returncode != 8:
            fail("Dart Decimate blocking exit was weakened")

        full = subprocess.run(
            [sys.executable, str(GATE), "--package", str(package), "--full"],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        if full.returncode:
            fail("explicit full gate failed")
        full_invoked = json.loads(capture.read_text(encoding="utf-8"))
        if full_invoked != {
            "argv": ["--yes", "dart-decimate", "json", str(root)],
            "cwd": str(root),
        }:
            fail("full gate did not preserve repository-root mapping")

        outside = Path(temporary) / "outside"
        write(outside / "pubspec.yaml", "name: outside\n")
        rejected = subprocess.run(
            [sys.executable, str(GATE), "--package", str(outside), "--base", "HEAD"],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        if rejected.returncode != 2:
            fail("package outside repository was not rejected")

    print("dart-decimate-gate-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
