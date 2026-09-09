"""Exercise real command exits, ordering, documents and coverage boundaries."""

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest
import tool_setup
from gate_config import Group, validate_file_sizes, validate_group


def test_file_size_boundary_and_narrow_exceptions(
    runner: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "large.py"
    path.write_text("value = 1\n" * 700)
    validate_file_sizes(tmp_path, {})
    path.write_text("value = 1\n" * 701)
    with pytest.raises(ValueError, match="701"):
        validate_file_sizes(tmp_path, {})
    with pytest.raises(ValueError, match="reason and evidence"):
        validate_file_sizes(
            tmp_path, {"*.py": {"reason": "broad", "evidence": "invalid"}}
        )
    validate_file_sizes(
        tmp_path, {"large.py": {"reason": "fixture", "evidence": "exact-file test"}}
    )
    (tmp_path / ".gitattributes").write_text("large.py linguist-generated=true\n")
    validate_file_sizes(tmp_path, {})


def test_history_exception_keeps_current_file_scanning(
    runner: ModuleType, tmp_path: Path
) -> None:
    checks = [
        gate("history", "raise SystemExit(1)", role="secrets-history"),
        gate("current", "from pathlib import Path;Path('scanned').touch()"),
    ]
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": checks, "scan_git_history": False})
    )
    assert runner.check() == 0
    assert (tmp_path / "scanned").is_file()


def gate(name: str, code: str, **options: object) -> dict[str, object]:
    return {"name": name, "command": [sys.executable, "-c", code], **options}


def configure(root: Path, checks: list[dict[str, object]]) -> None:
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": checks})
    )


def test_command_failure_survives_later_pass(
    runner: ModuleType, tmp_path: Path
) -> None:
    configure(
        tmp_path, [gate("fails", "raise SystemExit(2)"), gate("passes", "print('ok')")]
    )
    assert runner.check() == 1
    configure(tmp_path, [gate("passes", "print('ok')")])
    assert runner.check() == 0


def test_missing_command_and_timeout_fail(runner: ModuleType) -> None:
    missing = {"name": "missing", "command": ["/nonexistent/hard-eng-check"]}
    assert runner.run_gate({"path": "."}, missing, 1, threading.Lock()) is True
    assert (
        runner.run_gate(
            {"path": "."},
            gate("timeout", "import time;time.sleep(5)"),
            0.02,
            threading.Lock(),
        )
        is True
    )


@pytest.mark.parametrize("response", ["raise SystemExit(2)", "print('{}')"])
def test_tool_setup_failure_prevents_gate_execution(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: str
) -> None:
    executable = tmp_path / "bin/pnpm"
    executable.parent.mkdir()
    executable.write_text(f"#!{sys.executable}\n{response}\n")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ["PATH"])
    configure(
        tmp_path,
        [
            {"name": "scanner", "command": ["gitleaks", "version"]},
            gate("application", "from pathlib import Path;Path('ran').touch()"),
        ],
    )
    with pytest.raises((subprocess.CalledProcessError, TypeError)):
        runner.check()
    assert not (tmp_path / "ran").exists()


def test_lock_setup_runs_first_and_blocks_on_failure(
    runner: ModuleType, tmp_path: Path
) -> None:
    ordinary = gate(
        "check",
        "from pathlib import Path;assert Path('ready').exists();Path('ran').touch()",
    )
    setup = gate(
        "setup", "from pathlib import Path;Path('ready').touch()", role="lockfiles"
    )
    configure(tmp_path, [ordinary, setup])
    assert runner.check() == 0
    assert (tmp_path / "ran").exists()
    (tmp_path / "ran").unlink()
    configure(
        tmp_path,
        [ordinary, gate("broken-setup", "raise SystemExit(1)", role="lockfiles")],
    )
    assert runner.check() == 1
    assert not (tmp_path / "ran").exists()


def test_parallel_checks_overlap_with_two_worker_bound(
    runner: ModuleType, tmp_path: Path
) -> None:
    code = "from pathlib import Path;import time;Path('{name}.start').write_text(str(time.monotonic()));time.sleep({delay});Path('{name}.end').write_text(str(time.monotonic()))"
    configure(
        tmp_path,
        [
            gate(name, code.format(name=name, delay=delay), parallel=True)
            for name, delay in (("slow", 0.5), ("quick", 0.08), ("third", 0.08))
        ],
    )
    assert runner.check() == 0
    times = {path.name: float(path.read_text()) for path in tmp_path.glob("*.start")}
    times.update(
        {path.name: float(path.read_text()) for path in tmp_path.glob("*.end")}
    )
    assert times["quick.start"] < times["slow.end"]
    assert times["third.start"] >= times["quick.end"]
    assert times["third.end"] < times["slow.end"]


@pytest.mark.parametrize("document", ["PRODUCT.md", "DESIGN.md"])
@pytest.mark.parametrize("content", ["", "   \n", "# Title\n[TODO: fill]", "# Title\n"])
def test_invalid_documents_prevent_commands(
    runner: ModuleType, tmp_path: Path, document: str, content: str
) -> None:
    (tmp_path / document).write_text(content)
    configure(
        tmp_path, [gate("side-effect", "from pathlib import Path;Path('ran').touch()")]
    )
    with pytest.raises(ValueError):
        runner.check()
    assert not (tmp_path / "ran").exists()


@pytest.mark.parametrize(
    "checks",
    [
        [],
        [{"name": "bad", "command": []}],
        [{"name": "bad", "command": ["true"], "parallel": "yes"}],
    ],
)
def test_invalid_manifest_fails_before_commands(
    runner: ModuleType, tmp_path: Path, checks: list[dict[str, object]]
) -> None:
    configure(tmp_path, checks)
    with pytest.raises((ValueError, TypeError)):
        runner.check()


def test_report_collision_rejected(runner: ModuleType, tmp_path: Path) -> None:
    configure(
        tmp_path,
        [gate(name, "pass", report={"path": "same.json"}) for name in ("a", "b")],
    )
    with pytest.raises(ValueError, match="distinct"):
        runner.check()


@pytest.mark.parametrize(
    "language,command",
    [
        ("python", ["pytest", "-k", "one"]),
        ("python", ["pytest", "tests/a.py::test_one"]),
        ("javascript", ["vitest", "--testNamePattern=x"]),
        ("dart", ["flutter", "test", "--plain-name=x"]),
    ],
)
def test_suite_filters_are_rejected(
    runner: ModuleType, tmp_path: Path, language: str, command: list[str]
) -> None:
    with pytest.raises(ValueError, match="Focused"):
        runner.reject_test_filters(command, tmp_path, language)


def test_nested_package_script_filter_rejected(
    runner: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "test:coverage": "pnpm run unit",
                    "unit": "vitest --testNamePattern=x",
                }
            }
        )
    )
    with pytest.raises(ValueError, match="Focused"):
        runner.reject_test_filters(
            ["pnpm", "run", "test:coverage"], tmp_path, "javascript"
        )


def test_gate_validation_rejects_javascript_package_manager_drift(
    tmp_path: Path,
) -> None:
    (tmp_path / "package.json").write_text('{"packageManager":"pnpm@11.18.0"}')
    (tmp_path / "pnpm-lock.yaml").touch()
    group: Group = {
        "path": ".",
        "language": "javascript",
        "sources": ["src"],
        "checks": [
            {"name": "types", "role": "types", "command": ["tsc"]},
            {"name": "typing", "role": "typing-style", "command": ["biome"]},
        ],
    }
    assert validate_group(tmp_path, group, set()) == 2
    (tmp_path / "package-lock.json").touch()
    with pytest.raises(ValueError, match="legacy lockfiles"):
        validate_group(tmp_path, group, set())
    (tmp_path / "package-lock.json").unlink()
    group["checks"][0]["command"] = ["npm", "run", "typecheck"]
    with pytest.raises(ValueError, match="must use pnpm"):
        validate_group(tmp_path, group, set())
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "packageManager": "pnpm@11.18.0",
                "scripts": {"typecheck": "pnpm run unit", "unit": "npx c8 test"},
            }
        )
    )
    group["checks"][0]["command"] = ["pnpm", "run", "typecheck"]
    with pytest.raises(ValueError, match="must use pnpm, not: npx"):
        validate_group(tmp_path, group, set())


def test_source_files_include_unexecuted_modules(
    runner: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "src").mkdir()
    for name in ("used.ts", "unused.ts", "types.d.ts", "used.test.ts"):
        (tmp_path / "src" / name).write_text("export const value = 1;\n")
    files = runner.production_files(
        tmp_path, {"language": "javascript", "sources": ["src"]}
    )
    assert {path.name for path in files} == {"used.ts", "unused.ts"}
    typed = runner.production_files(
        tmp_path, {"language": "javascript", "sources": ["src"]}, include_tests=True
    )
    assert {path.name for path in typed} == {"used.ts", "unused.ts", "used.test.ts"}


def test_coverage_excludes_native_generated_and_vendor_attributes(
    runner: ModuleType, tmp_path: Path
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitattributes").write_text(
        "generated.py linguist-generated=true\nexternal.py linguist-vendored=true\n"
    )
    for name in ("app.py", "generated.py", "external.py"):
        (tmp_path / name).write_text("value = 1\n")
    group = {"language": "python", "sources": ["."]}
    assert {p.name for p in runner.production_files(tmp_path, group)} == {"app.py"}
    assert len(runner.production_files(tmp_path, group, include_tests=True)) == 3


def test_native_tool_bootstrap_uses_pnpm_and_preserves_ci_sdk_executables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sdk, scanner = tmp_path / "sdk", tmp_path / "hard-eng-tools/scanner"
    for directory, executable in ((sdk, "uv"), (scanner, "gitleaks")):
        directory.mkdir(parents=True)
        path = directory / executable
        path.write_text("#!/bin/sh\nexit 0\n")
        path.chmod(0o755)
    monkeypatch.setenv("PATH", str(sdk))
    monkeypatch.setattr(tool_setup.tempfile, "gettempdir", lambda: str(tmp_path))
    captured: list[str] = []

    def native_environment(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        captured.extend(command)
        return subprocess.CompletedProcess(
            command, 0, json.dumps({"PATH": str(scanner)}), ""
        )

    monkeypatch.setattr(subprocess, "run", native_environment)
    tool_setup.provision_tools(
        tmp_path,
        [{"path": ".", "checks": [{"name": "secrets", "command": ["gitleaks"]}]}],
        30,
    )
    assert shutil.which("uv") == str(sdk / "uv")
    assert shutil.which("gitleaks") == str(scanner / "gitleaks")
    assert captured[:2] == ["env", f"MISE_DATA_DIR={tmp_path}/hard-eng-tools/mise/data"]
    assert f"PNPM_CONFIG_STORE_DIR={tmp_path}/hard-eng-tools/pnpm/store" in captured
    assert f"PNPM_CONFIG_CACHE_DIR={tmp_path}/hard-eng-tools/pnpm/cache" in captured
    assert captured[captured.index("pnpm") :] == [
        "pnpm",
        "dlx",
        "--allow-build=@jdxcode/mise",
        "--package=@jdxcode/mise@latest",
        "mise",
        "--no-config",
        "env",
        "--json",
        "aqua:gitleaks/gitleaks@latest",
    ]


@pytest.mark.parametrize(
    "name,content",
    [
        ("pytest.ini", "[pytest]\naddopts = -k selected\n"),
        ("pyproject.toml", '[tool.pytest.ini_options]\naddopts = "-m selected"\n'),
        ("pytest.toml", '[pytest]\naddopts = ["--last-failed"]\n'),
        ("setup.cfg", "[tool:pytest]\naddopts = --deselect=tests/test_app.py\n"),
    ],
)
def test_pytest_configuration_cannot_filter_the_required_suite(
    runner: ModuleType, tmp_path: Path, name: str, content: str
) -> None:
    (tmp_path / name).write_text(content)
    with pytest.raises(ValueError, match="Focused test selection"):
        runner.reject_test_filters(["pytest"], tmp_path, "python")


def test_pytest_empty_priority_config_does_not_inherit_unused_filters(
    runner: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "pytest.ini").write_text("")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\naddopts="-k selected"\n'
    )
    runner.reject_test_filters(["pytest"], tmp_path, "python")


@pytest.mark.parametrize("covered,expected", [(7, False), (6, True)])
def test_real_runner_coverage_threshold(
    runner: ModuleType, tmp_path: Path, covered: int, expected: bool
) -> None:
    (tmp_path / "main.py").write_text("value = 1\n")
    report = {
        "files": {
            "main.py": {"summary": {"covered_lines": covered, "num_statements": 10}}
        }
    }
    code = f"from pathlib import Path;Path('coverage/junit.xml').write_text('<testsuite><testcase name=\"ok\"/></testsuite>');Path('coverage/coverage.json').write_text({json.dumps(report)!r})"
    check = gate(
        "tests",
        code,
        role="tests",
        report={
            "type": "python-tests",
            "tests": "coverage/junit.xml",
            "coverage": "coverage/coverage.json",
        },
    )
    assert (
        runner.run_gate(
            {"path": ".", "language": "python", "sources": ["main.py"]},
            check,
            5,
            threading.Lock(),
        )
        is expected
    )


def test_stale_report_cannot_pass(runner: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "old.json").write_text("[]")
    check = gate("deptry", "pass", report={"type": "deptry", "path": "old.json"})
    assert runner.run_gate({"path": "."}, check, 5, threading.Lock()) is True


def test_pre_push_tests_committed_code(installer: ModuleType, tmp_path: Path) -> None:
    root, receiver = tmp_path / "project", tmp_path / "receiver"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "init", "--bare", "-q", str(receiver)], check=True)
    (root / "package.json").write_text('{"private":true}')
    (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    installer.install(root)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (root / name).write_text((Path(installer.SOURCE) / name).read_text())
    configure(root, [gate("committed-check", "raise SystemExit(1)")])
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=root,
        check=True,
    )
    configure(root, [gate("local-repair", "pass")])
    result = subprocess.run(
        ["git", "push", str(receiver), "HEAD:refs/heads/main"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "FAIL committed-check" in result.stdout
    assert "local-repair" in (root / "hard-eng.gates.json").read_text()
    refs = (
        subprocess.check_output(["git", "show-ref"], cwd=receiver, text=True)
        if (receiver / "refs/heads/main").exists()
        else ""
    )
    assert not refs
    assert (
        len(
            subprocess.check_output(
                ["git", "worktree", "list", "--porcelain"], cwd=root, text=True
            ).split("worktree ")
        )
        == 2
    )
