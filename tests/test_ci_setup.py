"""Generated job deadlines honor the consumer's existing shipping budget."""

import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import tool_setup
import yaml
from ci_setup import (
    configure_ci,
    impact_tools,
    migrate_pnpm_bootstrap,
    workflow_tools,
)
from conftest import commit, load_module, use_installed_mise
from gate_config import GateConfig, Group, parse_config
from shipping import ShippingError, ShippingPolicy

SOURCE = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "manifest,pinned",
    [
        ({}, False),
        ({"packageManager": "pnpm@12.4.1+sha512.abc"}, True),
        ({"devEngines": {"packageManager": {"name": "pnpm", "version": "^12"}}}, True),
    ],
)
def test_pnpm_bootstrap_uses_root_declaration(
    tmp_path: Path,
    manifest: dict[str, object],
    pinned: bool,
) -> None:
    original = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    assert migrate_pnpm_bootstrap(tmp_path, original) == original
    (tmp_path / "package.json").write_text(json.dumps(manifest))
    migrated = migrate_pnpm_bootstrap(tmp_path, original)
    job = yaml.safe_load(migrated)["jobs"]["hard-eng"]
    bootstrap = next(
        step["with"] for step in job["steps"] if "pnpm/setup@" in step.get("uses", "")
    )
    assert bootstrap.get("version") == (None if pinned else "latest")
    assert bootstrap["install"] is False
    assert migrate_pnpm_bootstrap(tmp_path, migrated) == migrated
    custom = original.replace("version: latest", "version: 11.24.0")
    assert migrate_pnpm_bootstrap(tmp_path, custom) == custom
    custom = original.replace(
        "          install: false\n",
        "          install: false\n          working-directory: web\n",
    )
    assert migrate_pnpm_bootstrap(tmp_path, custom) == custom


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("location", ["local", "runner", "configured"])
def test_native_tool_bootstrap_preserves_ci_sdk_executables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrapped: bool, location: str
) -> None:
    use_installed_mise(tmp_path, monkeypatch)
    for name in (
        "RUNNER_TEMP",
        "MISE_DATA_DIR",
        "MISE_CACHE_DIR",
        "MISE_STATE_DIR",
        "PNPM_CONFIG_STORE_DIR",
        "PNPM_CONFIG_CACHE_DIR",
        "NPM_CONFIG_CACHE",
    ):
        monkeypatch.delenv(name, raising=False)
    storage = tmp_path / "hard-eng-tools"
    if location != "local":
        monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
        storage = tmp_path / "runner/hard-eng-tools"
    data = storage / "mise/data"
    if location == "configured":
        data = tmp_path / "configured/data"
        monkeypatch.setenv("MISE_DATA_DIR", str(data))
        monkeypatch.setenv("PNPM_CONFIG_STORE_DIR", str(tmp_path / "configured/store"))
    sdk, scanner = tmp_path / "sdk", data / "installs/gitleaks/test/bin"
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
        captured[:] = command
        environment = _kwargs["env"]
        assert isinstance(environment, dict)
        assert environment["MISE_DATA_DIR"] == str(data)
        assert environment["PNPM_CONFIG_STORE_DIR"] == str(
            tmp_path / "configured/store"
            if location == "configured"
            else storage / "pnpm/store"
        )
        assert environment["PNPM_CONFIG_CACHE_DIR"] == str(storage / "pnpm/cache")
        return subprocess.CompletedProcess(
            command, 0, json.dumps({"PATH": str(scanner)}), ""
        )

    monkeypatch.setattr(subprocess, "run", native_environment)
    command = ["node", "scan.mjs", "gitleaks"] if wrapped else ["gitleaks"]
    tool_setup.provision_tools(
        tmp_path,
        [{"path": ".", "checks": [{"name": "secrets", "command": command}]}],
        30,
    )
    assert shutil.which("uv") == str(sdk / "uv")
    assert shutil.which("gitleaks") == str(scanner / "gitleaks")
    assert captured[0] == "env"
    assert not any(argument.startswith("MISE_DATA_DIR=") for argument in captured)
    assert captured[captured.index("mise") :] == [
        "mise",
        "--no-config",
        "env",
        "--json",
        "aqua:gitleaks/gitleaks@latest",
    ]


def test_managed_python_scanner_provisions_project_local_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    use_installed_mise(tmp_path, monkeypatch)
    """A cold existing job receives uv before its managed scanner runs."""
    storage = tmp_path / "hard-eng-tools"
    uv_bin = storage / "mise/data/installs/uv/latest/bin"
    commands: list[list[str]] = []
    monkeypatch.setattr(tool_setup.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("MISE_DATA_DIR", str(storage / "mise/data"))
    monkeypatch.setenv("MISE_CACHE_DIR", str(storage / "mise/cache"))
    monkeypatch.setenv("MISE_STATE_DIR", str(storage / "mise/state"))

    def native_environment(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[-3:] == ["env", "--json", "uv@latest"]:
            uv_bin.mkdir(parents=True)
            binary = uv_bin / "uv"
            binary.write_text("#!/bin/sh\nexit 0\n")
            binary.chmod(0o755)
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"PATH": str(uv_bin)}), ""
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", native_environment)
    tool_setup.provision_tools(
        tmp_path,
        [
            {
                "path": ".",
                "checks": [{"name": "security", "command": ["semgrep", "scan", "."]}],
            }
        ],
        30,
    )
    assert commands[0][-2:] == ["install", "uv@latest"]
    assert commands[1][-3:] == ["env", "--json", "uv@latest"]
    assert shutil.which("uv") == str(uv_bin / "uv")


@pytest.mark.parametrize("seconds,minutes", [(600, 10), (601, 11), (60, 1)])
def test_generated_ci_timeout(
    tmp_path: Path, seconds: int | None, minutes: int
) -> None:
    config: GateConfig = {"packages": [], "shared": []}
    (tmp_path / "package.json").write_text('{"packageManager":"pnpm@12.4.1"}')
    if seconds is not None:
        config["shipping"] = {
            "base": "main",
            "checks": ["hard-eng"],
            "ui_paths": [],
            "ci_seconds": seconds,
            "pre_push_seconds": 600,
            "delivery": [],
        }
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    workflow = changes[".github/workflows/hard-eng.yml"]
    assert "          version: latest\n" not in workflow
    assert yaml.safe_load(workflow)["jobs"]["hard-eng"]["timeout-minutes"] == minutes
    assert '--base "$BASE_SHA"' in workflow
    steps = yaml.safe_load(workflow)["jobs"]["hard-eng"]["steps"]
    assert not any("actions/cache@" in step.get("uses", "") for step in steps)
    checks = next(step for step in steps if step.get("name") == "Run required checks")
    environment = yaml.safe_load(workflow)["jobs"]["hard-eng"]["env"]
    impact = next(step for step in steps if step.get("id") == "impact")
    assert "MISE_DATA_DIR=$RUNNER_TEMP/hard-eng-tools/mise/data" in impact["run"]
    assert environment["EXTRA_SDK_TOOLS"] == ""
    scan = next(step for step in steps if "secret scan" in step.get("name", ""))
    assert "if" not in yaml.safe_load(workflow)["jobs"]["hard-eng"]
    assert {checks["if"], scan["if"]} == {
        "steps.impact.outputs.docs_only != 'true'",
        "steps.impact.outputs.docs_only == 'true'",
    }
    assert (
        "install " in checks["run"]
        and "MISE_FETCH_REMOTE_VERSIONS_CACHE=1h" in checks["run"]
    )


def test_existing_hard_eng_workflow_is_preserved(tmp_path: Path) -> None:
    name = "hard-eng.yml"
    path = tmp_path / ".github/workflows" / name
    path.parent.mkdir(parents=True)
    content = "# Project-owned workflow\njobs:\n  custom:\n    timeout-minutes: 17\n"
    path.write_text(content)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes == {}
    assert path.read_text() == content


def test_maintenance_only_workflow_receives_a_quality_owner(
    tmp_path: Path, shipping_policy: ShippingPolicy
) -> None:
    path = tmp_path / ".github/workflows/nightly.yml"
    path.parent.mkdir(parents=True)
    content = """on:
  schedule:
    - cron: '0 4 * * *'
  workflow_dispatch:
jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - run: echo cleanup
"""
    path.write_text(content)
    config = parse_config(
        json.dumps(
            {
                "packages": [],
                "shared": [],
                "shipping": {**shipping_policy, "checks": ["quality"]},
            }
        )
    )
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}

    configure_ci(tmp_path, SOURCE, config, changes)

    assert path.read_text() == content
    assert ".github/workflows/hard-eng.yml" in changes
    assert config["shipping"]["checks"] == ["quality", "hard-eng"]


@pytest.mark.parametrize(
    "content",
    [
        "on: pull_request\njobs:\n  quality:\n    runs-on: ubuntu-latest\n",
        "on: [\n",
        """on: workflow_dispatch
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - run: python3 .hooks/hard-eng.py check --base \"$BASE_SHA\"
""",
    ],
)
def test_existing_quality_or_invalid_workflow_is_preserved(
    tmp_path: Path, shipping_policy: ShippingPolicy, content: str
) -> None:
    path = tmp_path / ".github/workflows/quality.yml"
    path.parent.mkdir(parents=True)
    path.write_text(content)
    config = parse_config(
        json.dumps({"packages": [], "shared": [], "shipping": shipping_policy})
    )
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}

    configure_ci(tmp_path, SOURCE, config, changes)

    assert changes == {}
    assert path.read_text() == content


@pytest.mark.parametrize("name", ["quality.yml", "hard-eng.yml"])
def test_integration_reminder_stops_once_existing_ci_runs_the_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    path = tmp_path / ".github/workflows" / name
    path.parent.mkdir(parents=True)
    job = "on: pull_request\njobs:\n  quality:\n    steps:\n      - run: {}\n"
    path.write_text(job.format("make test"))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    pending = (
        "Existing CI retained"
        if name == "quality.yml"
        else "Docs-only CI steps not added"
    )
    assert pending in capsys.readouterr().err
    path.write_text(job.format("python3 .hooks/hard-eng.py check --base main"))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    assert "Existing CI retained" not in capsys.readouterr().err
    path.write_text(job.format("python3 .hooks/hard-eng.py check"))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    assert "runs Hard Eng without --base" in capsys.readouterr().err
    path.write_text(
        job.format("python3 .hooks/hard-eng.py check --base main")
        + "      - run: python3 .hooks/hard-eng.py check\n"
    )
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    assert "runs Hard Eng without --base" in capsys.readouterr().err
    path.write_text(job.format("python3 .hooks/hard-eng.py check --base main"))
    other = path.with_name("other.yml")
    other.write_text(job.format("python3 .hooks/hard-eng.py check"))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    assert "other.yml runs Hard Eng without --base" in capsys.readouterr().err
    other.write_text(other.read_text().replace("pull_request", "workflow_dispatch"))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})
    assert "runs Hard Eng without --base" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "ci,event,base,rejected",
    [
        ("true", "push", None, True),
        ("true", "pull_request", "", True),
        ("true", "pull_request_target", "  ", True),
        ("true", "push", "HEAD", False),
        ("true", "workflow_dispatch", None, False),
        ("true", "schedule", None, False),
        ("", "push", None, False),
    ],
)
def test_ci_comparison_is_required_before_project_execution(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    ci: str,
    event: str,
    base: str | None,
    rejected: bool,
) -> None:
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [
                    {
                        "name": "proof",
                        "command": [sys.executable, "-c", "open('ran', 'w').close()"],
                    }
                ],
            }
        )
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
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
        cwd=tmp_path,
        check=True,
    )
    monkeypatch.setenv("GITHUB_ACTIONS", ci)
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    if rejected:
        with pytest.raises(ValueError, match="require --base"):
            runner.check(base=base)
        with pytest.raises(ValueError, match="require --base"):
            runner.impact(base or "")
        assert not (tmp_path / "ran").exists()
    else:
        assert runner.impact(base or "") == 0
        assert runner.check(base=base) == 0
        assert (tmp_path / "ran").is_file()


def test_unconfigured_maintenance_project_does_not_inherit_source_ci_budget(
    tmp_path: Path,
) -> None:
    path = tmp_path / ".github/workflows/nightly.yml"
    path.parent.mkdir(parents=True)
    path.write_text("on: workflow_dispatch\njobs: {}\n")
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": []})
    )
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert not changes


def test_existing_tool_bootstrap_migrates_with_customizations(tmp_path: Path) -> None:
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    old = """# Keep the project note
jobs:
  hard-eng:
    timeout-minutes: 12
    steps:
      - name: Project checks
        run: >-
          pnpm dlx --allow-build=@jdxcode/mise
          --package=@jdxcode/mise@latest mise --no-config exec
          uv@latest python@3.12 node@latest flutter@latest pnpm@11.18.0
          -- uv run --no-project --with pyyaml python .hooks/hard-eng.py check --base "$BASE_SHA"
"""
    path.write_text(old)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    migrated = changes[str(path.relative_to(tmp_path))]
    job = yaml.safe_load(migrated)["jobs"]["hard-eng"]
    assert migrated.startswith("# Keep the project note\n")
    assert job["timeout-minutes"] == 12
    step = job["steps"][0]
    assert step["name"] == "Project checks"
    commands = step["run"].splitlines()
    assert len(commands) == 2
    assert " install uv@latest" in commands[0] and commands[0].endswith("&&")
    assert commands[1].startswith("MISE_FETCH_REMOTE_VERSIONS_CACHE=1h ")
    assert (
        " exec uv@latest python@3.12 node@latest flutter@latest pnpm@11.18.0"
        in commands[1]
    )
    assert "flutter@latest pnpm@11.18.0" in commands[0]
    assert all("dlx --config.ignore-scripts=false --allow-build" in c for c in commands)
    path.write_text(migrated)
    changes.clear()
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert not changes


@pytest.mark.parametrize("named", [False, True])
def test_known_action_pins_migrate_without_replacing_custom_workflow(
    tmp_path: Path,
    named: bool,
) -> None:
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    old = (
        (SOURCE / ".github/workflows/hard-eng.yml")
        .read_text()
        .replace(
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5",
        )
        .replace(
            "703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0",
            "c9883cc79df532ad1a7b81bf9ab944ceb090d65c # v2.0.0",
        )
    )
    custom = "# Project-owned note\n" + old.replace(
        "timeout-minutes: 5", "timeout-minutes: 10"
    )
    if named:
        custom = custom.replace("- uses:", "- name: Configure tool\n        uses:")
    path.write_text(custom)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    expected = "# Project-owned note\n" + (
        SOURCE / ".github/workflows/hard-eng.yml"
    ).read_text().replace("timeout-minutes: 5", "timeout-minutes: 10")
    if named:
        expected = expected.replace("- uses:", "- name: Configure tool\n        uses:")
    assert changes[str(path.relative_to(tmp_path))] == expected
    path.write_text(expected)
    repeated: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, repeated)
    assert repeated == {}
    path.write_text(
        custom.replace("fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09", "a" * 40).replace(
            "c9883cc79df532ad1a7b81bf9ab944ceb090d65c", "b" * 40
        )
    )
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, repeated)
    assert repeated == {}


def test_invalid_shipping_budget_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "hard-eng.gates.json").write_text('{"shipping": {"ci_seconds": 0}}')
    with pytest.raises(ShippingError):
        configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})


def generated_tools(
    root: Path, config: GateConfig, selected: list[Group] | None = None
) -> tuple[str, list[str], list[str]]:
    """Run setup and return the workflow plus its mise install and exec tool lists."""
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, config, changes)
    workflow = changes[".github/workflows/hard-eng.yml"]
    job = yaml.safe_load(workflow)["jobs"]["hard-eng"]
    checks = job["steps"][-1]
    fallback = checks["env"]["SDK_TOOLS"].split(" || '", 1)[1].split("'", 1)[0]
    output = subprocess.check_output(
        ["bash", "-c", 'pnpm() { printf "%s\\n" "$*"; }\n' + checks["run"]],
        env={
            **os.environ,
            "SDK_TOOLS": " ".join(impact_tools(root, selected))
            if selected is not None
            else fallback,
            "EXTRA_SDK_TOOLS": job.get("env", {}).get("EXTRA_SDK_TOOLS", ""),
        },
        text=True,
    )
    install, execute = map(shlex.split, output.splitlines())
    return (
        workflow,
        install[install.index("install") + 1 :],
        execute[execute.index("exec") + 1 : execute.index("--")],
    )


@pytest.mark.parametrize("manager", ["dart", "flutter"])
def test_dart_workflow_uses_packaged_scanner_without_rust(
    tmp_path: Path, manager: str, shipping_policy: ShippingPolicy
) -> None:
    dependencies: dict[str, dict[str, str]] = (
        {"flutter": {"sdk": "flutter"}} if manager == "flutter" else {}
    )
    (tmp_path / "pubspec.yaml").write_text(
        yaml.safe_dump({"name": "fixture", "dependencies": dependencies})
    )
    config = parse_config(
        json.dumps(
            {
                "packages": [
                    {
                        "path": ".",
                        "language": "dart",
                        "checks": [
                            {"name": "dependencies", "command": [manager, "pub", "get"]}
                        ],
                    }
                ],
                "shared": [],
                "shipping": shipping_policy,
            }
        )
    )
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    workflow, installed, executed = generated_tools(tmp_path, config)
    tools = ["uv@latest", "python@3.12", "node@latest", manager + "@latest"]
    assert installed == executed == tools
    assert "rust@latest" not in workflow


def test_workflow_runs_once_per_change(tmp_path: Path) -> None:
    """A PR must not run the same check twice; only default-branch pushes run."""
    template = yaml.safe_load((SOURCE / ".github/workflows/hard-eng.yml").read_text())
    triggers = template.get("on", template.get(True))
    assert "pull_request" in triggers
    assert triggers["push"] == {"branches": ["main"]}
    config: GateConfig = {
        "packages": [],
        "shared": [],
        "shipping": {
            "base": "trunk",
            "checks": ["hard-eng"],
            "ui_paths": [],
            "ci_seconds": 120,
            "pre_push_seconds": 120,
            "delivery": [],
        },
    }
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    generated = yaml.safe_load(changes[".github/workflows/hard-eng.yml"])
    assert generated.get("on", generated.get(True))["push"] == {"branches": ["trunk"]}


def test_workflow_call_base_input_feeds_check() -> None:
    """A project's deploy workflow can call Hard Eng and pass its own base."""
    workflow = yaml.safe_load((SOURCE / ".github/workflows/hard-eng.yml").read_text())
    triggers = workflow.get("on", workflow.get(True))
    assert "base_sha" in triggers["workflow_call"]["inputs"]
    steps = workflow["jobs"]["hard-eng"]["steps"]
    checks = next(step for step in steps if step.get("name") == "Run required checks")
    assert checks["env"]["BASE_SHA"].startswith("${{ inputs.base_sha ||")
    assert "github.event.pull_request.base.sha" in checks["env"]["BASE_SHA"]
    assert "github.event.before" in checks["env"]["BASE_SHA"]


OLD_TRIGGERS = (
    "on:\n  push:\n    branches-ignore:\n      - 'feature/**'\n  pull_request:\n"
)
OLD_BASE = "BASE_SHA: ${{ github.event.pull_request.base.sha || github.event.before }}"


def test_generated_triggers_migrate_with_customizations(tmp_path: Path) -> None:
    """Installed copies move to single runs plus workflow_call; custom triggers stay."""
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    new_triggers = template[
        template.index("on:\n") : template.index("\n\npermissions:") + 1
    ]
    new_base = next(line for line in template.splitlines() if "BASE_SHA:" in line)
    old = "# Project-owned note\n" + template.replace(
        new_triggers, OLD_TRIGGERS, 1
    ).replace(new_base.strip(), OLD_BASE, 1).replace(
        "timeout-minutes: 5", "timeout-minutes: 10"
    )
    assert "pull_request:\n\npermissions:" in old, "installed shape"
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    path.write_text(old)
    config: GateConfig = {"packages": [], "shared": []}
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    assert changes == {}, "no shipping base to migrate towards"
    config["shipping"] = {
        "base": "trunk",
        "checks": ["hard-eng"],
        "ui_paths": [],
        "ci_seconds": 120,
        "pre_push_seconds": 120,
        "delivery": [],
    }
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    configure_ci(tmp_path, SOURCE, config, changes)
    migrated = changes[str(path.relative_to(tmp_path))]
    assert migrated == "# Project-owned note\n" + template.replace(
        "      - main\n", "      - trunk\n", 1
    ).replace("timeout-minutes: 5", "timeout-minutes: 10")
    path.write_text(migrated)
    changes.clear()
    configure_ci(tmp_path, SOURCE, config, changes)
    assert changes == {}
    custom = old.replace(
        "branches-ignore:\n      - 'feature/**'", "branches:\n      - develop"
    )
    path.write_text(custom)
    configure_ci(tmp_path, SOURCE, config, changes)
    assert changes == {}


def test_old_workflow_gains_docs_only_steps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Installed workflows skip tool setup for docs-only changes after an update."""
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    impact = template[
        template.index("      - name: Find whether") : template.index(
            "      - uses: pnpm/setup@"
        )
    ]
    scan = template[
        template.index("      - name: Run the secret") : template.index(
            "      - name: Run required checks"
        )
    ]
    old = template.replace(impact, "").replace(scan, "")
    old = old.replace("        if: steps.impact.outputs.docs_only != 'true'\n", "")
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    path.write_text(old)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes[".github/workflows/hard-eng.yml"] == template
    path.write_text(template)
    changes.clear()
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes == {}
    assert "Docs-only CI steps not added" not in capsys.readouterr().err
    path.write_text(old.replace("Run required checks", "Run project checks"))
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes == {}
    assert "Docs-only CI steps not added" in capsys.readouterr().err


@pytest.mark.parametrize(
    "changed,packages,expected",
    [
        ("README.md", ["."], "true"),
        ("app.py", ["."], "false"),
        ("README.md", [], "false"),
    ],
)
def test_impact_reports_docs_only_before_tools(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    changed: str,
    packages: list[str],
    expected: str,
) -> None:
    groups: list[Group] = [{"path": path, "checks": []} for path in packages]
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": groups, "shared": []})
    )
    commit(repository, "configure")
    (repository / changed).write_text("change\n")
    module = load_module("impact_runner", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = repository
    assert module.impact("HEAD") == 0
    assert capsys.readouterr().out == (
        f"docs_only={expected}\ntools=uv@latest python@3.12 node@latest\n"
    )


def test_impact_provisions_selected_sdks_without_yaml_and_falls_back_to_all(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    groups: list[Group] = [
        {"path": "web", "language": "javascript", "depends_on": [], "checks": []},
        {
            "path": "mobile",
            "language": "dart",
            "depends_on": [],
            "checks": [{"name": "dependencies", "command": ["flutter", "pub", "get"]}],
        },
        {
            "path": "function",
            "language": "dart",
            "depends_on": [],
            "checks": [{"name": "dependencies", "command": ["dart", "pub", "get"]}],
        },
    ]
    for group in groups:
        (repository / group["path"]).mkdir()
    (repository / "web/package.json").write_text('{"packageManager":"pnpm@12.4.1"}')
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": groups, "shared": []})
    )
    commit(repository, "packages")
    (repository / "web/app.ts").write_text("export const value = 1;\n")
    module = load_module("selected_impact_runner", SOURCE / ".hooks/hard-eng.py")
    module.__dict__["ROOT"] = repository
    assert module.impact("HEAD") == 0
    assert (
        "tools=uv@latest python@3.12 node@latest pnpm@12.4.1\n"
        in capsys.readouterr().out
    )
    assert module.impact("missing-base") == 0
    assert (
        "tools=uv@latest python@3.12 node@latest pnpm@12.4.1 flutter@latest\n"
        in capsys.readouterr().out
    )
    code = (
        "import json,sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r}); "
        "from ci_setup import impact_tools; "
        "print(impact_tools(Path(sys.argv[1]), json.loads(sys.argv[2])))"
    )
    output = subprocess.check_output(
        [sys.executable, "-S", "-c", code, str(repository), json.dumps(groups)],
        text=True,
    )
    assert "flutter@latest" in output
    support: Group = {"path": "function", "checks": groups[2]["checks"]}
    assert impact_tools(repository, [support])[-1] == "dart@latest"
    (repository / "web/package.json").write_text(
        '{"packageManager":"pnpm@12.4.1;echo injected"}'
    )
    with pytest.raises(ValueError, match="valid pnpm"):
        impact_tools(repository, groups)


@pytest.mark.parametrize(
    ("declared", "own_lock", "own_install", "expected"),
    [
        (None, False, False, ["pnpm@11.24.0"]),
        ("pnpm@12.4.1", True, True, ["pnpm@11.24.0", "pnpm@12.4.1"]),
        (None, True, True, ["pnpm@11.24.0", "pnpm@latest"]),
        (None, False, True, ["pnpm@11.24.0", "pnpm@latest"]),
    ],
)
def test_workspace_sdks_reuse_the_dependency_install_owners_pin(
    tmp_path: Path,
    declared: str | None,
    own_lock: bool,
    own_install: bool,
    expected: list[str],
) -> None:
    (tmp_path / "package.json").write_text('{"packageManager":"pnpm@11.24.0"}')
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9.0\n")
    (tmp_path / "pnpm-workspace.yaml").write_text("packages: [packages/*]\n")
    member = tmp_path / "packages/member"
    member.mkdir(parents=True)
    (member / "package.json").write_text(
        json.dumps({"packageManager": declared} if declared else {})
    )
    if own_lock:
        (member / "pnpm-lock.yaml").write_text("lockfileVersion: 9.0\n")
    install = {
        "name": "dependencies",
        "role": "lockfiles",
        "command": ["pnpm", "install", "--frozen-lockfile"],
    }
    groups: list[Group] = [
        {"path": ".", "language": "javascript", "checks": [install]},
        {
            "path": "packages/member",
            "language": "javascript",
            "checks": [install] if own_install else [],
        },
    ]
    config: GateConfig = {"packages": groups, "shared": []}
    assert impact_tools(tmp_path, groups)[3:] == expected
    assert workflow_tools(tmp_path, config)[3:] == expected
    inherited = impact_tools(tmp_path, [{"path": ".", "checks": [install]}, groups[1]])
    assert inherited[3:] == expected[-1:]


def flutter_app_config(root: Path) -> GateConfig:
    app = root / "app"
    app.mkdir()
    (app / "pubspec.yaml").write_text(
        yaml.safe_dump({"name": "app", "dependencies": {"flutter": {"sdk": "flutter"}}})
    )
    return {
        "packages": [
            {
                "path": "app",
                "language": "dart",
                "checks": [
                    {"name": "dependencies", "command": ["flutter", "pub", "get"]}
                ],
            }
        ],
        "shared": [],
    }


def test_existing_workflow_gains_sdk_for_package_added_later(tmp_path: Path) -> None:
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    old = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    start, end = old.index("    env:\n"), old.index("    steps:\n")
    old = old[:start] + old[end:]
    old = old.replace(
        "          SDK_TOOLS: ${{ steps.impact.outputs.tools || 'uv@latest python@3.12 node@latest' }}\n",
        "",
    ).replace('          read -r -a tools <<< "$SDK_TOOLS ${EXTRA_SDK_TOOLS:-}"\n', "")
    old = old.replace(
        '"${tools[@]}"', "uv@latest python@3.12 pnpm@12.4.1 dart@latest rust@latest"
    )
    old = old.replace(
        "      - uses: pnpm/setup@",
        "      - name: Cache native tool downloads\n"
        "        uses: actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0\n"
        "        with:\n"
        "          path: ${{ runner.temp }}/hard-eng-tools\n"
        "          key: ${{ runner.os }}-${{ runner.arch }}-hard-eng-tools-${{ hashFiles('hard-eng.gates.json') }}\n"
        "          restore-keys: ${{ runner.os }}-${{ runner.arch }}-hard-eng-tools-\n"
        "      - uses: pnpm/setup@",
        1,
    )
    before, checks = old.split("      - name: Run required checks\n", 1)
    checks = checks.replace(
        "        run: |\n", "        shell: bash\n        run: |\n", 1
    )
    old = before + "      - name: Run required checks\n" + checks
    path.write_text(old)
    config = flutter_app_config(tmp_path)
    workflow, installed, executed = generated_tools(tmp_path, config)
    tools = [
        "uv@latest",
        "python@3.12",
        "node@latest",
        "flutter@latest",
        "pnpm@12.4.1",
        "rust@latest",
    ]
    assert installed == executed == tools
    assert "actions/cache@" not in workflow
    path.write_text(workflow)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    assert not changes
    (tmp_path / "package.json").write_text('{"packageManager":"pnpm@12.4.1"}')
    (tmp_path / "pnpm-lock.yaml").touch()
    config["packages"].insert(0, {"path": ".", "language": "javascript", "checks": []})
    path.write_text(old.replace("pnpm@12.4.1", "pnpm@12.4.1 pnpm@latest"))
    workflow, installed, executed = generated_tools(tmp_path, config)
    assert installed == executed
    assert [tool for tool in installed if tool.startswith("pnpm@")] == ["pnpm@12.4.1"]
    assert "          version: latest\n" not in workflow
    assert "actions/cache@" not in workflow
    path.write_text(old.replace("python@3.12", "python@3.11"))
    configure_ci(tmp_path, SOURCE, config, changes)
    assert "python@3.11" in changes[".github/workflows/hard-eng.yml"]
    assert "SDK_TOOLS:" not in changes[".github/workflows/hard-eng.yml"]


def test_custom_flutter_commands_keep_manifest_sdk(
    tmp_path: Path, shipping_policy: ShippingPolicy
) -> None:
    config = parse_config(
        json.dumps({**flutter_app_config(tmp_path), "shipping": shipping_policy})
    )
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    original, _, _ = generated_tools(tmp_path, config)
    config["packages"][0]["checks"] = [
        {"name": "dependencies", "command": ["python3", "prepare_dependencies.py"]},
        {"name": "tests", "command": ["python3", "run_tests.py"]},
    ]
    workflow, installed, executed = generated_tools(
        tmp_path, config, config["packages"]
    )
    assert installed == executed
    assert "flutter@latest" in installed
    assert (
        yaml.safe_load(workflow)["jobs"]["hard-eng"]["env"]["EXTRA_SDK_TOOLS"]
        == "flutter@latest"
    )
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    path.write_text(original)
    migrated, installed, executed = generated_tools(
        tmp_path, config, config["packages"]
    )
    assert installed == executed and "flutter@latest" in installed
    path.write_text(migrated)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    assert not changes


def test_customised_workflow_names_missing_sdk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    content = "jobs:\n  custom:\n    steps:\n      - run: mise exec dart@latest -- make check\n"
    path.write_text(content)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, flutter_app_config(tmp_path), changes)
    assert not changes
    assert "Add flutter@latest to its mise install and exec tool lists." in (
        capsys.readouterr().err
    )


def test_installed_launcher_gains_ignore_scripts_override(tmp_path: Path) -> None:
    """A project's pnpm ignoreScripts must not skip mise's binary download in CI."""
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    installed = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    path.write_text(installed.replace("--config.ignore-scripts=false ", ""))
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    migrated = changes[str(path.relative_to(tmp_path))]
    assert "pnpm dlx --allow-build" not in migrated
    assert migrated.count("pnpm dlx --config.ignore-scripts=false --allow-build") == 4


def test_generated_tool_cache_is_removed_from_existing_workflows(
    tmp_path: Path,
) -> None:
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    setup = "      - uses: pnpm/setup@"
    cache = (
        "      - name: Cache native tool downloads\n"
        "        if: steps.impact.outputs.docs_only != 'true'\n"
        "        uses: actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9 # v6.1.0\n"
        "        with:\n"
        "          path: |\n"
        "            ${{ runner.temp }}/hard-eng-tools/mise/data/installs\n"
        "          key: ${{ runner.os }}-${{ runner.arch }}-hard-eng-tools-v2-all\n"
    )
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    path.write_text(template.replace(setup, cache + setup, 1))
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes[".github/workflows/hard-eng.yml"] == template
    project_cache = cache.replace("hard-eng-tools", "project-tools")
    path.write_text(template.replace(setup, project_cache + setup, 1))
    changes.clear()
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes == {}
