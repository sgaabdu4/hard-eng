"""Generated job deadlines honor the consumer's existing shipping budget."""

import json
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest
import tool_setup
import yaml
from ci_setup import configure_ci
from conftest import commit, load_module
from gate_config import GateConfig, Group, parse_config
from shipping import ShippingError, ShippingPolicy

SOURCE = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("location", ["local", "runner", "configured"])
def test_native_tool_bootstrap_uses_pnpm_and_preserves_ci_sdk_executables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrapped: bool, location: str
) -> None:
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


def test_managed_python_scanner_provisions_project_local_uv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    assert yaml.safe_load(workflow)["jobs"]["hard-eng"]["timeout-minutes"] == minutes
    assert '--base "$BASE_SHA"' in workflow
    steps = yaml.safe_load(workflow)["jobs"]["hard-eng"]["steps"]
    cache = next(
        step for step in steps if step.get("name") == "Cache native tool downloads"
    )
    assert cache["with"]["path"] == "${{ runner.temp }}/hard-eng-tools"
    assert "runner.os" in cache["with"]["key"] and "runner.arch" in cache["with"]["key"]
    assert "hard-eng.gates.json" in cache["with"]["key"]
    checks = next(step for step in steps if step.get("name") == "Run required checks")
    assert checks["env"]["MISE_DATA_DIR"].startswith(cache["with"]["path"] + "/")
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
                "packages": [{"path": ".", "language": "dart", "checks": []}],
                "shared": [],
                "shipping": shipping_policy,
            }
        )
    )
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    workflow = changes[".github/workflows/hard-eng.yml"]
    commands = yaml.safe_load(workflow)["jobs"]["hard-eng"]["steps"][-1][
        "run"
    ].splitlines()
    install = shlex.split(commands[0])
    assert install[install.index("install") + 1 : -1] == [
        "uv@latest",
        "python@3.12",
        "node@latest",
        manager + "@latest",
    ]
    execute = shlex.split(commands[1])
    assert execute[execute.index("exec") + 1 : execute.index("--")] == [
        "uv@latest",
        "python@3.12",
        "node@latest",
        manager + "@latest",
    ]
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


def test_old_workflow_gains_docs_only_steps(tmp_path: Path) -> None:
    """Installed workflows skip tool setup for docs-only changes after an update."""
    template = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
    impact = template[
        template.index("      - name: Find whether") : template.index(
            "      - name: Cache native"
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
    assert capsys.readouterr().out == f"docs_only={expected}\n"
