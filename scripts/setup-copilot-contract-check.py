#!/usr/bin/env python3
"""Behavior contracts for global Copilot instruction discovery."""

from __future__ import annotations

import json
import fcntl
import os
import shutil
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
SETTINGS_TOOL = ROOT / "scripts/setup/copilot-settings.py"
START = "# >>> hard-eng managed Copilot instructions >>>"
END = "# <<< hard-eng managed Copilot instructions <<<"
VARIABLE = "COPILOT_CUSTOM_INSTRUCTIONS_DIRS"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-copilot-contract: FAIL: {message}")


def context_version() -> str:
    manifest = json.loads(
        (ROOT / "scripts/setup/manifest.json").read_text(encoding="utf-8")
    )
    return manifest["codex"]["context_mode"]["version"]


def prepare_copilot_tools(home: Path) -> Path:
    source = (
        home
        / ".local/share/hard-eng/npm-runtime/node_modules/context-mode/configs/copilot-cli"
    )
    (source / ".github/plugin").mkdir(parents=True)
    (source / "skills/context-mode").mkdir(parents=True)
    (source / ".github/plugin/plugin.json").write_text(
        json.dumps(
            {
                "name": "context-mode",
                "version": context_version(),
                "skills": ["./skills/context-mode"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source / ".mcp.json").write_text(
        '{"mcpServers":{"context-mode":{"command":"context-mode"}}}\n',
        encoding="utf-8",
    )
    (source / "hooks.json").write_text(
        '{"version":1,"hooks":{"sessionStart":[]}}\n',
        encoding="utf-8",
    )
    (source / "skills/context-mode/SKILL.md").write_text(
        "---\nname: context-mode\ndescription: test\n---\n",
        encoding="utf-8",
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


def run_owner(
    home: Path,
    mode: str,
    shell: str,
    *,
    xdg: Path | None = None,
    path_prefix: Path | None = None,
    extra_env: dict[str, str] | None = None,
    override: str = "",
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(home),
        "SHELL": f"/bin/{shell}",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if xdg is None:
        env.pop("XDG_CONFIG_HOME", None)
    else:
        env["XDG_CONFIG_HOME"] = str(xdg)
    if path_prefix is not None:
        env["PATH"] = f"{path_prefix}:{env['PATH']}"
    if extra_env is not None:
        env.update(extra_env)
    script = (
        "set -eu\n"
        f"ROOT={shlex.quote(str(ROOT))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/common.sh'))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/copilot.sh'))}\n"
        f"{override}\n"
        f"{mode}_copilot_integration\n"
    )
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def prepare_home(home: Path) -> tuple[Path, dict[Path, bytes]]:
    os.symlink(ROOT, home / ".agents")
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
        path.write_bytes(content)
    (home / ".zshrc").chmod(0o640)
    return xdg, originals


def target_profiles(home: Path, xdg: Path) -> tuple[Path, ...]:
    return (
        home / ".bash_profile",
        home / ".bashrc",
        home / ".zshenv",
        home / ".zprofile",
        home / ".zshrc",
        xdg / "fish/config.fish",
    )


def check_rendered(home: Path, xdg: Path, originals: dict[Path, bytes]) -> None:
    for path in target_profiles(home, xdg):
        content = path.read_text(encoding="utf-8")
        if content.count(START) != 1 or content.count(END) != 1:
            fail(f"Copilot markers missing or duplicated: {path}")
        expected = (
            f'set -gx {VARIABLE} "$HOME/.agents"\n'
            if path.name == "config.fish"
            else f'export {VARIABLE}="$HOME/.agents"\n'
        )
        if expected not in content or originals[path].decode() not in content:
            fail(f"Copilot block changed user content or has the wrong export: {path}")
    if (home / ".zshrc").stat().st_mode & 0o777 != 0o640:
        fail("Copilot convergence changed an existing profile mode")


def check_interpreters(home: Path, xdg: Path) -> None:
    bash_profile = home / ".bash_profile"
    bash = subprocess.run(
        ["bash", "-c", ". \"$1\"; printf '%s' \"$COPILOT_CUSTOM_INSTRUCTIONS_DIRS\"", "--", str(bash_profile)],
        capture_output=True,
        text=True,
        check=False,
        env={"HOME": str(home), "PATH": os.environ["PATH"]},
    )
    if bash.returncode or bash.stdout != str(home / ".agents"):
        fail("Bash did not resolve the canonical Copilot instructions directory")

    zsh = shutil.which("zsh")
    if zsh is not None:
        sourced = subprocess.run(
            [zsh, "-c", ". \"$1\"; printf '%s' \"$COPILOT_CUSTOM_INSTRUCTIONS_DIRS\"", "--", str(home / ".zshrc")],
            capture_output=True,
            text=True,
            check=False,
            env={"HOME": str(home), "PATH": os.environ["PATH"]},
        )
        if sourced.returncode or sourced.stdout != str(home / ".agents"):
            fail("Zsh did not resolve the canonical Copilot instructions directory")

    fish = shutil.which("fish")
    if fish is not None:
        sourced = subprocess.run(
            [fish, "-c", "source $argv[1]; printf '%s' $COPILOT_CUSTOM_INSTRUCTIONS_DIRS", "--", str(xdg / "fish/config.fish")],
            capture_output=True,
            text=True,
            check=False,
            env={"HOME": str(home), "PATH": os.environ["PATH"]},
        )
        if sourced.returncode or sourced.stdout != str(home / ".agents"):
            fail("Fish did not resolve the canonical Copilot instructions directory")


def check_jsonc_settings() -> None:
    eof_comment = subprocess.run(
        [
            "python3", "-c",
            "from jsonc import loads; assert loads('{} // final comment') == {}",
        ],
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
            '{\n  // preserve this comment\n  "enabledPlugins": {}, // preserve this comment too\n}\n',
            encoding="utf-8",
        )
        environment = {
            **os.environ,
            "COPILOT_SETTINGS": str(settings),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        installed = subprocess.run(
            ["python3", str(SETTINGS_TOOL), "install"],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if installed.returncode:
            fail(installed.stderr.strip() or "Copilot JSONC settings convergence failed")
        content = settings.read_text(encoding="utf-8")
        if (
            "// preserve this comment" not in content
            or "// preserve this comment too" not in content
            or '"enabledPlugins": {}, // preserve this comment too\n  "includeCoAuthoredBy": false'
            not in content
            or "\n,\n" in content
        ):
            fail("Copilot JSONC settings convergence did not preserve structure")
        checked = subprocess.run(
            ["python3", str(SETTINGS_TOOL), "check"],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )
        if checked.returncode:
            fail("Copilot JSONC settings check rejected converged state")


def check_plugin_failure_does_not_mutate_profiles() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-failure-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        result = run_owner(
            home,
            "install",
            "bash",
            xdg=xdg,
            path_prefix=fake_bin,
            extra_env={"FAKE_COPILOT_FAIL": "1"},
        )
        if result.returncode == 0:
            fail("Copilot plugin failure was accepted")
        for path, content in originals.items():
            if path.read_bytes() != content:
                fail(f"plugin failure partially changed profile: {path}")
        if (home / ".local/share/hard-eng/copilot-context-mode-source").exists():
            fail("plugin failure left a newly synchronized source tree")


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


def check_late_failure_rolls_back_every_copilot_stage() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-transaction-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        copilot = home / ".copilot"
        config = copilot / "config.json"
        settings = copilot / "settings.json"
        hooks = copilot / "hooks/hard-eng.json"
        cache = copilot / "installed-plugins/user-owned"
        cache.mkdir(parents=True)
        (cache / "keep.txt").write_text("keep\n", encoding="utf-8")
        config.write_text('{"unrelated":true}\n', encoding="utf-8")
        settings.write_text('// keep\n{"unrelated":true}\n', encoding="utf-8")
        hooks.parent.mkdir(parents=True)
        hooks.write_text('{"unrelated":true}\n', encoding="utf-8")
        watched = (
            home / ".local/share/hard-eng/copilot-context-mode-source",
            config,
            copilot / "installed-plugins",
            settings,
            hooks,
        )
        before = {path: state_digest(path) for path in watched}
        result = run_owner(
            home,
            "install",
            "fish",
            xdg=xdg,
            path_prefix=fake_bin,
            override="copilot_profile_tool() { return 73; }",
        )
        if result.returncode == 0:
            fail("injected late Copilot stage failure was accepted")
        after = {path: state_digest(path) for path in watched}
        if after != before:
            fail("late Copilot failure did not restore every earlier stage")
        for path, content in originals.items():
            if path.read_bytes() != content:
                fail(f"late Copilot failure changed profile: {path}")


def check_plugin_failure_after_write_rolls_back() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-plugin-late-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        watched = (
            home / ".local/share/hard-eng/copilot-context-mode-source",
            home / ".copilot/config.json",
            home / ".copilot/installed-plugins",
            home / ".copilot/settings.json",
            home / ".copilot/hooks/hard-eng.json",
        )
        before = {path: state_digest(path) for path in watched}
        result = run_owner(
            home,
            "install",
            "bash",
            xdg=xdg,
            path_prefix=fake_bin,
            extra_env={"FAKE_COPILOT_FAIL_AFTER": "1"},
        )
        if result.returncode == 0:
            fail("Copilot plugin failure after writes was accepted")
        if {path: state_digest(path) for path in watched} != before:
            fail("Copilot plugin failure after writes was not rolled back")
        for path, content in originals.items():
            if path.read_bytes() != content:
                fail(f"late plugin failure changed profile: {path}")


def check_copilot_concurrent_edit_is_preserved() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-concurrent-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        result = run_owner(
            home,
            "install",
            "bash",
            xdg=xdg,
            path_prefix=fake_bin,
            override=(
                "copilot_profile_tool() { "
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
        first = run_owner(home, "install", "fish", xdg=xdg, path_prefix=fake_bin)
        if first.returncode:
            fail(first.stderr.strip() or "Copilot profile convergence failed")
        check_rendered(home, xdg, originals)
        check_interpreters(home, xdg)
        settings = home / ".copilot/settings.json"
        if '"includeCoAuthoredBy": false' not in settings.read_text(encoding="utf-8"):
            fail("Copilot no-authorship setting was not converged")
        before = {
            path: path.read_bytes()
            for path in (*target_profiles(home, xdg), settings, home / ".copilot/config.json")
        }
        modes = {path: path.stat().st_mode & 0o777 for path in target_profiles(home, xdg)}
        second = run_owner(
            home, "install", "fish", xdg=xdg, path_prefix=fake_bin
        )
        checked = run_owner(home, "check", "fish", xdg=xdg, path_prefix=fake_bin)
        after = {
            path: path.read_bytes()
            for path in (*target_profiles(home, xdg), settings, home / ".copilot/config.json")
        }
        if second.returncode or checked.returncode or after != before:
            fail("Copilot rerun/check did not preserve converged state")
        if {path: path.stat().st_mode & 0o777 for path in target_profiles(home, xdg)} != modes:
            fail("Copilot rerun/check changed profile modes")


def check_complete_plugin_tree_and_links() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-tree-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        installed = run_owner(home, "install", "bash", xdg=xdg, path_prefix=fake_bin)
        if installed.returncode:
            fail(installed.stderr.strip() or "Copilot tree fixture did not install")
        config = json.loads((home / ".copilot/config.json").read_text(encoding="utf-8"))
        cache = Path(config["installedPlugins"][0]["cache_path"])
        extra = cache / "unlisted.txt"
        extra.write_text("drift\n", encoding="utf-8")
        drift = run_owner(home, "check", "bash", xdg=xdg, path_prefix=fake_bin)
        if drift.returncode == 0:
            fail("Copilot plugin check ignored an extra cache file")
        extra.unlink()
        skills = cache / "skills"
        shutil.rmtree(skills)
        skills.symlink_to(
            home / ".local/share/hard-eng/copilot-context-mode-source/context-mode/skills",
            target_is_directory=True,
        )
        linked = run_owner(home, "check", "bash", xdg=xdg, path_prefix=fake_bin)
        if linked.returncode == 0:
            fail("Copilot plugin check followed an intermediate cache symlink")


def check_skip_without_copilot() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-skip-") as temporary:
        home = Path(temporary)
        os.symlink(ROOT, home / ".agents")
        result = run_owner(home, "install", "bash")
        checked = run_owner(home, "check", "bash")
        if result.returncode or checked.returncode:
            fail("Copilot owner did not skip a home without .copilot")
        if any((home / name).exists() for name in (".bash_profile", ".bashrc", ".zshenv", ".zprofile", ".zshrc")):
            fail("Copilot skip created shell profiles")


def check_check_is_read_only() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-check-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        for path in target_profiles(home, xdg):
            path.unlink()
        result = run_owner(home, "check", "bash", xdg=xdg, path_prefix=fake_bin)
        if result.returncode == 0 or any(path.exists() for path in target_profiles(home, xdg)):
            fail("Copilot check mutated or accepted missing profiles")


def check_conflicts() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-conflict-") as temporary:
        home = Path(temporary)
        os.symlink(ROOT, home / ".agents")
        (home / ".copilot").mkdir()
        fake_bin = prepare_copilot_tools(home)
        (home / ".copilot/config.json").write_text(
            json.dumps(
                {
                    "installedPlugins": [
                        {
                            "name": "context-mode",
                            "version": context_version(),
                            "enabled": True,
                            "cache_path": str(
                                home / ".copilot/installed-plugins/foreign"
                            ),
                            "source": {
                                "source": "github",
                                "path": "mksglu/context-mode",
                            },
                        }
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )
        result = run_owner(home, "install", "bash", path_prefix=fake_bin)
        if result.returncode == 0:
            fail("foreign Copilot plugin source was overwritten")
        if any(path.exists() for path in target_profiles(home, home / "xdg")):
            fail("Copilot plugin conflict caused partial profile creation")

    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-conflict-") as temporary:
        home = Path(temporary)
        xdg, originals = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        profile = home / ".zshrc"
        original = f'export {VARIABLE}="$HOME/other"\n'
        profile.write_text(original, encoding="utf-8")
        result = run_owner(home, "install", "zsh", xdg=xdg, path_prefix=fake_bin)
        if result.returncode == 0 or profile.read_text(encoding="utf-8") != original:
            fail("foreign Copilot export was overwritten")
        for path, content in originals.items():
            if path != profile and path.read_bytes() != content:
                fail("Copilot conflict caused partial profile mutation")

    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-malformed-") as temporary:
        home = Path(temporary)
        os.symlink(ROOT, home / ".agents")
        (home / ".copilot").mkdir()
        fake_bin = prepare_copilot_tools(home)
        profile = home / ".bash_profile"
        original = f"keep\n{START}\nunclosed\n"
        profile.write_text(original, encoding="utf-8")
        result = run_owner(home, "install", "bash", path_prefix=fake_bin)
        if result.returncode == 0 or profile.read_text(encoding="utf-8") != original:
            fail("malformed Copilot block was overwritten")


def check_lock_conflict() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-copilot-lock-") as temporary:
        home = Path(temporary)
        xdg, _ = prepare_home(home)
        fake_bin = prepare_copilot_tools(home)
        lock = home / ".local/share/hard-eng/.copilot-profile.lock"
        lock.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        before = {path: path.read_bytes() for path in target_profiles(home, xdg)}
        result = run_owner(
            home, "install", "fish", xdg=xdg, path_prefix=fake_bin
        )
        after = {path: path.read_bytes() for path in target_profiles(home, xdg)}
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
        if result.returncode == 0 or after != before:
            fail("active Copilot convergence lock was ignored or caused mutation")
        stale = run_owner(home, "install", "fish", xdg=xdg, path_prefix=fake_bin)
        if stale.returncode != 0:
            fail("released Copilot convergence lock did not recover automatically")


def main() -> int:
    check_jsonc_settings()
    check_plugin_failure_does_not_mutate_profiles()
    check_plugin_failure_after_write_rolls_back()
    check_late_failure_rolls_back_every_copilot_stage()
    check_copilot_concurrent_edit_is_preserved()
    check_convergence()
    check_complete_plugin_tree_and_links()
    check_skip_without_copilot()
    check_check_is_read_only()
    check_conflicts()
    check_lock_conflict()
    print("setup-copilot-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
