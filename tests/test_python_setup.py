"""Python projects get the import contract, parallel tests and typing checks they need."""

import json
import re
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import Gate, GateConfig, Group, parse_config
from python_setup import (
    import_configuration,
    import_contract_gap,
    leave_out_children,
    pyrefly_gap,
)
from reports import parallel_hint
from test_setup import repository

ONE_ROOT_INI = (
    "[importlinter]\nroot_package = app\n\n[importlinter:contract:own]\nname = Own\n"
    "type = acyclic_siblings\nancestors =\n    app\n    app.**\ndepth = 0\n"
)
ONE_ROOT_TOML = (
    '[tool.importlinter]\nroot_package = "app"\n\n[[tool.importlinter.contracts]]\n'
    'name = "Own"\ntype = "acyclic_siblings"\nancestors = ["app", "app.**"]\ndepth = 0\n'
)


@pytest.mark.parametrize(
    ("name", "settings", "one_root"),
    [
        (".importlinter", ONE_ROOT_INI, "root_package = app"),
        ("pyproject.toml", ONE_ROOT_TOML, 'root_package = "app"'),
    ],
)
def test_the_import_contract_step_keeps_the_root_of_a_one_root_option(
    tmp_path: Path, name: str, settings: str, one_root: str
) -> None:
    for root in ("app", "tools"):
        (tmp_path / root).mkdir()
        (tmp_path / root / "__init__.py").write_text("")
        (tmp_path / root / "mod.py").write_text("value = 1\n")
    owner = tmp_path / name
    owner.write_text(settings)
    group: Group = {"path": ".", "checks": [], "sources": ["app", "tools"]}
    gap = import_contract_gap(tmp_path, group)
    assert gap is not None
    assert "has no import contract for tools, so" in gap
    then = "\nThen add this contract:\n"
    edit = gap[gap.index("root_packages =") : gap.index(then)]
    block = gap[gap.index(then) + len(then) :]
    owner.write_text(settings.replace(one_root, edit) + "\n" + block)
    assert import_contract_gap(tmp_path, group) is None
    assert "put this in place of the root_package line:" in gap


def test_python_packages_receive_recursive_import_contract(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="1"\n')
    package = tmp_path / "src/example"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("value = 1\n")
    (package / "api.py").write_text("value = 2\n")
    installer.install(tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    assert 'root_packages = ["example"]' in content
    assert 'ancestors = ["example", "example.**"]' in content
    assert "depth = 0" in content
    assert (
        import_configuration(
            tmp_path, {"path": ".", "checks": [], "sources": ["src"]}, content
        )
        == content
    )
    content += (
        '\n[[tool.importlinter.contracts]]\nname = "Private implementation"\n'
        'type = "protected"\nprotected_modules = ["example.internal"]\n'
        'allowed_importers = ["example.api"]\n'
    )
    (package / "internal.py").write_text("value = 1\n")
    (package / "api.py").write_text("from example.internal import value\n")
    (tmp_path / "pyproject.toml").write_text(content)
    installer.install(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == content


def test_python_tests_run_in_parallel_unless_a_project_opts_out(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="1"\n')
    (tmp_path / "app.py").write_text("value = 1\n")
    gates = tmp_path / "hard-eng.gates.json"

    def tests_gate() -> tuple[GateConfig, Gate]:
        config = parse_config(gates.read_text())
        checks = config["packages"][0]["checks"]
        return config, next(gate for gate in checks if gate.get("role") == "tests")

    installer.install(tmp_path)
    config, gate = tests_gate()
    parallel = gate["command"]
    runner = parallel.index("-n") - 1
    assert parallel[runner : runner + 3] == ["pytest", "-n", "auto"]
    assert parallel[runner - 4 : runner] == [
        "--with",
        "pytest-xdist",
        "--upgrade-package",
        "pytest-xdist",
    ]
    gate["command"] = [*parallel[: runner - 4], "pytest", *parallel[runner + 3 :]]
    gates.write_text(json.dumps(config))
    installer.install(tmp_path)
    assert tests_gate()[1]["command"] == parallel
    config, gate = tests_gate()
    gate["command"] = [value if value != "auto" else "0" for value in parallel]
    gates.write_text(json.dumps(config))
    installer.install(tmp_path)
    assert tests_gate()[1]["command"] == gate["command"]
    assert "-n 0" in parallel_hint(1, True, parallel)
    assert parallel_hint(0, True, parallel) == parallel_hint(1, True, gate["command"])
    assert parallel_hint(1, True, gate["command"]) == ""


def test_standalone_python_does_not_invent_import_architecture(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "uv.lock").touch()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="1"\n')
    (tmp_path / "main.py").write_text("value = 1\n")
    package = installer.gate_config(tmp_path)["packages"][0]
    assert package["sources"] == ["main.py"]
    assert "imports" not in {gate["role"] for gate in package["checks"]}
    tests = next(gate for gate in package["checks"] if gate["role"] == "tests")
    assert "--cov=main" in tests["command"]
    installer.configure_typing_checks(package)
    installer.configure_typing_checks(package)
    annotations = [gate for gate in package["checks"] if gate["role"] == "annotations"]
    assert len(annotations) == 1
    assert "main.py" in annotations[0]["command"]
    assert "src" not in annotations[0]["command"]


def test_a_python_parent_leaves_out_child_groups_that_have_the_same_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def group(path: str, language: str, *roles: str) -> Group:
        checks: list[Gate] = [
            {"name": role, "role": role, "command": [role]} for role in roles
        ]
        return {"path": path, "language": language, "checks": checks}

    parent = group(".", "python", "tests", "dependencies")
    groups = [
        parent,
        group("packages/a", "python", "tests", "dependencies"),
        group("packages/b", "python", "tests"),
        group("web", "javascript", "tests", "dependencies"),
    ]
    tests, deptry = parent["checks"]
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps({"packages": groups, "shared": []})
    )
    pytest_command = ["uv", "run", "pytest", "-n", "auto"]
    deptry_command = ["deptry", ".", "--no-ansi"]
    assert leave_out_children(tmp_path, pytest_command, parent, tests) == [
        "uv",
        "run",
        "pytest",
        f"--ignore={tmp_path / 'packages/a'}",
        f"--ignore={tmp_path / 'packages/b'}",
        "-n",
        "auto",
    ]
    assert leave_out_children(tmp_path, deptry_command, parent, deptry) == [
        *deptry_command,
        "--extend-exclude",
        "^packages/a(/|$)",
    ]
    child = groups[1]
    assert leave_out_children(tmp_path, pytest_command, child, tests) == (
        pytest_command
    )

    import change_size

    def unreadable(_root: Path) -> dict[str, Group]:
        raise AssertionError("a gate that leaves out nothing read the gates file")

    monkeypatch.setattr(change_size, "configured_packages", unreadable)
    web = groups[3]
    assert leave_out_children(tmp_path, ["web"], web, web["checks"][0]) == ["web"]
    other: Gate = {"name": "lint", "role": "lint", "command": ["ruff"]}
    assert leave_out_children(tmp_path, ["ruff"], parent, other) == ["ruff"]


def pyrefly_package(root: Path, files: dict[str, str]) -> Path:
    directory = root / "tools/cli"
    directory.mkdir(parents=True)
    for name, text in files.items():
        (directory / name).write_text(text)
    return directory


def test_the_strict_pyrefly_refusal_names_the_file_and_the_lines(
    runner: ModuleType, tmp_path: Path
) -> None:
    project = '[project]\nname = "cli"\nversion = "1"\n'
    directory = pyrefly_package(tmp_path, {"pyproject.toml": project})
    with pytest.raises(ValueError) as missing:
        runner.validate_typing(directory, "python")
    text = str(missing.value)
    assert "tools/cli/pyproject.toml" in text
    assert "[tool.pyrefly]" in text
    assert 'preset = "strict"' in text
    assert "check-unannotated-defs" not in text
    assert text.endswith('add preset = "strict" in a new [tool.pyrefly] table')
    (directory / "pyproject.toml").write_text(
        project + '\n[tool.pyrefly]\npreset = "strict"\n'
    )
    runner.validate_typing(directory, "python")
    (directory / "pyrefly.toml").write_text(
        'preset = "strict"\nreplace-imports-with-any = ["a"]\n'
    )
    (directory / "pyproject.toml").write_text(
        project + '[tool.pyrefly]\npreset = "strict"\n'
    )
    with pytest.raises(ValueError) as refused:
        runner.validate_typing(directory, "python")
    text = str(refused.value)
    assert "tools/cli/pyrefly.toml" in text
    assert "replace-imports-with-any" in text
    assert "preset" not in text


@pytest.mark.parametrize(
    ("setting", "key"),
    [
        ("ignore-missing-imports = true", "ignore-missing-imports"),
        (
            'replace-untyped-imports-with-any = ["a"]',
            "replace-untyped-imports-with-any",
        ),
        ("sub-config = [{matches = 'a', settings = {}}]", "sub-config"),
        ("[tool.pyrefly.errors]\nbad-return = false", "bad-return"),
    ],
)
def test_setup_refuses_the_pyrefly_settings_that_the_types_gate_refuses(
    tmp_path: Path, setting: str, key: str
) -> None:
    from python_setup import configure_python

    package: Group = {
        "path": "tools/cli",
        "language": "python",
        "sources": ["cli"],
        "checks": [],
    }
    directory = pyrefly_package(
        tmp_path,
        {
            "uv.lock": "",
            "pyproject.toml": '[project]\nname = "cli"\nversion = "1"\n'
            f'[tool.pyrefly]\npreset = "strict"\n{setting}\n',
        },
    )
    with pytest.raises(
        ValueError, match=r"\. Ask the user before you make that change$"
    ) as error:
        configure_python(tmp_path, directory, package, {})
    assert "tools/cli/pyproject.toml" in str(error.value)
    assert key in str(error.value)


@pytest.mark.parametrize("native", [False, True], ids=["pyproject", "pyrefly-toml"])
@pytest.mark.parametrize(
    ("section", "named"),
    [
        ('preset = "basic"\ncheck-unannotated-defs = true\n', ["preset"]),
        (
            'preset = "strict"\ncheck-unannotated-defs = false\n',
            ["check-unannotated-defs"],
        ),
        (
            'preset = "basic"\ncheck-unannotated-defs = false\n',
            ["preset", "check-unannotated-defs"],
        ),
        ("", ["preset"]),
    ],
)
def test_the_pyrefly_step_sets_only_the_keys_that_are_wrong(
    section: str, named: list[str], native: bool
) -> None:
    head = "" if native else '[project]\nname = "cli"\n\n[tool.pyrefly]\n'
    text = head + section + ('[errors]\nbad-return = "error"\n' if native else "")
    file = "pyrefly.toml" if native else "pyproject.toml"
    parsed = tomllib.loads(text)
    step = pyrefly_gap(file, parsed if native else parsed["tool"]["pyrefly"])
    place = (
        "at the top of the file, before any [table] line"
        if native
        else "under [tool.pyrefly]"
    )
    assert step.endswith(place)
    change = re.compile(r'change (preset|check-unannotated-defs) to ("strict"|true)')
    add = re.compile(r'add (preset|check-unannotated-defs) = ("strict"|true)')
    found = [key for key, _ in change.findall(step) + add.findall(step)]
    assert sorted(found) == sorted(named)
    for key, value in change.findall(step):
        assert re.search(rf"(?m)^{key} = ", text)
        text = re.sub(rf"(?m)^{key} = .*$", f"{key} = {value}", text)
    for key, value in add.findall(step):
        assert not re.search(rf"(?m)^{key} = ", text)
        line = f"{key} = {value}\n"
        text = line + text if native else text.replace(head, head + line, 1)
    fixed = tomllib.loads(text)
    assert pyrefly_gap(file, fixed if native else fixed["tool"]["pyrefly"]) == ""
