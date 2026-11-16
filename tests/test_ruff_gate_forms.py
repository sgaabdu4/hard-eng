"""A ruff gate cannot be narrowed by a flag, a path or a wrapper around the command."""

import json
from pathlib import Path

import pytest
from conftest import commit, init
from gate_config import Gate, validate_gate


def lint(command: list[str], role: str = "lint") -> Gate:
    return {"name": role, "role": role, "command": command}


FLAG_FORMS = [
    ["ruff", "check", ".", "--exit-zero"],
    ["ruff", "check", ".", "--isolated"],
    ["ruff", "check", ".", "--extend-exclude", "src"],
    ["ruff", "check", ".", "--extend-exclude=src"],
    ["ruff", "check", ".", "--exclude", "src"],
    ["sh", "-c", "ruff check . --ignore F401"],
    ["sh", "-c", "ruff check . --exit-zero"],
    ["bash", "-c", "ruff check . --isolated"],
]


@pytest.mark.parametrize("command", FLAG_FORMS)
def test_a_ruff_lint_gate_with_a_narrowing_flag_or_wrapper_fails(
    tmp_path: Path, command: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: a flag that hides findings or skips files fails the lint gate, also inside `sh -c`."""
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(lint(command), tmp_path, set())


def test_a_package_script_that_holds_a_narrowing_flag_fails(tmp_path: Path) -> None:
    scripts = {"scripts": {"lint": "ruff check . --exit-zero"}}
    (tmp_path / "package.json").write_text(json.dumps(scripts))
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(lint(["bun", "run", "lint"]), tmp_path, set())
    scripts["scripts"]["lint"] = "ruff check ."
    (tmp_path / "package.json").write_text(json.dumps(scripts))
    validate_gate(lint(["bun", "run", "lint"]), tmp_path, set())


def test_a_format_gate_may_exclude_generated_folders(tmp_path: Path) -> None:
    command = ["ruff", "format", "--check", ".", "--extend-exclude", ".agents/skills"]
    validate_gate(lint(command, "format"), tmp_path, set())


def covered_root(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    tmp_path.mkdir(parents=True, exist_ok=True)
    init(root)
    for name, text in {"a.py": "x = 1\n", **files}.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    commit(root, "files")
    return root


def test_a_lint_gate_path_must_cover_every_python_file(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a lint gate that names paths fails while a tracked Python file lies outside them, a dot folder included."""
    root = covered_root(
        tmp_path,
        {"pkg/b.py": "x = 1\n", "other/c.py": "x = 1\n", ".scripts/tool.py": "x = 1\n"},
    )
    with pytest.raises(ValueError, match=r"HE-NO-SWITCH-OFF.*other/c\.py"):
        validate_gate(lint(["ruff", "check", "a.py", "pkg", ".scripts"]), root, set())
    with pytest.raises(ValueError, match=r"HE-NO-SWITCH-OFF.*\.scripts/tool\.py"):
        validate_gate(lint(["ruff", "check", "a.py", "pkg", "other"]), root, set())
    validate_gate(
        lint(["ruff", "check", "a.py", "pkg", "other", ".scripts"]), root, set()
    )
    validate_gate(lint(["ruff", "check", "."]), root, set())
    validate_gate(lint(["ruff", "check"]), root, set())


def test_files_that_hard_eng_installs_need_no_lint_path_in_a_project(
    tmp_path: Path,
) -> None:
    """Hard Eng lints its own installed files in its own repository; an installed project does not lint them."""
    files = {
        ".hooks/hard-eng-source.json": "{}",
        ".hooks/tool.py": "x = 1\n",
        ".agents/skills/he/scripts/run.py": "x = 1\n",
    }
    root = covered_root(tmp_path / "installed", files)
    validate_gate(lint(["ruff", "check", "a.py"]), root, set())
    own = covered_root(
        tmp_path / "own",
        {".hooks/tool.py": "x = 1\n", ".agents/starters/main.py": "x = 1\n"},
    )
    with pytest.raises(ValueError, match=r"\.agents/starters/main\.py"):
        validate_gate(lint(["ruff", "check", "a.py", ".hooks"]), own, set())
