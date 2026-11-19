"""Anything the judge does not recognise is refused: each row is an input a review found passing."""

import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import Gate, Group, validate_gate
from resolved_settings import validate_resolved
from test_fallow_resolved import need_fallow
from test_strict_refusals import project

LINT = ["uvx", "ruff@latest", "check", "."]
DEAD = ["fallow", "--only", "dead-code,dupes,health", "--fail-on-issues"]


def gate(command: list[str], role: str = "lint") -> Gate:
    return {"name": role, "role": role, "command": command}


def lint_groups(*paths: tuple[str, list[str]]) -> list[Group]:
    return [
        {"path": path, "language": "python", "checks": [gate(command)]}
        for path, command in paths
    ]


def fallow_groups() -> list[Group]:
    return [
        {
            "path": ".",
            "language": "javascript",
            "checks": [gate(DEAD, "dead-code-duplicates")],
        }
    ]


WRAPPED = [
    ["bash", "-ec", "ruff check . --exit-zero"],
    ["sh", "-ec", "ruff check . --extend-ignore F401"],
    ["bash", "-lc", "ruff check . --select E501"],
    ["bash", "-ec", "cargo clippy -- -A warnings"],
    ["bash", "-c", "eval 'ruff check . --exit-zero'"],
    ["sh", "-c", "ruff check $(echo . --exit-zero)"],
    ["eval", "ruff check . --exit-zero"],
    ["ruff", "check", ".", "--statistics"],
    ["ruff", "check", ".", "--stdin-filename", "x.py"],
    ["ruff", "check", ".", "--unknown-flag"],
    ["ruff", "check", ".", "--dupes-min-tokens"],
]


@pytest.mark.parametrize("command", WRAPPED)
def test_a_gate_that_cannot_be_reduced_to_a_judged_command_is_refused(
    tmp_path: Path, command: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: joined shell flags, eval, variables and flags the judge does not list fail at load, never as a traceback."""
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate(command), tmp_path, set())


@pytest.mark.parametrize(
    "command",
    [
        ["ruff", "check", "."],
        ["ruff", "check", ".", "--extend-select", "C901,PLR0912,PLR0915"],
        ["ruff", "check", ".", "--select", "ALL"],
        ["ruff", "check", ".", "--output-format", "concise", "--no-cache"],
        ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"],
    ],
)
def test_the_listed_forms_still_pass(tmp_path: Path, command: list[str]) -> None:
    validate_gate(gate(command), tmp_path, set())


def test_the_ruff_format_gate_may_extend_exclude(tmp_path: Path) -> None:
    command = ["ruff", "format", "--check", ".", "--extend-exclude", ".agents/skills"]
    validate_gate(gate(command, "format"), tmp_path, set())


NESTED = {
    "sub/ruff.toml selects": ("sub/ruff.toml", '[lint]\nselect = ["E501"]\n'),
    "sub/ruff.toml excludes": ("sub/ruff.toml", 'exclude = ["*.py"]\n'),
    "sub/pyproject.toml selects": (
        "sub/pyproject.toml",
        '[tool.ruff.lint]\nselect = ["E501"]\n',
    ),
}


@pytest.mark.parametrize("name", NESTED)
def test_a_ruff_config_below_a_gate_root_needs_its_own_gate_group(
    tmp_path: Path, name: str
) -> None:
    """HE-NO-SWITCH-OFF: ruff reads the closest config for each file, so a config below the root must be a gate root itself."""
    file, text = NESTED[name]
    root = project(
        tmp_path, {"main.py": "import os\n", "sub/a.py": "import os\n", file: text}
    )
    with pytest.raises(ValueError, match="give it its own gate group"):
        validate_resolved(root, lint_groups((".", LINT)), 900)


FALLOW = {
    "dynamicallyLoaded": {"dynamicallyLoaded": ["src/**"]},
    "entry wildcard": {"entry": ["src/*.ts"]},
    "ignoreExports": {"ignoreExports": [{"file": "src/a.ts", "exports": ["*"]}]},
    "duplicates.ignore": {"duplicates": {"ignore": ["src/**"]}},
    "minTokens": {"duplicates": {"minTokens": 100000}},
    "skipLocal": {"duplicates": {"skipLocal": True}},
}


@pytest.mark.parametrize("name", FALLOW)
def test_a_fallow_setting_that_hides_findings_is_refused(
    tmp_path: Path, name: str
) -> None:
    """HE-NO-SWITCH-OFF: each key `fallow config` prints is free, equal to its default or proven; the rest fail."""
    need_fallow()
    root = project(
        tmp_path,
        {
            ".fallowrc.json": json.dumps(FALLOW[name]),
            "src/a.ts": "export const a = 1;\n",
        },
    )
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_resolved(root, fallow_groups(), 900)


def test_loading_a_gate_runs_no_git_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The gate loader stays cheap: file scope is judged in the full check."""

    def refuse(*_arguments: object, **_options: object) -> None:
        raise AssertionError("gate load started a process")

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(subprocess, "run", refuse)
    validate_gate(gate(["ruff", "check", "src", "tests"]), tmp_path, set())


NO_FILES: dict[str, str] = {}
SCOPE = {
    "include setting": (
        {"pyproject.toml": '[tool.ruff]\ninclude = ["main.py"]\n'},
        LINT,
    ),
    "include flag": (NO_FILES, [*LINT, "--config", "include=['main.py']"]),
    ".ignore file": ({".ignore": "sub/\n"}, LINT),
    "exclude flag": (NO_FILES, [*LINT, "--exclude", "sub"]),
}


@pytest.mark.parametrize("name", SCOPE)
def test_a_lint_gate_that_checks_fewer_files_than_git_tracks_is_refused(
    tmp_path: Path, name: str
) -> None:
    """HE-NO-SWITCH-OFF: ruff is asked which files it checks, and each tracked Python file that it skips fails."""
    files, command = SCOPE[name]
    root = project(
        tmp_path, {"main.py": "import os\n", "sub/a.py": "import os\n", **files}
    )
    with pytest.raises(ValueError, match=r"sub/a\.py|main\.py"):
        validate_resolved(root, lint_groups((".", command)), 900)


def test_generated_files_may_be_left_out(tmp_path: Path) -> None:
    files = {
        "main.py": "x = 1\n",
        "proto/a_pb2.py": "import os\n",
        ".gitattributes": "proto/a_pb2.py linguist-generated\n",
    }
    root = project(tmp_path, files)
    validate_resolved(
        root, lint_groups((".", [*LINT, "--extend-exclude", "proto"])), 900
    )
    validate_resolved(root, lint_groups((".", [*LINT[:3], "main.py"])), 900)
    other = project(tmp_path / "plain", {**files, ".gitattributes": ""})
    with pytest.raises(ValueError, match=r"proto/a_pb2\.py"):
        validate_resolved(
            other, lint_groups((".", [*LINT, "--extend-exclude", "proto"])), 900
        )


@pytest.mark.parametrize(
    "mark", ["* linguist-generated\n", "other/** linguist-vendored\n"]
)
def test_a_catch_all_mark_does_not_leave_files_out(tmp_path: Path, mark: str) -> None:
    """HE-NO-SWITCH-OFF: a broad mark hides no file from the files-checked rule."""
    files = {"src/a.py": "x = 1\n", "other/b.py": "x = 1\n", ".gitattributes": mark}
    root = project(tmp_path, files)
    with pytest.raises(ValueError, match=r"other/b\.py"):
        validate_resolved(root, lint_groups((".", [*LINT[:3], "src"])), 900)


def test_files_that_hard_eng_installs_are_left_out_of_a_project_only(
    tmp_path: Path,
) -> None:
    """An installed project does not check the files Hard Eng writes; Hard Eng's own source does."""
    files = {
        "main.py": "x = 1\n",
        ".hooks/tool.py": "x = 1\n",
        ".agents/skills/he/run.py": "x = 1\n",
    }
    installed = project(
        tmp_path / "installed", {**files, ".hooks/hard-eng-source.json": "{}"}
    )
    validate_resolved(installed, lint_groups((".", [*LINT[:3], "main.py"])), 900)
    own = project(tmp_path / "own", files)
    with pytest.raises(ValueError, match=r"\.agents/skills/he/run\.py"):
        validate_resolved(own, lint_groups((".", [*LINT[:3], "main.py"])), 900)


def test_a_child_group_owns_its_files(tmp_path: Path) -> None:
    """A parent that names `src tests` does not own a child package that has its own lint gate."""
    files = {
        "src/a.py": "x = 1\n",
        "tests/t.py": "x = 1\n",
        "packages/child/src/c.py": "x = 1\n",
    }
    root = project(tmp_path, files)
    parent = [*LINT[:3], "src", "tests"]
    validate_resolved(root, lint_groups((".", parent), ("packages/child", LINT)), 900)
    with pytest.raises(ValueError, match=r"packages/child/src/c\.py"):
        validate_resolved(root, lint_groups((".", parent)), 900)


def test_the_run_judges_a_parent_against_every_group_not_only_the_changed_ones(
    tmp_path: Path,
) -> None:
    need_fallow()
    config = json.dumps({"ignorePatterns": ["packages/child/**"]})
    files = {
        ".fallowrc.json": config,
        "src/a.ts": "export const a = 1;\n",
        "packages/child/.fallowrc.json": "{}",
        "packages/child/src/b.ts": "export const b = 1;\n",
    }
    root = project(tmp_path, files)
    every: list[Group] = [
        *fallow_groups(),
        {
            "path": "packages/child",
            "language": "javascript",
            "checks": [gate(DEAD, "dead-code-duplicates")],
        },
    ]
    validate_resolved(root, every[:1], 900, every)
    with pytest.raises(ValueError, match=r"packages/child/src/b\.ts"):
        validate_resolved(root, every[:1], 900)


def test_the_run_judges_the_root_gate_against_every_configured_group(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run of the root group alone still knows the child group, so the root ignore of the child root is accepted; a child with no Fallow gate is still refused."""
    need_fallow()
    files = {
        ".fallowrc.json": json.dumps({"ignorePatterns": ["packages/child/**"]}),
        "src/a.ts": "export const a = 1;\n",
        "packages/child/.fallowrc.json": "{}",
        "packages/child/src/b.ts": "export const b = 1;\n",
    }
    monkeypatch.setattr(runner, "ROOT", project(tmp_path, files))
    root_group = fallow_groups()[0]
    child: Group = {
        "path": "packages/child",
        "language": "javascript",
        "checks": [gate(DEAD, "dead-code-duplicates")],
    }
    monkeypatch.setattr(runner, "CONFIGURED", [root_group, child])
    runner.prepared_command(root_group, root_group["checks"][0], 900, [root_group])
    child["checks"] = [gate(LINT)]
    with pytest.raises(ValueError, match=r"packages/child/src/b\.ts"):
        runner.prepared_command(root_group, root_group["checks"][0], 900, [root_group])


@pytest.mark.parametrize(
    "flags", [["--dupes-min-tokens", "100000"], ["--dupes-min-lines", "10000"]]
)
def test_a_fallow_gate_flag_that_loosens_the_duplicate_scan_is_refused(
    tmp_path: Path, flags: list[str]
) -> None:
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate([*DEAD, *flags], "dead-code-duplicates"), tmp_path, set())


def test_a_fallow_gate_with_a_base_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: `--base HEAD` makes an audit judge only the changed files, so a branch with old findings passes."""
    command = ["fallow", "audit", "--gate", "all", "--base", "HEAD", "--fail-on-issues"]
    with pytest.raises(
        ValueError,
        match=r"Fallow scans must cover the whole project[\s\S]*remove --base",
    ):
        validate_gate(gate(command, "dead-code-duplicates"), tmp_path, set())


def test_a_fallow_config_below_a_gate_root_needs_its_own_gate_group(
    tmp_path: Path,
) -> None:
    need_fallow()
    files = {
        "src/a.ts": "export const a = 1;\n",
        "sub/.fallowrc.json": "{}",
        "sub/b.ts": "export const b = 1;\n",
    }
    root = project(tmp_path, files)
    with pytest.raises(ValueError, match="give it its own gate group"):
        validate_resolved(root, fallow_groups(), 900)
    every: list[Group] = [
        *fallow_groups(),
        {
            "path": "sub",
            "language": "javascript",
            "checks": [gate(DEAD, "dead-code-duplicates")],
        },
    ]
    validate_resolved(root, every, 900)


def test_a_nested_ruff_config_that_sets_the_target_version_is_refused(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: no ruff key is free below a gate root, because a lower target version hides findings."""
    root = project(
        tmp_path,
        {"main.py": "x = 1\n", "sub/ruff.toml": 'target-version = "py37"\n'},
    )
    with pytest.raises(ValueError, match="give it its own gate group"):
        validate_resolved(root, lint_groups((".", LINT)), 900)


def test_a_nested_ruff_config_that_sets_a_target_at_the_minimum_passes(
    tmp_path: Path,
) -> None:
    """A target version at the `requires-python` minimum cannot hide a finding, so the folder needs no gate group."""
    root = project(
        tmp_path,
        {
            "main.py": "x = 1\n",
            "pyproject.toml": '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.12"\n',
            "sub/ruff.toml": 'target-version = "py312"\n',
        },
    )
    validate_resolved(root, lint_groups((".", LINT)), 900)


def test_a_ruff_config_in_a_javascript_group_is_judged_by_the_python_gate_above(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: ruff reads the closest config for each Python file, whatever language owns the folder."""
    root = project(
        tmp_path,
        {
            "main.py": "import os\n",
            "web/package.json": "{}",
            "web/tools/x.py": "import os\n",
            "web/ruff.toml": '[lint]\nselect = ["E501"]\n',
        },
    )
    every: list[Group] = [
        *lint_groups((".", LINT)),
        {"path": "web", "language": "javascript", "checks": []},
    ]
    with pytest.raises(ValueError, match="give it its own gate group"):
        validate_resolved(root, every, 900)


def test_a_gate_that_leaves_files_out_names_the_path_to_add(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: when only the annotations gate leaves a file out, the refusal says where to add it."""
    root = project(tmp_path, {"main.py": "x = 1\n", "sub/a.py": "x = 1\n"})
    command = ["ruff", "check", "main.py", "--select", "ANN"]
    every: list[Group] = [
        {"path": ".", "language": "python", "checks": [gate(command, "annotations")]}
    ]
    with pytest.raises(ValueError, match=r"add sub/a\.py to the annotations gate"):
        validate_resolved(root, every, 900)
