#!/usr/bin/env python3
"""Behavior contracts for Codex setup convergence."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTEXT = json.loads(
    (ROOT / "scripts/setup/manifest.json").read_text(encoding="utf-8")
)["codex"]["context_mode"]
COMMIT = CONTEXT["marketplace_commit"]
VERSION = CONTEXT["version"]
OLD_COMMIT = "0" * 40


def fail(message: str) -> None:
    raise SystemExit(f"setup-codex-contract: FAIL: {message}")


def prepare_fake_tools(home: Path) -> tuple[Path, Path]:
    fake_bin = home / "fake-bin"
    state = home / "fake-codex-state"
    fake_bin.mkdir()
    state.mkdir()
    (state / "root").mkdir()
    codex = fake_bin / "codex"
    codex.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        'state=$FAKE_CODEX_STATE\n'
        'mkdir -p "$HOME/.codex/tmp/arg0"\n'
        'touch "$HOME/.codex/tmp/arg0"\n'
        'source_url=https://github.com/mksglu/context-mode.git\n'
        '[ ! -f "$state/conflict" ] || source_url=https://example.invalid/other.git\n'
        'case "$1:$2:${3:-}" in\n'
        "  plugin:marketplace:list)\n"
        '    if [ -f "$state/marketplace" ]; then\n'
        '      printf \'{"marketplaces":[{"name":"context-mode","root":"%s/root","marketplaceSource":{"sourceType":"git","source":"%s"}}]}\\n\' "$state" "$source_url"\n'
        "    else\n"
        "      printf '%s\\n' '{\"marketplaces\":[]}'\n"
        "    fi\n"
        "    ;;\n"
        "  plugin:marketplace:add)\n"
        '    if [ -f "$state/marketplace" ] && [ -f "$state/drift" ]; then\n'
        "      printf '%s\\n' \"Error: marketplace 'context-mode' is already added from a different source; remove it before adding this source\" >&2\n"
        "      exit 96\n"
        "    fi\n"
        '    printf "%s\\n" marketplace-add >>"$state/log"\n'
        '    : >"$state/marketplace"\n'
        f'    case " $* " in *" --ref {OLD_COMMIT} "*) : >"$state/drift" ;; *) /bin/rm -f "$state/drift" ;; esac\n'
        "    printf '%s\\n' '{}'\n"
        "    ;;\n"
        "  plugin:marketplace:remove)\n"
        '    printf "%s\\n" marketplace-remove >>"$state/log"\n'
        '    /bin/rm -f "$state/marketplace" "$state/plugin"\n'
        "    printf '%s\\n' '{}'\n"
        "    ;;\n"
        "  plugin:list:--json)\n"
        '    if [ -f "$state/plugin" ]; then\n'
        f'      printf \'{{"installed":[{{"pluginId":"context-mode@context-mode","marketplaceName":"context-mode","version":"{VERSION}","installed":true,"enabled":true,"marketplaceSource":{{"sourceType":"git","source":"%s"}}}}]}}\\n\' "$source_url"\n'
        "    else\n"
        "      printf '%s\\n' '{\"installed\":[]}'\n"
        "    fi\n"
        "    ;;\n"
        "  plugin:add:context-mode@context-mode)\n"
        '    printf "%s\\n" plugin-add >>"$state/log"\n'
        '    if [ -f "$state/fail-plugin-add" ]; then\n'
        '      /bin/rm -f "$state/fail-plugin-add"\n'
        "      exit 97\n"
        "    fi\n"
        '    : >"$state/plugin"\n'
        "    printf '%s\\n' '{}'\n"
        "    ;;\n"
        "  plugin:remove:context-mode@context-mode)\n"
        '    printf "%s\\n" plugin-remove >>"$state/log"\n'
        '    /bin/rm -f "$state/plugin"\n'
        "    printf '%s\\n' '{}'\n"
        "    ;;\n"
        "  *) printf 'unexpected fake codex args: %s\\n' \"$*\" >&2; exit 98 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    codex.chmod(0o755)
    git = fake_bin / "git"
    git.write_text(
        "#!/bin/sh\n"
        "set -eu\n"
        f'[ ! -f "$FAKE_CODEX_STATE/drift" ] || {{ printf "%s\\n" {OLD_COMMIT}; exit; }}\n'
        f"printf '%s\\n' {COMMIT}\n",
        encoding="utf-8",
    )
    git.chmod(0o755)
    return fake_bin, state


def run_install(home: Path, fake_bin: Path, state: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "PATH": f"{fake_bin}:{env['PATH']}",
        "FAKE_CODEX_STATE": str(state),
    })
    script = (
        "set -eu\n"
        f"ROOT={shlex.quote(str(ROOT))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/common.sh'))}\n"
        f". {shlex.quote(str(ROOT / 'scripts/setup/codex.sh'))}\n"
        "install_codex_integration\n"
    )
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def prepare_home(home: Path) -> tuple[Path, Path]:
    os.symlink(ROOT, home / ".agents")
    return prepare_fake_tools(home)


def check_fresh_and_rerun() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-codex-fresh-") as temporary:
        home = Path(temporary)
        fake_bin, state = prepare_home(home)
        first = run_install(home, fake_bin, state)
        if first.returncode:
            fail(first.stderr.strip() or "fresh Codex convergence failed")
        agents = home / ".codex/AGENTS.md"
        if not agents.is_symlink() or os.readlink(agents) != str(home / ".agents/AGENTS.md"):
            fail("fresh Codex convergence did not create the canonical symlink")
        expected_log = "marketplace-add\nplugin-add\n"
        if (state / "log").read_text(encoding="utf-8") != expected_log:
            fail("fresh Codex convergence did not use official add commands once")
        arg0 = home / ".codex/tmp/arg0"
        arg0.mkdir(parents=True, exist_ok=True)
        os.utime(arg0, ns=(1_700_000_000_000_000_000,) * 2)
        before_mtime = arg0.stat().st_mtime_ns
        second = run_install(home, fake_bin, state)
        if second.returncode:
            fail(second.stderr.strip() or "Codex rerun failed")
        if (state / "log").read_text(encoding="utf-8") != expected_log:
            fail("Codex rerun repeated official mutations")
        if arg0.stat().st_mtime_ns != before_mtime:
            fail("Codex read-only state probe touched the active home")


def check_conflicts() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-codex-link-conflict-") as temporary:
        home = Path(temporary)
        fake_bin, state = prepare_home(home)
        codex_dir = home / ".codex"
        codex_dir.mkdir()
        agents = codex_dir / "AGENTS.md"
        agents.write_text("user-owned\n", encoding="utf-8")
        result = run_install(home, fake_bin, state)
        if result.returncode == 0 or agents.read_text(encoding="utf-8") != "user-owned\n":
            fail("user-owned Codex AGENTS.md conflict was not preserved")
        if (state / "log").exists():
            fail("instruction conflict mutated plugin state")

    with tempfile.TemporaryDirectory(prefix="hard-eng-codex-source-conflict-") as temporary:
        home = Path(temporary)
        fake_bin, state = prepare_home(home)
        (state / "marketplace").touch()
        (state / "conflict").touch()
        result = run_install(home, fake_bin, state)
        if result.returncode == 0:
            fail("foreign Context Mode marketplace source was accepted")
        if (home / ".codex/AGENTS.md").exists() or (state / "log").exists():
            fail("marketplace source conflict caused partial mutation")


def check_marketplace_repin_refreshes_plugin() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-codex-repin-") as temporary:
        home = Path(temporary)
        fake_bin, state = prepare_home(home)
        (state / "marketplace").touch()
        (state / "plugin").touch()
        (state / "drift").touch()
        result = run_install(home, fake_bin, state)
        if result.returncode:
            fail(result.stderr.strip() or "marketplace repin failed")
        expected_log = "marketplace-remove\nmarketplace-add\nplugin-add\n"
        if (state / "log").read_text(encoding="utf-8") != expected_log:
            fail("marketplace repin did not refresh the installed plugin")


def check_failed_repin_rollback() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-codex-repin-rollback-") as temporary:
        home = Path(temporary)
        fake_bin, state = prepare_home(home)
        for marker in ("marketplace", "plugin", "drift", "fail-plugin-add"):
            (state / marker).touch()
        result = run_install(home, fake_bin, state)
        if result.returncode == 0:
            fail("injected repin plugin failure passed")
        if not all((state / marker).exists() for marker in ("marketplace", "plugin", "drift")):
            fail("failed repin did not restore the previous marketplace and plugin")
        expected_log = (
            "marketplace-remove\n"
            "marketplace-add\n"
            "plugin-add\n"
            "marketplace-remove\n"
            "marketplace-add\n"
            "plugin-add\n"
        )
        if (state / "log").read_text(encoding="utf-8") != expected_log:
            fail("failed repin did not restore through official commands")


def check_failed_plugin_rollback() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-codex-rollback-") as temporary:
        home = Path(temporary)
        fake_bin, state = prepare_home(home)
        (state / "fail-plugin-add").touch()
        result = run_install(home, fake_bin, state)
        if result.returncode == 0:
            fail("injected plugin install failure passed")
        if (home / ".codex/AGENTS.md").exists():
            fail("failed plugin install left a new instruction symlink")
        if (state / "marketplace").exists() or (state / "plugin").exists():
            fail("failed plugin install left new plugin state")


def main() -> int:
    check_fresh_and_rerun()
    check_conflicts()
    check_marketplace_repin_refreshes_plugin()
    check_failed_repin_rollback()
    check_failed_plugin_rollback()
    print("setup-codex-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
