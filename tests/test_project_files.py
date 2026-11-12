"""A project file that does not parse is named with its format and the parser's own reason."""

import json
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import project_files
import pytest
import yaml
from conftest import SOURCE, gate, init

PARSERS: dict[str, Callable[[str], object]] = {
    "JSON": json.loads,
    "TOML": tomllib.loads,
    "YAML": yaml.safe_load,
}
DART_PUBSPEC = 'name: fixture\nenvironment:\n  sdk: ">=3.0.0 <4.0.0"\n'
PYTHON_PROJECT = (
    '[project]\nname = "x"\nversion = "0.1.0"\nrequires-python = ">=3.12"\n'
)
JAVASCRIPT_MANIFEST = '{"name":"x","scripts":{"test:coverage":"node t.js","test:performance":"node p.js"}}'


def hooks_project(tmp_path: Path, completed_plan: str) -> Path:
    project = tmp_path / "project"
    init(project)
    documents = {
        name: (SOURCE / name).read_text() for name in ("PRODUCT.md", "DESIGN.md")
    }
    for name, text in {"PLAN.md": completed_plan, **documents}.items():
        (project / name).write_text(text)
    shutil.copytree(
        SOURCE / ".hooks",
        project / ".hooks",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    return project


def entry(project: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(project / ".hooks/hard-eng.py"), *arguments],
        cwd=project,
        input="{}",
        capture_output=True,
        text=True,
        check=False,
    )


def reason(kind: str, text: str) -> str:
    with pytest.raises(Exception, match=".") as caught:
        PARSERS[kind](text)
    error = caught.value
    return str(getattr(error, "problem", None) or str(error).splitlines()[0])


def printed(result: subprocess.CompletedProcess[str]) -> str:
    """The one line a failed command prints, with no traceback."""
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    (line,) = result.stderr.splitlines()
    return line


def install(project: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SOURCE / "setup.py"), str(project)],
        capture_output=True,
        text=True,
        check=False,
    )


def named(name: str, kind: str, text: str) -> str:
    return f"{name} is not valid {kind}: {reason(kind, text)}"


def gated_project(installer: ModuleType, project: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        (project / name).parent.mkdir(parents=True, exist_ok=True)
        (project / name).write_text(content)
    config = installer.gate_config(project)
    for package in config["packages"]:
        package["depends_on"] = []
        package["performance_exception"] = "Reviewed fixture: no product workload."
    (project / "hard-eng.gates.json").write_text(json.dumps(config))


def test_a_gates_file_that_does_not_parse_is_named(
    tmp_path: Path, completed_plan: str
) -> None:
    project = hooks_project(tmp_path, completed_plan)
    text = '{\n "packages": []\n "shared": []}'
    (project / "hard-eng.gates.json").write_text(text)
    assert printed(entry(project, "check")) == "Hard Eng: " + named(
        "hard-eng.gates.json", "JSON", text
    )


def test_a_package_manifest_that_does_not_parse_is_named(
    installer: ModuleType, tmp_path: Path, completed_plan: str
) -> None:
    project = hooks_project(tmp_path, completed_plan)
    files = {"bun.lock": "", "uv.lock": ""}
    for package in ("web", "admin"):
        files |= {
            f"{package}/package.json": JAVASCRIPT_MANIFEST,
            f"{package}/bun.lock": "",
            f"{package}/src/app.js": "// fixture\n",
        }
    gated_project(installer, project, files)
    text = '{"name": "x",\n "scripts": {"a": 1 "b": 2}}'
    (project / "admin/package.json").write_text(text)
    assert printed(entry(project, "check")) == "Hard Eng: " + named(
        "admin/package.json", "JSON", text
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('{"version": 1,\n "gates": {}', None),
        ('["version", 1]', "hard-eng.debt.json must hold version 1"),
    ],
)
def test_a_debt_file_that_does_not_parse_or_holds_a_list_is_named(
    tmp_path: Path, completed_plan: str, text: str, expected: str | None
) -> None:
    project = hooks_project(tmp_path, completed_plan)
    (project / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [gate("ok", "pass", role="custom")]})
    )
    (project / "hard-eng.debt.json").write_text(text)
    line = printed(entry(project, "check"))
    assert line.startswith(
        "Hard Eng: " + (expected or named("hard-eng.debt.json", "JSON", text))
    )


def test_a_pubspec_that_does_not_parse_is_named_without_a_traceback(
    installer: ModuleType, tmp_path: Path, completed_plan: str
) -> None:
    project = hooks_project(tmp_path, completed_plan)
    files = {"pubspec.yaml": DART_PUBSPEC, "lib/app.dart": "// fixture\n"}
    gated_project(installer, project, files | {"bun.lock": "", "uv.lock": ""})
    text = "name: [fixture\n"
    (project / "pubspec.yaml").write_text(text)
    expected = f"pubspec.yaml is not valid YAML: {reason('YAML', text)}"
    assert expected in printed(entry(project, "check"))
    started = entry(project, "session", "claude")
    assert started.returncode == 0
    assert "Traceback" not in started.stderr
    assert expected in json.loads(started.stdout)["systemMessage"]


@pytest.mark.parametrize(
    ("name", "kind", "text"),
    [
        (".claude/settings.json", "JSON", '{"outputStyle": "Plain STE",}'),
        (".codex/config.toml", "TOML", "[features\n"),
        ("l10n.yaml", "YAML", "arb-dir: [lib/l10n\n"),
    ],
)
def test_setup_names_a_project_file_that_does_not_parse(
    tmp_path: Path, name: str, kind: str, text: str
) -> None:
    project = tmp_path / "project"
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "bun.lock").write_text('{"lockfileVersion": 1}\n')
    if kind == "YAML":
        (project / "pubspec.yaml").write_text(DART_PUBSPEC)
        (project / "lib").mkdir()
        (project / "lib/app.dart").write_text("// fixture\n")
        (project / "uv.lock").touch()
    else:
        (project / "package.json").write_text('{"private":true}')
    (project / name).parent.mkdir(exist_ok=True)
    (project / name).write_text(text)
    assert printed(install(project)).startswith(named(name, kind, text))


def test_a_setup_rerun_names_a_python_project_file_that_does_not_parse(
    installer: ModuleType, tmp_path: Path, completed_plan: str
) -> None:
    project = hooks_project(tmp_path, completed_plan)
    files = {"pyproject.toml": PYTHON_PROJECT, "src/x/__init__.py": ""}
    gated_project(installer, project, files | {"uv.lock": "", "bun.lock": ""})
    text = '[project\nname = "x"\n'
    (project / "pyproject.toml").write_text(text)
    assert printed(install(project)).startswith(named("pyproject.toml", "TOML", text))


def test_background_work_gives_its_answer_or_raises_its_error() -> None:
    def broken() -> int:
        raise OSError("no answer")

    assert project_files.background(lambda: 7, (OSError,))() == 7
    waiting = project_files.background(broken, (OSError,))
    with pytest.raises(OSError, match="no answer"):
        waiting()


def test_a_line_is_told_one_time_while_a_check_keeps_its_listings(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with project_files.keeping("listings"):
        project_files.tell_once("note\nmore\n")
        project_files.tell_once("note\nother\n")
    project_files.tell_once("note\nnote\n")
    assert capsys.readouterr().err == "note\nmore\nother\nnote\nnote\n"
