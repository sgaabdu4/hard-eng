"""Python projects get the import contract, parallel tests and typing checks they need."""

import json
from pathlib import Path
from types import ModuleType

from gate_config import Gate, GateConfig, parse_config
from python_setup import import_configuration
from reports import parallel_hint
from test_setup import repository


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
