"""Untrusted JSON gate: shipped declarations, tsconfig and Fallow wiring, and the cast rule."""

import json
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import Gate, Group
from untrusted_input import (
    fallow_ignores_hooks,
    jsonc_config,
    next_route_types,
    reject_jsdoc_casts,
    typescript_config,
    typescript_projects,
    validate_typescript,
)

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


@pytest.mark.parametrize(
    ("base", "location", "expected"),
    [
        ({"include": ["src"]}, "base.json", {"files": [UNTRUSTED]}),
        ({"compilerOptions": {}}, "base.json", {"include": ["**/*", UNTRUSTED]}),
        (
            {"compilerOptions": {}},
            "node_modules/@acme/tsconfig/tsconfig.json",
            {"include": ["**/*", UNTRUSTED]},
        ),
    ],
)
def test_extended_tsconfig_keeps_the_files_typescript_inherits(
    tmp_path: Path, base: dict[str, object], location: str, expected: dict[str, object]
) -> None:
    path = tmp_path / location
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(base))
    extends = "./base.json" if location == "base.json" else "@acme/tsconfig"
    (tmp_path / "tsconfig.json").write_text(json.dumps({"extends": extends}))
    (tmp_path / ".fallowrc.json").write_text('{"ignorePatterns": [".hooks/**"]}')
    changes: dict[str, str] = {}
    typescript_config(tmp_path, tmp_path, ["src"], changes)
    assert jsonc_config("tsconfig.json", changes["tsconfig.json"]) == {
        "extends": extends,
        **expected,
    }


@pytest.mark.parametrize("base", [None, {"files": ["src/main.ts"]}])
def test_inherited_file_list_setup_cannot_extend_names_the_line_to_add(
    tmp_path: Path, base: dict[str, object] | None
) -> None:
    if base is not None:
        (tmp_path / "base.json").write_text(json.dumps(base))
    text = '{"extends": "./base.json"}'
    (tmp_path / "tsconfig.json").write_text(text)
    with pytest.raises(ValueError, match=f"cannot extend; add '{UNTRUSTED}'"):
        typescript_config(tmp_path, tmp_path, ["src"], {})
    assert (tmp_path / "tsconfig.json").read_text() == text


def test_javascript_type_assertions_fail_like_typescript_casts(tmp_path: Path) -> None:
    (tmp_path / "cast.mjs").write_text(
        "const raw = '{}';\n"
        "export const user = /** @type {{name: string}} */ (JSON.parse(raw));\n"
        "export const admin =\n"
        "  /**\n   * The signed-in admin.\n   * @type {{name: string}}\n   */ (\n"
        "    JSON.parse(raw)\n  );\n"
    )
    (tmp_path / "valid.mjs").write_text(
        "/** @type {unknown} */\n"
        "const parsed = JSON.parse('{}');\n"
        "export const modes = /** @type {const} */ (['a', 'b']);\n"
        "export { parsed };\n"
    )
    (tmp_path / "types.ts").write_text("/** @type {X} */ (value);\n")
    reject_jsdoc_casts(tmp_path, ["valid.mjs", "types.ts"])
    with pytest.raises(ValueError, match=r"type guard: cast\.mjs:2, cast\.mjs:4$"):
        reject_jsdoc_casts(tmp_path, ["cast.mjs", "valid.mjs", "types.ts"])


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
    (tmp_path / "bun.lock").write_text('{"lockfileVersion": 1}\n')
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


def vite_react_ts(
    root: Path, root_files: list[str], lists: dict[str, list[str]] | None = None
) -> None:
    """The tsconfig layout `bun create vite --template react-ts` writes."""
    solution = {
        **(lists or {"files": root_files}),
        "references": [
            {"path": "./tsconfig.app.json"},
            {"path": "./tsconfig.node.json"},
        ],
    }
    (root / "tsconfig.json").write_text(json.dumps(solution, indent=2))
    app = '{\n  "compilerOptions": {\n    /* Bundler mode */\n    "noEmit": true,\n    "jsx": "react-jsx"\n  },\n  "include": ["src"]\n}\n'
    (root / "tsconfig.app.json").write_text(app)
    node = '{\n  "compilerOptions": {"module": "nodenext", "noEmit": true},\n  "include": ["vite.config.ts"]\n}\n'
    (root / "tsconfig.node.json").write_text(node)
    (root / "src").mkdir()
    (root / "src/main.tsx").write_text("export {};\n")
    (root / "vite.config.ts").write_text("export default {};\n")


def test_fresh_vite_install_keeps_the_solution_tsconfig_buildable(
    installer: ModuleType, tmp_path: Path
) -> None:
    """`tsc -b` fails with TS6306/TS6310 once the solution root lists a file."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    scripts = {"build": "tsc -b && vite build"}
    (tmp_path / "package.json").write_text(json.dumps({"scripts": scripts}))
    (tmp_path / "bun.lock").write_text('{"lockfileVersion": 1}\n')
    vite_react_ts(tmp_path, [])
    changes = installer.plan_install(tmp_path.resolve())[0]
    assert "tsconfig.json" not in changes
    for name in ("tsconfig.app.json", "tsconfig.node.json"):
        include = jsonc_config(name, changes[name])["include"]
        assert isinstance(include, list) and UNTRUSTED in include
    assert "/* Bundler mode */" in changes["tsconfig.app.json"]


@pytest.mark.parametrize(
    ("root", "repaired"),
    [
        ({"files": [UNTRUSTED]}, {"files": []}),
        ({"files": [], "include": [UNTRUSTED]}, {"files": [], "include": []}),
        ({"files": [], "include": []}, None),
    ],
)
def test_update_repairs_a_solution_tsconfig_an_earlier_setup_broke(
    tmp_path: Path,
    root: dict[str, list[str]],
    repaired: dict[str, list[str]] | None,
) -> None:
    """Nx-style roots list `include: []` beside `files: []`; both stay solution roots."""
    vite_react_ts(tmp_path, [], root)
    (tmp_path / ".fallowrc.json").write_text('{"ignorePatterns": [".hooks/**"]}')
    changes: dict[str, str] = {}
    typescript_config(tmp_path, tmp_path, ["src", "vite.config.ts"], changes)
    if repaired is None:
        assert "tsconfig.json" not in changes
    else:
        solution = jsonc_config("tsconfig.json", changes["tsconfig.json"])
        assert {key: solution[key] for key in repaired} == repaired
    for name, source in (
        ("tsconfig.app.json", "src"),
        ("tsconfig.node.json", "vite.config.ts"),
    ):
        assert jsonc_config(name, changes[name])["include"] == [UNTRUSTED, source]
    for name, text in changes.items():
        (tmp_path / name).write_text(text)
    rerun: dict[str, str] = {}
    typescript_config(tmp_path, tmp_path, ["src", "vite.config.ts"], rerun)
    assert rerun == {}


@pytest.mark.parametrize("declared", [True, False])
def test_typescript_check_requires_the_untrusted_input_declarations(
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

    monkeypatch.setattr(subprocess, "run", show_config)
    expected = {tmp_path / "src/app.ts"}
    if declared:
        validate_typescript(tmp_path, ["tsc"], tmp_path, expected, 10)
    else:
        with pytest.raises(ValueError, match="omits .hooks/untrusted-input.d.ts"):
            validate_typescript(tmp_path, ["tsc"], tmp_path, expected, 10)


FAKE_TSC = """
import json, sys
args = sys.argv[1:]
project = args[args.index("-p") + 1] if "-p" in args else "tsconfig.json"
untrusted = ".hooks/untrusted-input.d.ts"
files = {
    "tsconfig.json": [untrusted],
    "tsconfig.app.json": ["src/main.tsx", untrusted],
    "tsconfig.node.json": ["vite.config.ts", untrusted],
}[project]
if "--showConfig" in args:
    print(json.dumps({"compilerOptions": {"strict": True, "checkJs": True}, "files": files}))
else:
    with open("runs.txt", "a") as runs:
        runs.write(project + "\\n")
    raise SystemExit(int(project == sys.argv[1]))
"""


@pytest.mark.parametrize("failing", ["", "tsconfig.app.json"])
def test_types_gate_checks_each_config_a_solution_tsconfig_references(
    runner: ModuleType, tmp_path: Path, failing: str
) -> None:
    """Checking the solution root alone compiles only the declarations, none of src."""
    vite_react_ts(tmp_path, [])
    group: Group = {
        "path": ".",
        "language": "javascript",
        "sources": ["src", "vite.config.ts"],
        "checks": [],
    }
    command = [sys.executable, "-c", FAKE_TSC, failing]
    types: Gate = {"name": "types", "role": "types", "command": command}
    assert runner.run_gate(group, types, 30, threading.Lock()) is bool(failing)
    runs = (tmp_path / "runs.txt").read_text().split()
    assert runs == ["tsconfig.app.json", "tsconfig.node.json"]


@pytest.mark.parametrize(
    ("package", "dependencies", "cli", "typegen"),
    [
        (".", {"next": "16.4.0"}, "node_modules", True),
        (".", {"next": "15.0.0"}, None, False),
        ("apps/web", {"next": "16.4.0"}, "node_modules", True),
        (".", {}, "node_modules", False),
        ("packages/ui", {"next": "16.4.0"}, "node_modules", False),
    ],
)
def test_types_gate_writes_next_route_types_before_a_clean_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    package: str,
    dependencies: dict[str, str],
    cli: str | None,
    typegen: bool,
) -> None:
    """A clean checkout lacks Next's `LayoutProps`; Bun workspaces hoist Next to the root."""
    directory = tmp_path / package
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"dependencies": dependencies}
    (directory / "package.json").write_text(json.dumps(manifest))
    if package != "packages/ui":
        (directory / "app").mkdir()
    if cli is not None:
        typegen_cli = tmp_path / cli / "next/dist/cli/next-typegen.js"
        typegen_cli.parent.mkdir(parents=True)
        typegen_cli.write_text("")
    calls: list[tuple[list[str], object]] = []

    def run(command: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, options.get("cwd")))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    next_route_types(directory, 10)
    expected: list[tuple[list[str], object]] = []
    if typegen:
        expected.append((["bun", "x", "next", "typegen"], directory))
    assert calls == expected


def test_types_gate_reads_nested_config_files_from_their_own_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`tsc -p client/tsconfig.json --showConfig` lists files relative to client/."""
    solution = '{"files": [], "references": [{"path": "./client"}]}'
    (tmp_path / "tsconfig.json").write_text(solution)
    (tmp_path / "client/src").mkdir(parents=True)
    (tmp_path / "client/tsconfig.json").write_text('{"include": ["src"]}')
    (tmp_path / "client/src/app.ts").write_text("export {};\n")
    shown = {
        "compilerOptions": {"strict": True, "checkJs": True},
        "files": ["./src/app.ts", f"../{UNTRUSTED}"],
    }

    def show_config(
        command: list[str], **_: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 0, json.dumps(shown))

    monkeypatch.setattr(subprocess, "run", show_config)
    expected = {tmp_path / "client/src/app.ts"}
    validate_typescript(tmp_path, ["tsc"], tmp_path, expected, 10)


@pytest.mark.parametrize("composite", [True, False])
def test_types_gate_builds_composite_references_before_checking_dependents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, composite: bool
) -> None:
    """A dependent `--noEmit` check fails with TS6305 until its composite reference is built."""
    vite_react_ts(tmp_path, [])
    calls: list[list[str]] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        project = command[command.index("-p") + 1] if "-p" in command else ""
        source = "src/main.tsx" if "app" in project else "vite.config.ts"
        options = {"strict": True, "checkJs": True, "composite": composite}
        shown = {"compilerOptions": options, "files": [source, UNTRUSTED]}
        return subprocess.CompletedProcess(command, 0, json.dumps(shown))

    monkeypatch.setattr(subprocess, "run", run)
    expected = {tmp_path / "src/main.tsx", tmp_path / "vite.config.ts"}
    validate_typescript(tmp_path, ["tsc", "--noEmit"], tmp_path, expected, 10)
    assert (["tsc", "-b"] in calls) is composite


def test_setup_and_types_gate_follow_references_through_an_app_to_its_library(
    tmp_path: Path,
) -> None:
    (tmp_path / "tsconfig.json").write_text(
        '{"files": [], "references": [{"path": "./app"}]}'
    )
    for name, extra in (("app", ', "references": [{"path": "../lib"}]'), ("lib", "")):
        (tmp_path / name).mkdir()
        (tmp_path / name / "tsconfig.json").write_text(f'{{"include": ["src"]{extra}}}')
    (tmp_path / ".fallowrc.json").write_text('{"ignorePatterns": [".hooks/**"]}')
    changes: dict[str, str] = {}
    typescript_config(tmp_path, tmp_path, ["app/src", "lib/src"], changes)
    assert sorted(changes) == ["app/tsconfig.json", "lib/tsconfig.json"]
    assert typescript_projects(tmp_path, ["tsc"], tmp_path) == [
        ["-p", "app/tsconfig.json"],
        ["-p", "lib/tsconfig.json"],
    ]


def test_types_gate_requires_composite_configs_to_set_strict_themselves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`tsc -b` ignores the gate's flags, so a loose composite emits declarations without null."""
    vite_react_ts(tmp_path, [])

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        project = command[command.index("-p") + 1] if "-p" in command else ""
        source = "src/main.tsx" if "app" in project else "vite.config.ts"
        options = {"strict": "--strict" in command, "checkJs": True, "composite": True}
        shown = {"compilerOptions": options, "files": [source, UNTRUSTED]}
        return subprocess.CompletedProcess(command, 0, json.dumps(shown))

    monkeypatch.setattr(subprocess, "run", run)
    expected = {tmp_path / "src/main.tsx", tmp_path / "vite.config.ts"}
    with pytest.raises(ValueError, match="composite tsconfig must set strict"):
        validate_typescript(tmp_path, ["tsc", "--strict"], tmp_path, expected, 10)


def test_types_gate_fails_when_the_composite_solution_build_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stale declarations from an earlier build would let dependent checks pass."""
    vite_react_ts(tmp_path, [])

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if "-b" in command:
            return subprocess.CompletedProcess(command, 1, "error TS6202: cycle", "")
        project = command[command.index("-p") + 1] if "-p" in command else ""
        source = "src/main.tsx" if "app" in project else "vite.config.ts"
        options = {"strict": True, "checkJs": True, "composite": True}
        shown = {"compilerOptions": options, "files": [source, UNTRUSTED]}
        return subprocess.CompletedProcess(command, 0, json.dumps(shown))

    monkeypatch.setattr(subprocess, "run", run)
    expected = {tmp_path / "src/main.tsx", tmp_path / "vite.config.ts"}
    with pytest.raises(ValueError, match="TS6202"):
        validate_typescript(tmp_path, ["tsc"], tmp_path, expected, 10)
