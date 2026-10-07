"""A project without a supported manifest installs with only the language-neutral gates."""

import json
import os
import sys
from pathlib import Path
from types import ModuleType

import mutation
import pytest
from basic_mode import language_label
from conftest import SOURCE, commit, init, load_module
from gate_config import parse_config, repository_files, validate_required_checks
from shipping import ShippingPolicy

GO_MODULE = "module example\n\ngo 1.22\n\nrequire github.com/pkg/errors v0.9.1\n"


def go_project(root: Path) -> None:
    (root / "go.mod").write_text(GO_MODULE)
    (root / "go.sum").write_text("github.com/pkg/errors v0.9.1 h1:abc=\n")
    (root / "main.go").write_text("package main\n\nfunc main() {}\n")


def no_provisioning(*_arguments: object) -> None:
    return None


def roles(config: dict[str, list[dict[str, object]]]) -> list[object]:
    return [gate["role"] for gate in config["shared"]]


def test_go_project_installs_with_only_shared_gates(
    installer: ModuleType,
    repository: Path,
    shipping_policy: ShippingPolicy,
    capsys: pytest.CaptureFixture[str],
) -> None:
    go_project(repository)
    config = installer.gate_config(repository)
    assert config["packages"] == []
    assert roles(config) == [
        "secrets-files",
        "secrets-history",
        "security",
        "vulnerabilities",
    ]
    assert "--lockfile=go.mod" in config["shared"][-1]["command"]
    config["shipping"] = shipping_policy
    (repository / "hard-eng.gates.json").write_text(json.dumps(config))
    installer.install(repository)
    lines = capsys.readouterr().out.splitlines()
    assert (
        "Basic mode for Go: rules, skills, secret scans and security scan installed; "
        "no built-in checks for Go." in lines
    )
    assert "Gap: No built-in checks for Go" in lines
    assert (
        'File it, without asking: python3 .hooks/hard-eng.py gap-issue "No built-in checks for Go"'
        in lines
    )
    for name in (".hooks/hard-eng.py", ".git/hooks/pre-push", "AGENTS.md"):
        assert (repository / name).exists()
    installed = parse_config((repository / "hard-eng.gates.json").read_text())
    assert installed["packages"] == []
    validate_required_checks(repository, installed)
    workflow = (repository / ".github/workflows/hard-eng.yml").read_text()
    assert "EXTRA_SDK_TOOLS: ''" in workflow or 'EXTRA_SDK_TOOLS: ""' in workflow
    assert "|| 'uv@latest python@3.12 node@latest'" in workflow
    assert "dart@" not in workflow and "flutter@" not in workflow
    assert "poetry@" not in workflow and "pnpm@" not in workflow


def test_basic_mode_check_impact_and_mutation_run_without_packages(
    installer: ModuleType,
    repository: Path,
    shipping_policy: ShippingPolicy,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    go_project(repository)
    config = installer.gate_config(repository)
    config["shipping"] = shipping_policy
    (repository / "hard-eng.gates.json").write_text(json.dumps(config))
    installer.install(repository)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (repository / name).write_text((SOURCE / name).read_text())
    config["shared"] = config["shared"][:2]
    scanner = tmp_path / "bin/gitleaks"
    scanner.parent.mkdir()
    scanner.write_text(
        f"#!{sys.executable}\nimport sys\nfrom pathlib import Path\n"
        "report = Path(sys.argv[sys.argv.index('--report-path') + 1])\n"
        "report.parent.mkdir(parents=True, exist_ok=True)\n"
        'report.write_text(\'{"version":"2.1.0","runs":[{"results":[],"tool":'
        '{"driver":{"name":"gitleaks","rules":[{"id":"fixture"}]}}}]}\')\n'
    )
    scanner.chmod(0o755)
    monkeypatch.setenv("PATH", f"{scanner.parent}{os.pathsep}{os.environ['PATH']}")
    (repository / "hard-eng.gates.json").write_text(json.dumps(config))
    base = commit(repository, "stub gates")
    (repository / "main.go").write_text("package main\n\nfunc main() { _ = 1 }\n")
    runner = load_module("basic_runner", SOURCE / ".hooks/hard-eng.py")
    runner.__dict__["ROOT"] = repository
    monkeypatch.setattr(runner, "provision_tools", no_provisioning)
    capsys.readouterr()
    for quick in (True, False):
        assert runner.check(base=base, quick=quick, verify_plan=False) == 0
    assert "PASS secrets-files" in capsys.readouterr().out
    assert runner.impact(base) == 0
    assert capsys.readouterr().out == (
        "docs_only=false\ntools=uv@latest python@3.12 node@latest\n"
    )
    assert mutation.report(repository, base, None, lambda *_arguments: set()) == 0
    assert "Mutation testing" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("files", "label"),
    [
        ({"go.mod": "module x\n"}, "Go"),
        ({"Cargo.toml": ""}, "Rust"),
        ({"pom.xml": ""}, "Java/Kotlin"),
        ({"build.gradle.kts": ""}, "Java/Kotlin"),
        ({"Gemfile": ""}, "Ruby"),
        ({"composer.json": "{}"}, "PHP"),
        ({"App.csproj": ""}, ".NET"),
        ({"Package.swift": ""}, "Swift"),
        ({"CMakeLists.txt": ""}, "C/C++"),
        ({"main.go": "package main\n"}, "Go"),
        ({"deploy.sh": "echo hi\n"}, "this language"),
    ],
)
def test_language_label_comes_from_manifest_or_extension(
    tmp_path: Path, files: dict[str, str], label: str
) -> None:
    init(tmp_path / "repository")
    root = tmp_path / "repository"
    for name, content in files.items():
        (root / name).write_text(content)
    assert language_label(root, repository_files(root)) == label


def test_vulnerability_scan_is_omitted_without_an_understood_lockfile(
    installer: ModuleType, repository: Path
) -> None:
    (repository / "go.mod").write_text("module example\n\ngo 1.22\n")
    (repository / "go.sum").write_text("")
    (repository / "main.go").write_text("package main\n")
    assert roles(installer.gate_config(repository)) == [
        "secrets-files",
        "secrets-history",
        "security",
    ]


@pytest.mark.parametrize("files", [{}, {"README.md": "# Notes\n", "LICENSE": "MIT\n"}])
def test_repository_without_project_files_still_asks_for_a_project_type(
    installer: ModuleType, tmp_path: Path, files: dict[str, str]
) -> None:
    init(tmp_path / "repository")
    root = tmp_path / "repository"
    for name, content in files.items():
        (root / name).write_text(content)
    with pytest.raises(ValueError, match="ask the user which type to create"):
        installer.gate_config(root)
