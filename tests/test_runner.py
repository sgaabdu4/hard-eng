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
from gate_config import (
    GateConfig,
    Group,
    load_groups,
    validate_file_sizes,
    validate_group,
)


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


def native_gate_fixture(root: Path, installer: ModuleType, language: str) -> GateConfig:
    name, content, source = {
        "python": (
            "pyproject.toml",
            '[project]\nname="fixture"\nversion="1.0.0"\n',
            "src/app.py",
        ),
        "javascript": (
            "package.json",
            '{"scripts":{"test:coverage":"node tests.js","test:performance":"node performance.js"}}',
            "src/app.js",
        ),
        "dart": (
            "pubspec.yaml",
            'name: fixture\nenvironment:\n  sdk: ">=3.0.0 <4.0.0"\n',
            "lib/app.dart",
        ),
    }[language]
    (root / name).write_text(content)
    (root / "pnpm-lock.yaml").touch()
    (root / source).parent.mkdir(parents=True, exist_ok=True)
    (root / source).write_text("# fixture\n")
    config: GateConfig = installer.gate_config(root)
    (root / "hard-eng.gates.json").write_text(json.dumps(config))
    load_groups(root)
    return config


@pytest.mark.parametrize(
    "language,role",
    [
        (language, role)
        for language, roles in {
            "python": "format lint complexity types annotations tests performance dead-code duplicates dependencies lockfiles vulnerabilities security",
            "javascript": "format-lint focused-tests types typing-style tests performance dead-code-duplicates lockfiles vulnerabilities security",
            "dart": "format types tests performance dead-code-duplicates boundaries lockfiles vulnerabilities security",
        }.items()
        for role in roles.split()
    ],
)
def test_removing_package_baseline_fails_before_execution(
    runner: ModuleType, installer: ModuleType, tmp_path: Path, language: str, role: str
) -> None:
    config = native_gate_fixture(tmp_path, installer, language)
    package = config["packages"][0]
    package["checks"] = [
        check for check in package["checks"] if check.get("role") != role
    ]
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match=role):
        runner.check()


@pytest.mark.parametrize("role", ["secrets-files", "secrets-history"])
def test_removing_shared_security_fails(
    runner: ModuleType, installer: ModuleType, tmp_path: Path, role: str
) -> None:
    config = native_gate_fixture(tmp_path, installer, "python")
    config["shared"] = [gate for gate in config["shared"] if gate.get("role") != role]
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match=role):
        load_groups(tmp_path)
    if role == "secrets-history":
        config["scan_git_history"] = False
        (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
        load_groups(tmp_path)


@pytest.mark.parametrize(
    "filename,role",
    [
        (".github/workflows/build.yml", "workflows"),
        ("helper.sh", "shell"),
        ("Dockerfile", "deployment"),
    ],
)
def test_new_repository_inputs_require_applicable_gates(
    runner: ModuleType, installer: ModuleType, tmp_path: Path, filename: str, role: str
) -> None:
    native_gate_fixture(tmp_path, installer, "python")
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture\n")
    with pytest.raises(ValueError, match=role):
        load_groups(tmp_path)


def test_omitting_package_or_language_cannot_remove_baseline(
    runner: ModuleType, installer: ModuleType, tmp_path: Path
) -> None:
    config = native_gate_fixture(tmp_path, installer, "python")
    package = config["packages"].pop()
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="package is missing"):
        load_groups(tmp_path)
    package.pop("language")
    config["packages"].append(package)
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    with pytest.raises(ValueError, match="package language"):
        load_groups(tmp_path)
    package["language"] = "python"
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    (tmp_path / "package.json").write_text('{"private":true}')
    with pytest.raises(ValueError, match="javascript package is missing"):
        load_groups(tmp_path)


@pytest.mark.parametrize(
    "feature,role",
    [
        ("build", "build"),
        ("test:integration", "integration"),
        ("test:ui", "ui"),
        ("check:generated", "generated"),
        ("react", "react"),
        ("imports", "imports"),
    ],
)
def test_package_features_require_their_checks(
    runner: ModuleType, installer: ModuleType, tmp_path: Path, feature: str, role: str
) -> None:
    language = "python" if feature == "imports" else "javascript"
    native_gate_fixture(tmp_path, installer, language)
    if language == "python":
        (tmp_path / "src/library").mkdir()
        (tmp_path / "src/library/__init__.py").touch()
    else:
        path = tmp_path / "package.json"
        manifest = json.loads(path.read_text())
        if feature == "react":
            manifest["dependencies"] = {"react": "19.0.0"}
        else:
            manifest["scripts"][feature] = "node fixture.js"
        path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=role):
        load_groups(tmp_path)


def test_workspace_cannot_cover_unrelated_packages_or_child_security(
    runner: ModuleType, installer: ModuleType, tmp_path: Path
) -> None:
    native_gate_fixture(tmp_path, installer, "javascript")
    workspace = tmp_path / "pnpm-workspace.yaml"
    workspace.write_text("packages:\n  - packages/*\n")
    child = tmp_path / "packages/app"
    (child / "src").mkdir(parents=True)
    (child / "package.json").write_text((tmp_path / "package.json").read_text())
    (child / "src/app.js").write_text("export const value = 1;\n")
    config: GateConfig = installer.gate_config(tmp_path)
    path = tmp_path / "hard-eng.gates.json"
    path.write_text(json.dumps(config))
    load_groups(tmp_path)
    app = next(group for group in config["packages"] if group["path"] == "packages/app")
    assert not {"lockfiles", "vulnerabilities"} & {
        gate.get("role") for gate in app["checks"]
    }
    security = next(gate for gate in app["checks"] if gate.get("role") == "security")
    app["checks"].remove(security)
    path.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="security"):
        load_groups(tmp_path)
    app["checks"].append(security)
    path.write_text(json.dumps(config))
    workspace.write_text("packages: []\n")
    (child / "pnpm-lock.yaml").touch()
    with pytest.raises(ValueError, match="lockfiles"):
        load_groups(tmp_path)


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
            {"name": "format", "role": "format-lint", "command": ["biome"]},
            {"name": "focused", "role": "focused-tests", "command": ["biome"]},
            {"name": "tests", "role": "tests", "command": ["node", "test.js"]},
            {
                "name": "dead-code",
                "role": "dead-code-duplicates",
                "command": ["fallow"],
            },
            {
                "name": "performance",
                "role": "performance",
                "command": ["node", "test.js"],
                "report": {
                    "type": "performance-junit",
                    "path": "coverage/performance.xml",
                },
            },
        ],
    }
    assert validate_group(tmp_path, group, set()) == 7
    performance = group["checks"].pop()
    with pytest.raises(ValueError, match="mandatory performance"):
        validate_group(tmp_path, group, set())
    group["checks"].append(performance)
    performance["parallel"] = True
    with pytest.raises(ValueError, match="serially"):
        validate_group(tmp_path, group, set())
    performance["parallel"] = False
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


@pytest.mark.parametrize(
    "kind", ["deptry", "performance-junit", "performance-dart", "lighthouse-ci"]
)
def test_stale_report_cannot_pass(
    runner: ModuleType, tmp_path: Path, kind: str
) -> None:
    (tmp_path / "old.json").write_text("[]")
    check = gate(kind, "pass", report={"type": kind, "path": "old.json"})
    assert runner.run_gate({"path": "."}, check, 5, threading.Lock()) is True


def test_pre_push_tests_committed_code(installer: ModuleType, tmp_path: Path) -> None:
    root, receiver = tmp_path / "project", tmp_path / "receiver"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "init", "--bare", "-q", str(receiver)], check=True)
    (root / "package.json").write_text('{"private":true}')
    (root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    installer.install(root)
    # This fixture tests the Git boundary with an ad-hoc command, not an app suite.
    (root / "package.json").unlink()
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
