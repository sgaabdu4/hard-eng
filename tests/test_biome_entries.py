"""Biome settings: the Hard Eng entries that setup adds to the project's files.includes."""

import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from untrusted_input import biome_ignores_hooks, jsonc_config

HARD = ["!.hooks", "!.hard-eng", "!**/coverage"]


@pytest.mark.parametrize(
    ("name", "existing", "expected"),
    [
        (
            "biome.json",
            '{\n  "files": {\n    "includes": ["**", "!dist"]\n  }\n}\n',
            {"files": {"includes": ["**", "!dist", *HARD]}},
        ),
        (
            "biome.json",
            '{"files": {"includes": []}}',
            {"files": {"includes": ["**", *HARD]}},
        ),
        (
            "biome.json",
            '{"files": {"ignoreUnknown": true}, "linter": {"enabled": true}}',
            {
                "files": {"ignoreUnknown": True, "includes": ["**", *HARD]},
                "linter": {"enabled": True},
            },
        ),
        (
            "biome.json",
            '{"linter": {"enabled": true}}',
            {
                "files": {"includes": ["**", *HARD]},
                "linter": {"enabled": True},
            },
        ),
        (
            "biome.jsonc",
            '{\n  // keep me\n  "files": {\n    "includes": [\n      "**", // all\n      "!dist",\n    ],\n  },\n}\n',
            {"files": {"includes": ["**", "!dist", *HARD]}},
        ),
        (
            "biome.json",
            '{\n  "overrides": [{ "includes": ["a"] }],\n  "files": {\n    "includes": ["**"]\n  }\n}\n',
            {
                "overrides": [{"includes": ["a"]}],
                "files": {"includes": ["**", *HARD]},
            },
        ),
        (
            "biome.json",
            '{"overrides": [{"includes": ["a"]}], "linter": {"includes": ["x"]}}',
            {
                "files": {"includes": ["**", *HARD]},
                "overrides": [{"includes": ["a"]}],
                "linter": {"includes": ["x"]},
            },
        ),
    ],
)
def test_setup_keeps_the_project_biome_run_away_from_the_hooks_folder(
    tmp_path: Path, name: str, existing: str, expected: dict[str, object]
) -> None:
    (tmp_path / name).write_text(existing)
    changes: dict[str, str] = {}
    biome_ignores_hooks(tmp_path, changes)
    text = changes[name]
    assert jsonc_config(name, text) == expected
    if "keep me" in existing:
        assert "// keep me" in text
        assert "// all" in text
    (tmp_path / name).write_text(text)
    rerun: dict[str, str] = {}
    biome_ignores_hooks(tmp_path, rerun)
    assert rerun == {}


@pytest.mark.parametrize("language", ["workspace", "python"])
def test_setup_adds_the_biome_entry_when_no_typescript_package_is_at_the_root(
    installer: ModuleType, tmp_path: Path, language: str
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "biome.json").write_text('{"files": {"includes": ["**"]}}')
    if language == "python":
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
        (tmp_path / "uv.lock").write_text("version = 1\n")
    else:
        (tmp_path / "package.json").write_text(
            '{"private": true, "workspaces": ["web"]}'
        )
        (tmp_path / "bun.lock").write_text('{"lockfileVersion": 1}\n')
        (tmp_path / "web/src").mkdir(parents=True)
        (tmp_path / "web/package.json").write_text('{"name": "web"}')
        (tmp_path / "web/tsconfig.json").write_text('{"include": ["src"]}')
        (tmp_path / "web/src/main.ts").write_text("export {};\n")
    changes = installer.plan_install(tmp_path.resolve())[0]
    includes = jsonc_config("biome.json", changes["biome.json"])["files"]
    assert isinstance(includes, dict)
    assert includes["includes"] == ["**", *HARD]


LONG = "a" * 50
LISTED = '"includes": ["**", "!.hooks", "!.hard-eng", "!**/coverage"]'


@pytest.mark.parametrize(
    ("before", "after"),
    [
        (
            '{\n  "files": {\n    "ignoreUnknown": false\n  }\n}\n',
            f'{{\n  "files": {{\n    {LISTED},\n    "ignoreUnknown": false\n  }}\n}}\n',
        ),
        (
            '{\n\t"files": {\n\t\t"ignoreUnknown": false\n\t}\n}\n',
            f'{{\n\t"files": {{\n\t\t{LISTED},\n\t\t"ignoreUnknown": false\n\t}}\n}}\n',
        ),
        (
            '{\n  "linter": {\n    "enabled": true\n  }\n}\n',
            f'{{\n  "files": {{ {LISTED} }},\n  "linter": {{\n    "enabled": true\n  }}\n}}\n',
        ),
        (
            '{\n\t"linter": {\n\t\t"enabled": true\n\t}\n}\n',
            f'{{\n\t"files": {{ {LISTED} }},\n\t"linter": {{\n\t\t"enabled": true\n\t}}\n}}\n',
        ),
        ("{}\n", f'{{ "files": {{ {LISTED} }} }}\n'),
        ('{\n  "files": {}\n}\n', f'{{\n  "files": {{ {LISTED} }}\n}}\n'),
        (
            '{\n  "files": {\n    "includes": [\n      "**",\n      "!dist" // keep\n    ]\n  }\n}\n',
            '{\n  "files": {\n    "includes": [\n      "**",\n      "!dist", // keep\n      "!.hooks",\n      "!.hard-eng",\n      "!**/coverage"\n    ]\n  }\n}\n',
        ),
        (
            f'{{\n\t"files": {{\n\t\t"includes": [\n\t\t\t"**",\n\t\t\t"!{LONG}",\n\t\t\t"!dist"\n\t\t]\n\t}}\n}}\n',
            f'{{\n\t"files": {{\n\t\t"includes": [\n\t\t\t"**",\n\t\t\t"!{LONG}",\n\t\t\t"!dist",\n\t\t\t"!.hooks",\n\t\t\t"!.hard-eng",\n\t\t\t"!**/coverage"\n\t\t]\n\t}}\n}}\n',
        ),
        (
            f'{{\n  "files": {{\n    "includes": ["**", "!{LONG}"]\n  }}\n}}\n',
            f'{{\n  "files": {{\n    "includes": [\n      "**",\n      "!{LONG}",\n      "!.hooks",\n      "!.hard-eng",\n      "!**/coverage"\n    ]\n  }}\n}}\n',
        ),
        (
            f'{{\n\t"files": {{\n\t\t"includes": ["**", "!{LONG}"]\n\t}}\n}}\n',
            f'{{\n\t"files": {{\n\t\t"includes": [\n\t\t\t"**",\n\t\t\t"!{LONG}",\n\t\t\t"!.hooks",\n\t\t\t"!.hard-eng",\n\t\t\t"!**/coverage"\n\t\t]\n\t}}\n}}\n',
        ),
        (
            f'{{\n  "formatter": {{ "lineWidth": 120 }},\n  "files": {{\n    "includes": ["**", "!{LONG}"]\n  }}\n}}\n',
            f'{{\n  "formatter": {{ "lineWidth": 120 }},\n  "files": {{\n    "includes": ["**", "!{LONG}", "!.hooks", "!.hard-eng", "!**/coverage"]\n  }}\n}}\n',
        ),
    ],
)
def test_the_biome_edit_leaves_the_layout_that_the_biome_formatter_writes(
    tmp_path: Path, before: str, after: str
) -> None:
    (tmp_path / "biome.json").write_text(before)
    changes: dict[str, str] = {}
    biome_ignores_hooks(tmp_path, changes)
    assert changes["biome.json"] == after


def test_setup_leaves_a_project_without_biome_settings_alone(tmp_path: Path) -> None:
    changes: dict[str, str] = {}
    biome_ignores_hooks(tmp_path, changes)
    assert changes == {}


@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        (
            '{\n  "files": {\n    "includes": ["**", "!dist", "!.hooks"]\n  }\n}\n',
            ["**", "!dist", "!.hooks", "!.hard-eng", "!**/coverage"],
        ),
        (
            '{\n  "files": {\n    "includes": [\n      "**",\n      "!.hooks"\n    ]\n  }\n}\n',
            ["**", "!.hooks", "!.hard-eng", "!**/coverage"],
        ),
        (
            '{"files": {"includes": ["**", "!.hard-eng", "!.hooks"]}}',
            ["**", "!.hard-eng", "!.hooks", "!**/coverage"],
        ),
    ],
)
def test_setup_adds_only_the_entries_that_an_older_install_lacks(
    tmp_path: Path, existing: str, expected: list[str]
) -> None:
    (tmp_path / "biome.json").write_text(existing)
    changes: dict[str, str] = {}
    biome_ignores_hooks(tmp_path, changes)
    files = jsonc_config("biome.json", changes["biome.json"])["files"]
    assert isinstance(files, dict)
    assert files["includes"] == expected
    (tmp_path / "biome.json").write_text(changes["biome.json"])
    rerun: dict[str, str] = {}
    biome_ignores_hooks(tmp_path, rerun)
    assert rerun == {}


def test_setup_prints_a_step_when_it_cannot_edit_the_biome_settings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    entries = '"!.hooks", "!.hard-eng" and "!**/coverage"'
    (tmp_path / "biome.json").write_text('{"extends": ["./base.json"]}')
    changes: dict[str, str] = {}
    biome_ignores_hooks(tmp_path, changes)
    assert changes == {}
    assert capsys.readouterr().err == (
        "biome.json: it extends another configuration, and a local files.includes "
        "list replaces the inherited one. Copy the inherited list into "
        f'files.includes (use "**" when there is none) and add {entries} as its '
        "last entries, so that your own Biome runs leave the Hard Eng files\n"
    )
    (tmp_path / "biome.json").write_text('{"files": {"includes": [/* ours */]}}')
    biome_ignores_hooks(tmp_path, changes)
    assert changes == {}
    assert capsys.readouterr().err == (
        f'biome.json: files.includes is empty: put "**" first, then add {entries} '
        "as the last entries, so that your own Biome runs leave the Hard Eng files\n"
    )
