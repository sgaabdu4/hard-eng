"""Untrusted JSON gate: shipped declarations, tsconfig and Fallow wiring, and the cast rule."""

import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import Group
from untrusted_input import fallow_ignores_hooks, jsonc_config, typescript_config

UNTRUSTED = ".hooks/untrusted-input.d.ts"


def typing_template(installer: ModuleType) -> list[str]:
    template = installer.SOURCE / ".agents/skills/he/templates/hard-eng.javascript.json"
    checks = json.loads(template.read_text())["packages"][0]["checks"]
    return next(gate["command"] for gate in checks if gate["role"] == "typing-style")


def test_update_adds_the_cast_rule_to_the_installed_typing_style_gate(
    installer: ModuleType,
) -> None:
    rule = "--only=nursery/noUnsafeTypeAssertion"
    previous = [value for value in typing_template(installer) if value != rule]
    package: Group = {
        "path": ".",
        "language": "javascript",
        "sources": ["src"],
        "checks": [
            {"name": "typing-style", "role": "typing-style", "command": previous}
        ],
    }
    for _ in range(2):
        installer.configure_typing_checks(package)
        typing = [gate for gate in package["checks"] if "typing" in gate["role"]]
        assert typing == [
            {
                "name": "typing-style",
                "role": "typing-style",
                "command": typing_template(installer),
            }
        ]


@pytest.mark.parametrize(
    ("existing", "expected"),
    [
        (
            '{\n  "compilerOptions": {"strict": true},\n  "include": [\n    "src"\n  ]\n}\n',
            {"compilerOptions": {"strict": True}, "include": [UNTRUSTED, "src"]},
        ),
        ('{"files": ["src/main.ts"]}', {"files": [UNTRUSTED, "src/main.ts"]}),
        (
            '{\n  "compilerOptions": {}\n}\n',
            {"include": ["**/*", UNTRUSTED], "compilerOptions": {}},
        ),
        (
            '{\n  // from tsc --init\n  "extends": "./base.json",\n  "include": ["src",],\n}\n',
            {"extends": "./base.json", "include": [UNTRUSTED, "src"]},
        ),
    ],
)
def test_update_adds_untrusted_input_to_an_existing_tsconfig(
    tmp_path: Path, existing: str, expected: dict[str, object]
) -> None:
    (tmp_path / "tsconfig.json").write_text(existing)
    (tmp_path / ".fallowrc.json").write_text('{"ignorePatterns": [".hooks/**"]}')
    changes: dict[str, str] = {}
    typescript_config(tmp_path, tmp_path, ["src"], changes)
    text = changes["tsconfig.json"]
    assert jsonc_config("tsconfig.json", text) == expected
    assert "// from tsc --init" in text or "//" not in existing
    (tmp_path / "tsconfig.json").write_text(text)
    rerun: dict[str, str] = {}
    typescript_config(tmp_path, tmp_path, ["src"], rerun)
    assert rerun == {}


def test_nested_package_tsconfig_reaches_the_root_declarations(tmp_path: Path) -> None:
    child = tmp_path / "packages/app"
    child.mkdir(parents=True)
    changes: dict[str, str] = {}
    typescript_config(tmp_path, child, ["src"], changes)
    written = json.loads(changes["packages/app/tsconfig.json"])
    assert written["include"] == ["src", "test", "tests", f"../../{UNTRUSTED}"]
    assert ".fallowrc.json" not in changes


def test_inherited_file_list_names_the_line_to_add(tmp_path: Path) -> None:
    text = '{"extends": "./base.json"}'
    (tmp_path / "tsconfig.json").write_text(text)
    with pytest.raises(ValueError, match=f"inherits include; .*add '{UNTRUSTED}'"):
        typescript_config(tmp_path, tmp_path, ["src"], {})
    assert (tmp_path / "tsconfig.json").read_text() == text


@pytest.mark.parametrize(
    ("name", "existing", "expected"),
    [
        (None, None, {"ignorePatterns": [".hooks/**"]}),
        (
            ".fallowrc.json",
            '{\n\t"entry": ["a.ts"],\n\t"ignorePatterns": ["apps/**"]\n}\n',
            {"entry": ["a.ts"], "ignorePatterns": [".hooks/**", "apps/**"]},
        ),
        (
            ".fallowrc.jsonc",
            '{\n  // keep me\n  "$schema": "https://example.test/schema.json",\n}\n',
            {
                "ignorePatterns": [".hooks/**"],
                "$schema": "https://example.test/schema.json",
            },
        ),
        (".fallowrc.json", "{}\n", {"ignorePatterns": [".hooks/**"]}),
    ],
)
def test_fallow_config_skips_the_hidden_hard_eng_declarations(
    tmp_path: Path,
    name: str | None,
    existing: str | None,
    expected: dict[str, object],
) -> None:
    if name is not None and existing is not None:
        (tmp_path / name).write_text(existing)
    changes: dict[str, str] = {}
    fallow_ignores_hooks(tmp_path, changes)
    written = name or ".fallowrc.json"
    text = changes[written]
    assert jsonc_config(written, text) == expected
    if existing is not None and "keep me" in existing:
        assert "// keep me" in text
    (tmp_path / written).write_text(text)
    rerun: dict[str, str] = {}
    fallow_ignores_hooks(tmp_path, rerun)
    assert rerun == {}


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("fallow.toml", 'entry = ["a.ts"]\n'),
        (".fallowrc.json", '{"extends": "./base.json"}'),
    ],
)
def test_fallow_config_setup_cannot_edit_names_the_line_to_add(
    tmp_path: Path, name: str, text: str
) -> None:
    (tmp_path / name).write_text(text)
    with pytest.raises(ValueError, match="add '.hooks/\\*\\*' to ignorePatterns"):
        fallow_ignores_hooks(tmp_path, {})


def test_fresh_install_ships_and_includes_the_untrusted_input_declarations(
    installer: ModuleType, tmp_path: Path
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "package.json").write_text('{"private":true}')
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    (tmp_path / "index.ts").write_text("export {};\n")
    changes = installer.plan_install(tmp_path.resolve())[0]
    assert changes[UNTRUSTED] == (installer.SOURCE / UNTRUSTED).read_text()
    assert UNTRUSTED in json.loads(changes["tsconfig.json"])["include"]
    assert json.loads(changes[".fallowrc.json"]) == {"ignorePatterns": [".hooks/**"]}
    gates = json.loads(changes["hard-eng.gates.json"])
    typing = [
        gate["command"]
        for package in gates["packages"]
        for gate in package["checks"]
        if gate.get("role") == "typing-style"
    ]
    assert typing == [typing_template(installer)]


@pytest.mark.parametrize("declared", [True, False])
def test_typescript_check_requires_the_untrusted_input_declarations(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    declared: bool,
) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.ts").write_text("export {};\n")
    files = ["src/app.ts", *([UNTRUSTED] if declared else [])]
    shown = {"compilerOptions": {"strict": True, "checkJs": True}, "files": files}

    def show_config(
        command: list[str], **_: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, json.dumps(shown))

    monkeypatch.setattr(runner.subprocess, "run", show_config)
    group: Group = {
        "path": ".",
        "language": "javascript",
        "sources": ["src"],
        "checks": [],
    }
    if declared:
        runner.validate_typescript(["tsc"], tmp_path, group, 10)
    else:
        with pytest.raises(ValueError, match="omits .hooks/untrusted-input.d.ts"):
            runner.validate_typescript(["tsc"], tmp_path, group, 10)
