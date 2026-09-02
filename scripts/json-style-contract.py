#!/usr/bin/env python3
"""Prove generated JSON already satisfies a repository's Biome format check, so a rollout never turns its CI red."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIOME = ROOT / "node_modules/.bin/biome"
MODULE = ROOT / "runtime/repository_native/jsonstyle.py"
SPACES: dict[str, object] = {"formatter": {"indentStyle": "space"}}
PIN = {"tag": "v2026.09.02", "archive_sha256": "a" * 64, "manifest_sha256": "b" * 64}
GATES: dict[str, object] = {
    "schema_version": 1,
    "families": {
        "targeted": ["npm", "run", "build"],
        "fallow": ["npx", "--yes", "fallow@latest", "--fail-on-issues", "--format", "json", "--quiet"],
        "long": [f"--option-number-{index:02d}" for index in range(12)],
    },
    "phases": {"pre-commit": ["targeted"], "pre-push": ["targeted", "fallow", "long"]},
    "coverage": {"targeted": ["checkpoint check", "package.json"]},
    "empty": {"object": {}, "array": [], "mixed": [1, "two", None, True, 2.5]},
    "hard_eng": {"schema_version": 1, "channel": "prerelease", "wiring": "shared", "pin": PIN},
}
HOOKS: dict[str, object] = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash|Edit|Write",
                "hooks": [{"type": "command", "command": "bash .hard-eng/hook.sh claude pretooluse", "timeout": 30}],
            }
        ]
    }
}
FAILURES: list[str] = []
Renderer = Callable[[object, object], str]


def load_module():
    spec = importlib.util.spec_from_file_location("jsonstyle", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


jsonstyle = load_module()


def stdlib(value: object, _: object) -> str:
    return json.dumps(value, indent=2) + "\n"


def styled(value: object, style: object) -> str:
    return jsonstyle.render(value, style)


def biome_rejection(directory: Path, name: str) -> str | None:
    result = subprocess.run(
        [str(BIOME), "format", name], cwd=directory, capture_output=True, text=True, timeout=120, check=False
    )
    return None if result.returncode == 0 else (result.stdout + result.stderr)[-500:]


def case(
    label: str,
    files: dict[str, object],
    *,
    repo_config: dict[str, object] | None,
    oracle_config: dict[str, object] | None = None,
    renderer: Renderer = styled,
    expect_clean: bool = True,
) -> dict[str, str]:
    rendered: dict[str, str] = {}
    with tempfile.TemporaryDirectory(dir=ROOT / ".git") as temporary:
        directory = Path(temporary)
        (directory / ".git").mkdir()
        if repo_config is not None:
            (directory / "biome.json").write_text(json.dumps(repo_config), encoding="utf-8")
        for name, value in files.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            text = renderer(value, jsonstyle.style_for(path))
            path.write_text(text, encoding="utf-8")
            rendered[name] = text
            if json.loads(text) != value:
                FAILURES.append(f"{label}: {name} does not round-trip")
        if oracle_config is not None:
            (directory / "biome.json").write_text(json.dumps(oracle_config), encoding="utf-8")
        for name in files:
            rejection = biome_rejection(directory, name)
            if expect_clean and rejection is not None:
                FAILURES.append(f"{label}: Biome would reformat {name}: {rejection}")
            if not expect_clean and rejection is None:
                FAILURES.append(f"{label}: Biome accepted {name}, so the oracle proves nothing")
    return rendered


def boundary_value(first: int, second: int, *, last: bool) -> dict[str, object]:
    array = ["a" * first, "b" * second]
    return {"z": 1, "k": array} if last else {"k": array, "z": 1}


def check_boundary() -> None:
    inline = '["' + "a" * 32
    fits = case("boundary fits with comma", {"a.json": boundary_value(32, 32, last=False)}, repo_config=SPACES)
    if inline not in fits["a.json"].split("\n")[1]:
        FAILURES.append("an array that exactly fills the line width was expanded")
    breaks = case("boundary breaks past width", {"a.json": boundary_value(32, 33, last=False)}, repo_config=SPACES)
    if '["' in breaks["a.json"].split("\n")[1]:
        FAILURES.append("an array one column past the line width stayed inline")
    last = case("boundary last property", {"a.json": boundary_value(32, 33, last=True)}, repo_config=SPACES)
    if inline not in last["a.json"].split("\n")[2]:
        FAILURES.append("the last property has no trailing comma, so its array fits and must stay inline")


def check_styles() -> None:
    gates: dict[str, object] = {"hard-eng.gates.json": GATES}
    case("Prettier defaults without any config", gates, repo_config=None, oracle_config=SPACES)
    case("Biome tabs by default", gates, repo_config={})
    case(
        "landroyal shape",
        gates,
        repo_config={"formatter": {"indentStyle": "space", "indentWidth": 2, "lineWidth": 100}},
    )
    case("afenso shape", gates, repo_config={"formatter": {"indentStyle": "space", "lineWidth": 120}})
    case(
        "json section overrides",
        gates,
        repo_config={**SPACES, "json": {"formatter": {"indentWidth": 4, "lineWidth": 60}}},
    )
    case(
        "hook files", {".claude/settings.json": HOOKS, ".codex/hooks.json": {"version": 1, **HOOKS}}, repo_config=SPACES
    )
    case("stdlib output is what Biome rejects", gates, repo_config=SPACES, renderer=stdlib, expect_clean=False)


def check_config_reading() -> None:
    with tempfile.TemporaryDirectory(dir=ROOT / ".git") as temporary:
        directory = Path(temporary)
        (directory / ".git").mkdir()
        (directory / "biome.jsonc").write_text(
            '{\n  // comment with "quotes" and a // marker\n  "$schema": "https://biomejs.dev/schemas/2.0.0/schema.json",\n'
            '  /* block */ "formatter": {"indentStyle": "space", "indentWidth": 4, "lineWidth": 90}\n}\n',
            encoding="utf-8",
        )
        style = jsonstyle.style_for(directory / "packages/app/.claude/settings.json")
        if (style.width, style.indent, style.indent_columns) != (90, "    ", 4):
            FAILURES.append(f"biome.jsonc settings were not read from a parent directory: {style}")
        nested = directory / "vendor/.git"
        nested.mkdir(parents=True)
        inside = jsonstyle.style_for(nested.parent / "hard-eng.gates.json")
        if inside != jsonstyle.JsonStyle():
            FAILURES.append(f"the lookup crossed a nested repository boundary: {inside}")


def main() -> int:
    if not BIOME.is_file():
        print(f"FAIL: Biome oracle missing at {BIOME}", file=sys.stderr)
        return 1
    check_styles()
    check_boundary()
    check_config_reading()
    if FAILURES:
        for failure in FAILURES:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: generated JSON matches Biome and Prettier formatting under every configured style")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
