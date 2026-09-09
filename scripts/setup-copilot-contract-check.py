#!/usr/bin/env python3
"""Isolated contracts for the global Copilot CLI setup owner (`scripts/setup/copilot.sh`)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_TOOL = ROOT / "scripts/setup/copilot-settings.py"
START = "# >>> hard-eng managed Copilot instructions >>>"
END = "# <<< hard-eng managed Copilot instructions <<<"
LEGACY_BLOCK = f'{START}\nexport COPILOT_CUSTOM_INSTRUCTIONS_DIRS="$HOME/.agents"\n{END}\n'
TOOLS = ("bash", "git", "node", "npm", "npx", "perl", "python3", "sh")
SKIPPED = "Copilot CLI is not installed; skipped Copilot wiring"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-copilot-contract: FAIL {message}")


def context_version() -> str:
    manifest = json.loads((ROOT / "scripts/setup/manifest.json").read_text(encoding="utf-8"))
    return manifest["codex"]["context_mode"]["version"]


def prepare_copilot_tools(home: Path) -> Path:
    source = home / ".local/share/hard-eng/npm-runtime/node_modules/context-mode/configs/copilot-cli"
    (source / ".github/plugin").mkdir(parents=True)
    (source / "skills/context-mode").mkdir(parents=True)
    (source / ".github/plugin/plugin.json").write_text(
        json.dumps({"name": "context-mode", "version": context_version(), "skills": ["./skills/context-mode"]}) + "\n",
        encoding="utf-8",
    )
    (source / ".mcp.json").write_text('{"mcpServers":{"context-mode":{"command":"context-mode"}}}\n', encoding="utf-8")
    (source / "hooks.json").write_text('{"version":1,"hooks":{"sessionStart":[]}}\n', encoding="utf-8")
    (source / "skills/context-mode/SKILL.md").write_text(
        "---\nname: context-mode\ndescription: test\n---\n", encoding="utf-8"
    )
    fake_bin = home / "fake-bin"
    fake_bin.mkdir()
    fake_copilot = fake_bin / "copilot"
    fake_copilot.write_text(
        """#!/usr/bin/env python3
import json
import os
import shutil
import sys
from pathlib import Path

home = Path(os.environ["COPILOT_HOME"])
if os.environ.get("FAKE_COPILOT_FAIL") == "1":
    raise SystemExit(7)
if sys.argv[1:3] == ["mcp", "add"]:
    name = sys.argv[3]
    command = sys.argv[sys.argv.index("--") + 1]
    config_path = home / "mcp-config.json"
    if config_path.exists():
        servers_config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        servers_config = {"mcpServers": {}}
    servers_config.setdefault("mcpServers", {})[name] = {
        "tools": ["*"],
        "type": "local",
        "command": command,
        "args": [],
    }
    config_path.write_text(json.dumps(servers_config, indent=2) + "\\n", encoding="utf-8")
    raise SystemExit(0)
if sys.argv[1:3] != ["plugin", "install"]:
    raise SystemExit(2)
source = Path(sys.argv[3])
cache = home / "installed-plugins/_direct/copilot-cli"
cache.parent.mkdir(parents=True, exist_ok=True)
if cache.exists():
    shutil.rmtree(cache)
shutil.copytree(source, cache)
config_path = home / "config.json"
if config_path.exists():
    raw = config_path.read_text(encoding="utf-8")
    raw = "\\n".join(
        line for line in raw.splitlines() if not line.lstrip().startswith("//")
    )
    config = json.loads(raw or "{}")
else:
    config = {}
installed = [
    item
    for item in config.get("installedPlugins", [])
    if item.get("name") != "context-mode"
]
manifest = json.loads(
    (source / ".github/plugin/plugin.json").read_text(encoding="utf-8")
)
installed.append(
    {
        "name": manifest["name"],
        "version": manifest["version"],
        "enabled": True,
        "cache_path": str(cache),
        "source": {"source": "local", "path": str(source)},
    }
)
config["installedPlugins"] = installed
config_path.write_text(json.dumps(config, indent=2) + "\\n", encoding="utf-8")
settings = home / "settings.json"
if not settings.exists():
    settings.write_text('{"enabledPlugins":{}}\\n', encoding="utf-8")
if os.environ.get("FAKE_COPILOT_FAIL_AFTER") == "1":
    raise SystemExit(8)
""",
        encoding="utf-8",
    )
    fake_copilot.chmod(0o755)
    return fake_bin


def tools_path(home: Path) -> Path:
    tools = home / "tools"
    if not tools.exists():
        tools.mkdir()
        for name in TOOLS:
            target = shutil.which(name)
            if target is not None:
                (tools / name).symlink_to(target)
    return tools


def run_owner(
    home: Path,
    mode: str,
    *,
    xdg: Path | None = None,
    fake_bin: Path | None = None,
    extra_env: dict[str, str] | None = None,
    override: str = "",
) -> subprocess.CompletedProcess[str]:
    env = {name: value for name, value in os.environ.items() if name not in {"COPILOT_HOME", "XDG_CONFIG_HOME"}}
    env.update({"HOME": str(home), "SHELL": "/bin/bash", "PYTHONDONTWRITEBYTECODE": "1"})
    path = [str(tools_path(home)), "/usr/bin", "/bin"]
    if fake_bin is not None:
        path.insert(0, str(fake_bin))
    env["PATH"] = os.pathsep.join(path)
    if xdg is not None:
        env["XDG_CONFIG_HOME"] = str(xdg)
    if extra_env is not None:
        env.update(extra_env)
    script = (
        "set -eu\n"
        f"ROOT={json.dumps(str(ROOT))}\n"
        f". {json.dumps(str(ROOT / 'scripts/setup/common.sh'))}\n"
        f". {json.dumps(str(ROOT / 'scripts/setup/copilot.sh'))}\n"
        f"{override}\n"
        f"{mode}_copilot_integration\n"
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=False, env=env)


def prepare_home(home: Path, *, copilot_home: bool = True) -> tuple[Path, dict[Path, bytes]]:
    os.symlink(ROOT, home / ".agents")
    if copilot_home:
        (home / ".copilot").mkdir()
    xdg = home / "xdg"
    originals = {
        home / ".bash_profile": b"export BASH_PROFILE_SETTING=keep\n",
        home / ".bashrc": b"export BASHRC_SETTING=keep\n",
        home / ".zshenv": b"export ZSHENV_SETTING=keep\n",
        home / ".zprofile": b"export ZPROFILE_SETTING=keep\n",
        home / ".zshrc": b"export ZSHRC_SETTING=keep\n",
        xdg / "fish/config.fish": b"set -gx FISH_SETTING keep\n",
    }
    for path, content in originals.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content + LEGACY_BLOCK.encode())
    (home / ".zshrc").chmod(0o640)
    return xdg, originals


def instructions_link(home: Path) -> Path:
    return home / ".copilot/copilot-instructions.md"


def assert_link(home: Path) -> None:
    link = instructions_link(home)
    if not link.is_symlink() or os.readlink(link) != str(home / ".agents/AGENTS.md"):
        fail("Copilot instructions link is missing or points elsewhere")
    if not link.resolve().samefile(ROOT / "AGENTS.md"):
        fail("Copilot instructions link does not resolve to the canonical AGENTS.md")


def assert_profiles_cleaned(originals: dict[Path, bytes]) -> None:
    for path, content in originals.items():
        if path.read_bytes() != content:
            fail(f"legacy Copilot block was not removed cleanly: {path}")


def assert_profiles_untouched(originals: dict[Path, bytes]) -> None:
    for path, content in originals.items():
        if path.read_bytes() != content + LEGACY_BLOCK.encode():
            fail(f"failed setup changed a shell profile: {path}")


def state_digest(path: Path) -> tuple:
    if not os.path.lexists(path):
        return ("absent",)
    metadata = path.lstat()
    mode = metadata.st_mode & 0o7777
    if path.is_symlink():
        return ("symlink", mode, os.readlink(path))
    if path.is_file():
        return ("file", mode, path.read_bytes())
    if path.is_dir():
        return (
            "directory",
            mode,
            tuple(
                (entry.name, state_digest(entry))
                for entry in sorted(path.iterdir(), key=lambda item: os.fsencode(item.name))
            ),
        )
    return ("other", mode)


def watched_paths(home: Path) -> tuple[Path, ...]:
    copilot = home / ".copilot"
    return (
        home / ".local/share/hard-eng/copilot-context-mode-source",
        copilot / "config.json",
        copilot / "installed-plugins",
        copilot / "settings.json",
        copilot / "hooks/hard-eng.json",
        copilot / "mcp-config.json",
        copilot / "copilot-instructions.md",
    )


def check_jsonc_settings() -> None:
    eof_comment = subprocess.run(
        ["python3", "-c", "from jsonc import loads; assert loads('{} // final comment') == {}"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT / "scripts/setup")},
    )
    if eof_comment.returncode:
        fail(eof_comment.stderr.strip() or "valid final JSONC line comment was rejected")
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-settings-") as temporary:
        settings = Path(temporary) / "settings.json"
        settings.write_text(
            '{\n  // preserve this comment\n  "enabledPlugins": {}, // preserve this comment too\n}\n', encoding="utf-8"
        )
        environment = {**os.environ, "COPILOT_SETTINGS": str(settings), "PYTHONDONTWRITEBYTECODE": "1"}
        installed = subprocess.run(
            ["python3", str(SETTINGS_TOOL), "install"], capture_output=True, text=True, check=False, env=environment
        )
        if installed.returncode:
            fail(installed.stderr.strip() or "Copilot JSONC settings convergence failed")
        content = settings.read_text(encoding="utf-8")
        if (
            "// preserve this comment" not in content
            or "// preserve this comment too" not in content
            or '"enabledPlugins": {}, // preserve this comment too\n  "includeCoAuthoredBy": false' not in content
            or "\n,\n" in content
        ):
            fail("Copilot JSONC settings convergence did not preserve structure")
        checked = subprocess.run(
            ["python3", str(SETTINGS_TOOL), "check"], capture_output=True, text=True, check=False, env=environment
        )
        if checked.returncode:
            fail("Copilot JSONC settings check rejected converged state")


def check_plugin_failure_leaves_no_state() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-failure-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        result = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin, extra_env={"FAKE_COPILOT_FAIL": "1"})
        if result.returncode == 0:
            fail("Copilot plugin failure was accepted")
        assert_profiles_untouched(originals)
        if (home / ".local/share/hard-eng/copilot-context-mode-source").exists():
            fail("plugin failure left a newly synchronized source tree")
        if os.path.lexists(instructions_link(home)):
            fail("plugin failure left an instructions link behind")


def check_late_failure_rolls_back_every_copilot_stage() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-transaction-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        copilot = home / ".copilot"
        cache = copilot / "installed-plugins/user-owned"
        cache.mkdir(parents=True)
        (cache / "keep.txt").write_text("keep\n", encoding="utf-8")
        (copilot / "config.json").write_text('{"unrelated":true}\n', encoding="utf-8")
        (copilot / "settings.json").write_text('// keep\n{"unrelated":true}\n', encoding="utf-8")
        (copilot / "hooks").mkdir()
        (copilot / "hooks/hard-eng.json").write_text('{"unrelated":true}\n', encoding="utf-8")
        before = {path: state_digest(path) for path in watched_paths(home)}
        result = run_owner(
            home, "install", xdg=xdg, fake_bin=fake_bin, override="copilot_instructions_tool() { return 73; }"
        )
        if result.returncode == 0:
            fail("injected late Copilot stage failure was accepted")
        if {path: state_digest(path) for path in watched_paths(home)} != before:
            fail("late Copilot failure did not restore every earlier stage")
        assert_profiles_untouched(originals)


def check_plugin_failure_after_write_rolls_back() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-plugin-late-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        before = {path: state_digest(path) for path in watched_paths(home)}
        result = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin, extra_env={"FAKE_COPILOT_FAIL_AFTER": "1"})
        if result.returncode == 0:
            fail("Copilot plugin failure after writes was accepted")
        if {path: state_digest(path) for path in watched_paths(home)} != before:
            fail("Copilot plugin failure after writes was not rolled back")
        assert_profiles_untouched(originals)


def check_copilot_concurrent_edit_is_preserved() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-concurrent-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        result = run_owner(
            home,
            "install",
            xdg=xdg,
            fake_bin=fake_bin,
            override=(
                "copilot_instructions_tool() { "
                "printf '%s\\n' '{\"user\":true}' >\"$COPILOT_DIR/settings.json\"; "
                "return 73; }"
            ),
        )
        settings = home / ".copilot/settings.json"
        if result.returncode == 0:
            fail("Copilot concurrent-edit rollback was accepted")
        if settings.read_text(encoding="utf-8") != '{"user":true}\n':
            fail("Copilot rollback overwrote a concurrent settings edit")
        if "rollback incomplete" not in result.stderr:
            fail("Copilot concurrent edit did not report preserved recovery state")


def check_convergence() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        first = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin)
        if first.returncode:
            fail(first.stderr.strip() or "Copilot convergence failed")
        if "setup:copilot: PASS updated" not in first.stdout:
            fail("Copilot instructions convergence did not report the cleaned profiles")
        assert_link(home)
        assert_profiles_cleaned(originals)
        if (home / ".zshrc").stat().st_mode & 0o777 != 0o640:
            fail("Copilot convergence changed an existing profile mode")
        settings = home / ".copilot/settings.json"
        if '"includeCoAuthoredBy": false' not in settings.read_text(encoding="utf-8"):
            fail("Copilot no-authorship setting was not converged")
        mcp_config = json.loads((home / ".copilot/mcp-config.json").read_text(encoding="utf-8"))
        if mcp_config["mcpServers"]["codebase-memory"]["command"] != f"{home}/.local/bin/codebase-memory-mcp":
            fail("Copilot MCP registration was not converged")
        before = {path: state_digest(path) for path in (*originals, *watched_paths(home))}
        second = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin)
        checked = run_owner(home, "check", xdg=xdg, fake_bin=fake_bin)
        if second.returncode or checked.returncode:
            fail("Copilot rerun/check failed on converged state")
        if "setup:copilot: PASS unchanged" not in second.stdout:
            fail("Copilot rerun did not report unchanged instructions")
        if {path: state_digest(path) for path in (*originals, *watched_paths(home))} != before:
            fail("Copilot rerun/check did not preserve converged state")


def check_complete_plugin_tree_and_links() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-tree-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        installed = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin)
        if installed.returncode:
            fail(installed.stderr.strip() or "Copilot tree fixture did not install")
        config = json.loads((home / ".copilot/config.json").read_text(encoding="utf-8"))
        cache = Path(config["installedPlugins"][0]["cache_path"])
        extra = cache / "unlisted.txt"
        extra.write_text("drift\n", encoding="utf-8")
        drift = run_owner(home, "check", xdg=xdg, fake_bin=fake_bin)
        if drift.returncode == 0:
            fail("Copilot plugin check ignored an extra cache file")
        extra.unlink()
        skills = cache / "skills"
        shutil.rmtree(skills)
        skills.symlink_to(
            home / ".local/share/hard-eng/copilot-context-mode-source/context-mode/skills", target_is_directory=True
        )
        linked = run_owner(home, "check", xdg=xdg, fake_bin=fake_bin)
        if linked.returncode == 0:
            fail("Copilot plugin check followed an intermediate cache symlink")


def check_skip_without_copilot() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-skip-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home, copilot_home=False)
        result = run_owner(home, "install", xdg=xdg)
        checked = run_owner(home, "check", xdg=xdg)
        if result.returncode or checked.returncode:
            fail("Copilot owner did not skip a machine without the Copilot CLI")
        if SKIPPED not in result.stdout or SKIPPED not in checked.stdout:
            fail("Copilot skip did not report the exact reason")
        if (home / ".copilot").exists():
            fail("Copilot skip created the Copilot home")
        assert_profiles_untouched(originals)


def check_missing_home_is_created() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-home-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home, copilot_home=False)
        fake_bin = prepare_copilot_tools(home)
        early = run_owner(home, "check", xdg=xdg, fake_bin=fake_bin)
        if early.returncode == 0 or "Copilot home is missing" not in early.stderr:
            fail("Copilot check accepted a missing Copilot home")
        if (home / ".copilot").exists():
            fail("Copilot check created the Copilot home")
        installed = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin)
        if installed.returncode:
            fail(installed.stderr.strip() or "Copilot install did not create the missing home")
        assert_link(home)
        assert_profiles_cleaned(originals)
        if run_owner(home, "check", xdg=xdg, fake_bin=fake_bin).returncode:
            fail("Copilot check failed after creating the home")


def check_check_is_read_only() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-check-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        if run_owner(home, "install", xdg=xdg, fake_bin=fake_bin).returncode:
            fail("Copilot read-only fixture did not install")
        instructions_link(home).unlink()
        before = {path: state_digest(path) for path in watched_paths(home)}
        result = run_owner(home, "check", xdg=xdg, fake_bin=fake_bin)
        if result.returncode == 0:
            fail("Copilot check accepted a missing instructions link")
        if {path: state_digest(path) for path in watched_paths(home)} != before:
            fail("Copilot check mutated state")


def check_conflicts() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-conflict-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        link = instructions_link(home)
        link.symlink_to(home / "elsewhere.md")
        foreign = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin)
        if foreign.returncode == 0 or "has another owner" not in foreign.stderr:
            fail("foreign Copilot instructions link was replaced")
        if os.readlink(link) != str(home / "elsewhere.md"):
            fail("foreign Copilot instructions link was changed")
        assert_profiles_untouched(originals)
        link.unlink()
        link.write_text("mine\n", encoding="utf-8")
        owned = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin)
        if owned.returncode == 0 or "move it aside" not in owned.stderr:
            fail("user-owned Copilot instructions file was replaced")
        if link.read_text(encoding="utf-8") != "mine\n":
            fail("user-owned Copilot instructions file was changed")
        link.unlink()
        (home / ".zshrc").write_bytes(originals[home / ".zshrc"] + START.encode() + b"\n")
        malformed = run_owner(home, "install", xdg=xdg, fake_bin=fake_bin)
        if malformed.returncode == 0 or "malformed legacy Copilot markers" not in malformed.stderr:
            fail("malformed legacy Copilot markers were accepted")
        if os.path.lexists(link):
            fail("malformed legacy markers left an instructions link behind")
        (home / ".zshrc").write_bytes(originals[home / ".zshrc"] + LEGACY_BLOCK.encode())
        if run_owner(home, "install", xdg=xdg, fake_bin=fake_bin).returncode:
            fail("Copilot install did not recover after the markers were repaired")
        assert_profiles_cleaned(originals)
        (home / ".bashrc").write_bytes(originals[home / ".bashrc"] + LEGACY_BLOCK.encode())
        stale = run_owner(home, "check", xdg=xdg, fake_bin=fake_bin)
        if stale.returncode == 0 or "legacy Copilot instruction block remains" not in stale.stderr:
            fail("Copilot check accepted a returning legacy profile block")
        if run_owner(home, "install", xdg=xdg, fake_bin=fake_bin).returncode:
            fail("Copilot install did not remove a returning legacy profile block")
        assert_profiles_cleaned(originals)


def main() -> int:
    check_jsonc_settings()
    check_plugin_failure_leaves_no_state()
    check_plugin_failure_after_write_rolls_back()
    check_late_failure_rolls_back_every_copilot_stage()
    check_copilot_concurrent_edit_is_preserved()
    check_convergence()
    check_complete_plugin_tree_and_links()
    check_skip_without_copilot()
    check_missing_home_is_created()
    check_check_is_read_only()
    check_conflicts()
    print("setup-copilot-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
