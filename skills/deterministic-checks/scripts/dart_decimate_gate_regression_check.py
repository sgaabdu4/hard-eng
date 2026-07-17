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
        existing = package / "lib/existing.dart"
        write(existing, 'const existingToken = "not-a-secret";\n')
        write(shared, 'const sharedToken = "not-a-secret";\nconst sharedValue = 1;\n')
        run_git(root, "init", "-q", "-b", "main")
        run_git(root, "config", "user.email", "fixture@example.invalid")
        run_git(root, "config", "user.name", "Fixture")
        run_git(root, "add", ".")
        run_git(root, "commit", "-q", "-m", "baseline")
        write(shared, 'const sharedToken = "not-a-secret";\nconst sharedValue = 2;\n')
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
            "report = os.environ.get('DART_DECIMATE_REPORT')\n"
            "if report:\n"
            "    print(Path(report).read_text())\n"
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

        report_path = Path(temporary) / "false-security-group.json"
        report = {
            "command": "audit",
            "verdict": "fail",
            "summary": {
                "attribution": {
                    "introduced": {"error_findings": 1},
                    "pre_existing": {"error_findings": 0},
                }
            },
            "findings": [
                {
                    "kind": "security-candidate",
                    "severity": "error",
                    "fingerprint": "sec:fixture",
                    "path": "functions/worker/ff_shared/lib/shared.dart",
                    "files": [
                        "functions/worker/ff_shared/lib/shared.dart",
                        "functions/worker/lib/existing.dart",
                    ],
                }
            ],
            "security_candidates": [
                {
                    "fingerprint": "sec:fixture",
                    "occurrences": [
                        {
                            "path": "functions/worker/ff_shared/lib/shared.dart",
                            "line": 1,
                        },
                        {
                            "path": "functions/worker/lib/existing.dart",
                            "line": 1,
                        },
                    ],
                }
            ],
        }
        report_path.write_text(json.dumps(report), encoding="utf-8")
        false_group = subprocess.run(
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
            env={
                **environment,
                "DART_DECIMATE_EXIT": "1",
                "DART_DECIMATE_REPORT": str(report_path),
            },
            check=False,
        )
        if false_group.returncode:
            fail("unchanged grouped security occurrences remained blocking")
        corrected = json.loads(false_group.stdout)
        receipt = corrected.get("hard_eng_gate", {})
        if receipt.get("result") != "pass" or receipt.get(
            "inherited_security_fingerprints"
        ) != ["sec:fixture"]:
            fail("false security group lacked deterministic correction receipt")
        if corrected["findings"] != report["findings"]:
            fail("security evidence was suppressed during attribution correction")

        write(
            shared, 'const sharedToken = "changed-candidate";\nconst sharedValue = 2;\n'
        )
        introduced = subprocess.run(
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
            env={
                **environment,
                "DART_DECIMATE_EXIT": "1",
                "DART_DECIMATE_REPORT": str(report_path),
            },
            check=False,
        )
        if introduced.returncode != 1:
            fail("changed security occurrence was incorrectly inherited")

        malformed_path = Path(temporary) / "malformed.json"
        malformed_path.write_text("{not-json", encoding="utf-8")
        malformed = subprocess.run(
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
            env={
                **environment,
                "DART_DECIMATE_EXIT": "1",
                "DART_DECIMATE_REPORT": str(malformed_path),
            },
            check=False,
        )
        if malformed.returncode != 1:
            fail("malformed blocking report did not fail closed")

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
