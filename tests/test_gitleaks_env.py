"""The Gitleaks config variables cannot replace the project's config."""

import json
import os
import sys
from pathlib import Path

import pytest
from gate_config import Gate, validate_gate
from gitleaks_entries import ensure_gitleaks, scan
from gitleaks_scan import run_current_files, run_gate_command
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

NAMES = ["GITLEAKS_CONFIG", "GITLEAKS_CONFIG_TOML"]
KEY = "AKIA" + "IOSFODNN7EXAMPLQ\n"
ALLOW_ALL = "[extend]\nuseDefault = true\n[[allowlists]]\npaths = ['''.*''']\n"


def script(directory: Path) -> Path:
    scanner = directory / "gitleaks"
    scanner.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "names = ['GITLEAKS_CONFIG', 'GITLEAKS_CONFIG_TOML']\n"
        "Path(os.environ['SEEN']).write_text(json.dumps([n for n in names if n in os.environ]))\n"
        "if '--report-path' in sys.argv:\n"
        "    report = Path(sys.argv[sys.argv.index('--report-path') + 1])\n"
        "    report.parent.mkdir(parents=True, exist_ok=True)\n"
        '    report.write_text(\'{"version":"2.1.0","runs":[{"results":[],"tool":{"driver":{"name":"gitleaks","rules":[]}}}]}\')\n'
    )
    scanner.chmod(0o755)
    return scanner


@pytest.fixture
def seen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script(bin_dir)
    result = tmp_path / "seen.json"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("SEEN", str(result))
    for name in NAMES:
        monkeypatch.setenv(name, "hidden.toml")
    return result


def test_gitleaks_runs_without_the_config_variables(tmp_path: Path, seen: Path) -> None:
    """HE-NO-SWITCH-OFF: the gate runs Gitleaks with both variables unset, whichever role runs it."""
    repo = project(tmp_path / "p", {"a.txt": "x\n"})
    command = ["gitleaks", "dir", ".", "--report-path", "reports/g.sarif"]
    run_current_files(command, repo, 30, None, sys.stderr)
    assert json.loads(seen.read_text()) == []
    seen.unlink()
    run_gate_command("secrets-history", command, repo, 30, None, sys.stderr)
    assert json.loads(seen.read_text()) == []


def test_the_entry_judge_scans_without_the_config_variables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensure_gitleaks(900)
    (tmp_path / "hidden.toml").write_text(ALLOW_ALL)
    (tmp_path / "live.py").write_text(KEY)
    for name in NAMES:
        monkeypatch.setenv(name, str(tmp_path / "hidden.toml"))
    found = scan(["dir", "."], tmp_path, tmp_path / "r.json", [], 900)
    assert len(found) == 1


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    ("file", "text"),
    [
        (".github/workflows/ci.yml", "env:\n  @N@: hidden.toml\n"),
        ("scripts/scan.sh", "export @N@=hidden.toml\n"),
        ("Makefile", "scan:\n\t@N@=hidden.toml gitleaks dir .\n"),
        (".env", "@N@=hidden.toml\n"),
    ],
)
def test_a_workflow_or_script_that_sets_the_config_variable_is_refused(
    tmp_path: Path, name: str, file: str, text: str
) -> None:
    """HE-NO-SWITCH-OFF: a variable that swaps the Gitleaks config is a switch-off wherever the project sets it."""
    message = refusal(project(tmp_path, {file: text.replace("@N@", name)}))
    assert f"{file}:" in message
    assert name in message


def test_prose_that_names_the_config_variable_passes(tmp_path: Path) -> None:
    validate_whole_project(
        project(
            tmp_path,
            {"README.md": "Set GITLEAKS_CONFIG=x on your machine.\n"},
        )
    )


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    "command",
    [
        ["env", "@N@=x.toml", "gitleaks", "dir", "."],
        ["sh", "-c", "@N@=x.toml gitleaks dir ."],
        ["@N@=x.toml", "gitleaks", "dir", "."],
    ],
)
def test_a_gate_command_that_sets_the_config_variable_fails(
    tmp_path: Path, name: str, command: list[str]
) -> None:
    gate: Gate = {
        "name": "secrets",
        "role": "security",
        "command": [word.replace("@N@", name) for word in command],
    }
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate, tmp_path, set())
