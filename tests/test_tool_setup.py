import fcntl
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1]
BUN = """#!{python}
import json, os, sys, time
from pathlib import Path
state = Path({state!r})
if sys.argv[1] == "pm" and sys.argv[2] == "view":
    if (state / "offline").exists():
        raise SystemExit("network unreachable")
    print(json.dumps((state / "latest").read_text().strip()))
    raise SystemExit
target = Path.cwd()
package, version = sys.argv[-1].rsplit("@", 1)
with (state / "adds").open("a") as log:
    log.write(version + "\\n")
time.sleep(float(os.environ.get("FAKE_ADD_SECONDS", "0")))
if (state / "fail").exists():
    raise SystemExit("registry unavailable")
binary = target / "node_modules" / package / "bin/mise"
binary.parent.mkdir(parents=True)
reported = "0.0.0" if (state / "corrupt").exists() else version
binary.write_text(
    "#!/bin/sh\\n"
    f'[ "$1" = --version ] && echo "{{reported}} test" && exit 0\\n'
    '[ "$2" = env ] && echo \\'{{"PATH": ""}}\\'\\n'
    "exit 0\\n"
)
binary.chmod(0o755)
"""
PROVISION = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import tool_setup
tool_setup.provision_tools(
    Path(sys.argv[2]),
    [{"path": ".", "checks": [{"name": "secrets", "command": ["gitleaks"]}]}],
    60,
)
"""


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    state = tmp_path / "registry"
    bin_directory = tmp_path / "bin"
    state.mkdir()
    bin_directory.mkdir()
    (state / "latest").write_text("2026.9.13")
    bun = bin_directory / "bun"
    bun.write_text(BUN.format(python=sys.executable, state=str(state)))
    bun.chmod(0o755)
    return state


def launch(
    tmp_path: Path, add_seconds: float = 0, quick: bool = False
) -> subprocess.Popen[str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("MISE_", "BUN_", "NPM_CONFIG_"))
    }
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            PROVISION,
            str(SOURCE / ".hooks"),
            str(tmp_path),
            *(["--quick"] if quick else []),
        ],
        env={
            **environment,
            "RUNNER_TEMP": str(tmp_path / "runner"),
            "PATH": str(tmp_path / "bin") + os.pathsep + environment["PATH"],
            "FAKE_ADD_SECONDS": str(add_seconds),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def provision(tmp_path: Path, quick: bool = False) -> subprocess.CompletedProcess[str]:
    process = launch(tmp_path, quick=quick)
    output, _ = process.communicate(timeout=60)
    return subprocess.CompletedProcess(process.args, process.returncode, output)


def launchers(tmp_path: Path) -> list[str]:
    return sorted(
        path.name
        for path in (tmp_path / "runner/hard-eng-tools/mise-launcher").iterdir()
        if path.is_dir()
    )


def adds(registry: Path) -> list[str]:
    return (registry / "adds").read_text().split()


def test_unchanged_latest_version_is_installed_once(
    tmp_path: Path, registry: Path
) -> None:
    for _ in range(3):
        assert provision(tmp_path).returncode == 0
    assert adds(registry) == ["2026.9.13"]
    assert launchers(tmp_path) == ["2026.9.13"]


def test_concurrent_checks_share_one_installation(
    tmp_path: Path, registry: Path
) -> None:
    processes = [launch(tmp_path, add_seconds=1) for _ in range(4)]
    for process in processes:
        output, _ = process.communicate(timeout=60)
        assert process.returncode == 0, output
    assert adds(registry) == ["2026.9.13"]
    assert launchers(tmp_path) == ["2026.9.13"]


def test_new_version_replaces_unheld_launchers_only(
    tmp_path: Path, registry: Path
) -> None:
    owned = tmp_path / "runner/hard-eng-tools"
    unrelated = owned / "bun/cache/earlier/pkg"
    unrelated.mkdir(parents=True)
    (registry / "latest").write_text("2026.9.11")
    assert provision(tmp_path).returncode == 0
    with (owned / "mise-launcher/2026.9.11.lock").open("a") as running_check:
        fcntl.flock(running_check, fcntl.LOCK_SH)
        for version in ("2026.9.12", "2026.9.13"):
            (registry / "latest").write_text(version)
            assert provision(tmp_path).returncode == 0
            assert launchers(tmp_path) == ["2026.9.11", version]
    assert provision(tmp_path).returncode == 0
    assert launchers(tmp_path) == ["2026.9.13"]
    assert adds(registry) == ["2026.9.11", "2026.9.12", "2026.9.13"]
    assert unrelated.is_dir()


@pytest.mark.parametrize("marker", ["fail", "corrupt"])
def test_failed_installation_leaves_no_launcher(
    tmp_path: Path, registry: Path, marker: str
) -> None:
    (registry / marker).touch()
    result = provision(tmp_path)
    assert result.returncode != 0
    assert "registry unavailable" in result.stdout or "installation check" in (
        result.stdout
    )
    assert not list((tmp_path / "runner/hard-eng-tools/mise-launcher").glob("[!.]*/"))
    assert not list((tmp_path / "runner/hard-eng-tools/mise-launcher").glob(".*"))
    (registry / marker).unlink()
    assert provision(tmp_path).returncode == 0
    assert launchers(tmp_path) == ["2026.9.13"]


def test_interrupted_installation_is_replaced_cleanly(
    tmp_path: Path, registry: Path
) -> None:
    interrupted = launch(tmp_path, add_seconds=30)
    while not (registry / "adds").exists():
        time.sleep(0.05)
    os.killpg(interrupted.pid, signal.SIGKILL)
    interrupted.wait()
    storage = tmp_path / "runner/hard-eng-tools/mise-launcher"
    assert [path.name[:9] for path in storage.iterdir() if path.is_dir()] == [
        ".staging-"
    ]
    assert provision(tmp_path).returncode == 0
    assert [path.name for path in storage.iterdir() if path.is_dir()] == ["2026.9.13"]


def test_pnpm_era_launcher_folder_is_replaced(tmp_path: Path, registry: Path) -> None:
    import tool_setup

    storage = tmp_path / "runner/hard-eng-tools/mise-launcher"
    old = storage / "2026.9.13/node_modules/@jdxcode/mise/bin/mise"
    old.parent.mkdir(parents=True)
    old.write_text("#!/bin/sh\nexit 0\n")
    assert provision(tmp_path).returncode == 0
    assert adds(registry) == ["2026.9.13"]
    installed = storage / "2026.9.13" / tool_setup.MISE_BINARY
    assert installed.is_file()
    assert not old.exists()
    assert provision(tmp_path).returncode == 0
    assert adds(registry) == ["2026.9.13"]


def test_tools_are_provisioned_outside_a_project_that_pins_bun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    import tool_setup
    from conftest import use_installed_mise
    from gate_config import Group

    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"packageManager": "bun@1.3.0"}')
    use_installed_mise(tmp_path, monkeypatch)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
    native = Mock(return_value=subprocess.CompletedProcess([], 0, '{"PATH": ""}', ""))
    monkeypatch.setattr(subprocess, "run", native)
    react: Group = {
        "path": ".",
        "checks": [{"name": "doctor", "command": ["react-doctor"]}],
    }
    tool_setup.provision_tools(project, [react], 30)
    directories = [Path(call.kwargs["cwd"]) for call in native.call_args_list]
    assert directories == [tmp_path / "runner/hard-eng-tools"] * 2


def test_dead_code_gate_treats_console_script_targets_as_used(tmp_path: Path) -> None:
    import tool_setup

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n[project.scripts]\ndemo = "demo:main"\n'
        'other = "demo.cli:run_app"\n'
    )
    command = ["vulture", "src", "--min-confidence", "60"]
    assert tool_setup.managed_command(command, tmp_path) == [
        "uvx",
        "vulture@latest",
        *command[1:],
        "--ignore-names",
        "main,run_app",
    ]
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    assert tool_setup.managed_command(command, tmp_path)[2:] == command[1:]


def test_quick_check_uses_installed_tools_while_offline(
    tmp_path: Path, registry: Path
) -> None:
    assert provision(tmp_path).returncode == 0
    (registry / "offline").touch()
    assert provision(tmp_path).returncode != 0
    result = provision(tmp_path, quick=True)
    assert result.returncode == 0, result.stdout
    assert adds(registry) == ["2026.9.13"]


def test_quick_check_offline_without_tools_says_to_connect_once(
    tmp_path: Path, registry: Path
) -> None:
    (registry / "offline").touch()
    result = provision(tmp_path, quick=True)
    assert result.returncode != 0
    assert "Tools are not installed yet" in result.stdout
    assert "run the full check" in result.stdout


def test_quick_check_runs_python_scanners_from_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tool_setup

    command = ["ruff", "check"]
    monkeypatch.setattr(sys, "argv", ["hard-eng.py", "check"])
    assert tool_setup.managed_command(command)[:2] == ["uvx", "ruff@latest"]
    monkeypatch.setattr(sys, "argv", ["hard-eng.py", "check", "--quick"])
    assert tool_setup.managed_command(command)[:3] == [
        "uvx",
        "--offline",
        "ruff@latest",
    ]


def test_parallel_scanners_run_the_version_found_once_before_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tool_setup

    calls = tmp_path / "calls.txt"
    uvx = tmp_path / "bin/uvx"
    uvx.parent.mkdir()
    uvx.write_text(
        "#!/bin/sh\n"
        f'echo "$*" >> {calls}\n'
        'for a in "$@"; do case "$a" in *@latest) echo "${a%@latest} 9.9.9";; esac; done\n'
    )
    uvx.chmod(0o755)
    monkeypatch.setenv("PATH", f"{uvx.parent}:{os.environ['PATH']}")
    monkeypatch.setattr(sys, "argv", ["hard-eng.py", "check"])
    monkeypatch.setattr(tool_setup, "SCANNER_VERSIONS", {})
    tool_setup.pin_python_scanners(["ruff", "semgrep"], 30)
    assert calls.read_text().splitlines() == [
        "ruff@latest --version",
        "semgrep@latest --version",
    ]
    assert tool_setup.managed_command(["ruff", "check"])[:2] == ["uvx", "ruff@9.9.9"]


def test_configured_uvx_scanners_are_pinned_like_bare_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tool_setup
    from gate_config import Group

    pinned: list[str] = []

    def pin(names: list[str], timeout: float) -> None:
        del timeout
        pinned.extend(names)

    def batch(selected: list[str], timeout: float) -> None:
        del selected, timeout

    monkeypatch.setattr(tool_setup, "pin_python_scanners", pin)
    monkeypatch.setattr(tool_setup, "provision_batch", batch)
    monkeypatch.setattr(tool_setup, "SCANNER_VERSIONS", {"ruff": "9.9.9"})
    monkeypatch.setattr(sys, "argv", ["hard-eng.py", "check"])
    command = ["uvx", "ruff@latest", "check", "src"]
    group: Group = {"path": ".", "checks": [{"name": "lint", "command": command}]}
    tool_setup.provision_tools(tmp_path, [group], 30)
    assert pinned == ["ruff"]
    assert tool_setup.managed_command(command) == ["uvx", "ruff@9.9.9", "check", "src"]


@pytest.mark.parametrize(
    ("tool", "installed", "runtime"),
    [
        ("node_modules/vite/bin/vite.js", ("bun", "node"), "bun"),
        ("node_modules/wrangler/bin/wrangler.js", ("bun", "node"), "node"),
        ("node_modules/.bin/wrangler", ("bun", "node"), "node"),
        ("node_modules/miniflare/dist/src/index.js", ("bun", "node"), "node"),
        ("node_modules/wrangler/bin/wrangler.js", ("bun",), "bun"),
    ],
)
def test_node_runs_on_bun_except_for_cloudflare_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    installed: tuple[str, ...],
    runtime: str,
) -> None:
    """Under Bun, miniflare's typegen fetch reaches a real parked domain, not workerd."""
    import tool_setup

    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    for name in installed:
        (bin_directory / name).write_text(f'#!/bin/sh\necho {name} "$@"\n')
        (bin_directory / name).chmod(0o755)
    environment = {"PATH": f"{bin_directory}{os.pathsep}/usr/bin{os.pathsep}/bin"}
    monkeypatch.setenv("PATH", environment["PATH"])
    tool_setup.bun_node(tmp_path / "storage", environment)
    shim = Path(str(shutil.which("node", path=environment["PATH"])))
    for path in (environment["PATH"], os.environ["PATH"]):
        assert shutil.which("node", path=path) == str(shim)
    ran = subprocess.run([shim, tool], capture_output=True, text=True, check=True)
    assert ran.stdout.split() == [runtime, tool]


def test_node_with_a_script_on_stdin_runs_it_on_bun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bare `bun` prints its help and exits 0, so `node <<EOF` scripts passed unrun."""
    import tool_setup

    bun = tmp_path / "bin/bun"
    bun.parent.mkdir()
    bun.write_text('#!/bin/sh\necho bun "$@"\ncat\nexit 3\n')
    bun.chmod(0o755)
    environment = {"PATH": f"{bun.parent}{os.pathsep}/usr/bin{os.pathsep}/bin"}
    monkeypatch.setenv("PATH", environment["PATH"])
    tool_setup.bun_node(tmp_path / "storage", environment)
    shim = Path(str(shutil.which("node", path=environment["PATH"])))
    ran = subprocess.run(
        [shim], input="process.exit(3)", capture_output=True, text=True, check=False
    )
    assert (ran.returncode, ran.stdout) == (3, "bun -\nprocess.exit(3)\n")
    empty = subprocess.run([shim], input="", capture_output=True, text=True, check=True)
    assert empty.stdout == ""
    flagged = subprocess.run(
        [shim, "--input-type=module"],
        input="process.exit(3)",
        capture_output=True,
        text=True,
        check=False,
    )
    assert flagged.stdout == "bun --input-type=module -\nprocess.exit(3)\n"
    for flag in ("-r", "--require", "--import", "--loader"):
        valued = subprocess.run(
            [shim, flag, "node:fs"],
            input="process.exit(3)",
            capture_output=True,
            text=True,
            check=False,
        )
        assert (valued.returncode, valued.stdout) == (
            3,
            f"bun {flag} node:fs -\nprocess.exit(3)\n",
        )
    for own in (["-e", "1"], ["-eprocess.exit(3)"], ["-p1+1"], ["app.js"], ["-"]):
        named = subprocess.run(
            [shim, *own], input="", capture_output=True, text=True, check=False
        )
        assert named.stdout == f"bun {' '.join(own)}\n"


def test_missing_bun_names_how_to_install_it(tmp_path: Path) -> None:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("MISE_", "BUN_", "NPM_CONFIG_"))
    }
    result = subprocess.run(
        [sys.executable, "-c", PROVISION, str(SOURCE / ".hooks"), str(tmp_path)],
        env={
            **environment,
            "RUNNER_TEMP": str(tmp_path / "runner"),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode != 0
    assert "oven-sh/setup-bun" in result.stderr


def test_tool_dependencies_stay_off_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tool_setup

    tool = tmp_path / "data/installs/npm-react-doctor/latest"
    (tool / "bin").mkdir(parents=True)
    (tool / "node_modules/.bin").mkdir(parents=True)
    monkeypatch.setenv("PATH", "/usr/bin")
    paths = [str(tool / "node_modules/.bin"), str(tool / "bin"), "/usr/bin"]
    tool_setup.export_tool_paths(
        '{"PATH": "' + os.pathsep.join(paths) + '"}', tmp_path / "data"
    )
    exported = os.environ["PATH"].split(os.pathsep)
    assert str(tool / "bin") in exported
    assert str(tool / "node_modules/.bin") not in exported


SHIM_PATH = (
    PROVISION
    + """import shutil
node = shutil.which("node")
print("shim:" + node)
print(Path(node).read_text(), end="")
"""
)


def test_checkouts_on_different_revisions_keep_their_own_shims(
    tmp_path: Path, registry: Path
) -> None:
    """Two checkouts once rewrote one shared node shim, so a running check ran the other's."""
    old = tmp_path / "tmp/hard-eng-tools"
    (old / "bun-node").mkdir(parents=True)
    (old / "bun-node/node").write_text("#!/bin/sh\nexit 0\n")
    old_launcher = old / "mise-launcher/2026.9.13/node_modules"
    shutil.copytree(SOURCE / ".hooks", tmp_path / "a/.hooks")
    shutil.copytree(SOURCE / ".hooks", tmp_path / "b/.hooks")
    other = tmp_path / "b/.hooks/tool_setup.py"
    other.write_text(
        other.read_text().replace(
            'script = "#!/bin/sh\\n"', 'script = "#!/bin/sh\\n# other revision\\n"'
        )
    )
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("MISE_", "BUN_", "NPM_CONFIG_", "RUNNER_"))
    }
    environment.update(
        TMPDIR=str(tmp_path / "tmp"),
        PATH=str(tmp_path / "bin") + os.pathsep + environment["PATH"],
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", SHIM_PATH, str(tmp_path / name / ".hooks"), "."],
            cwd=tmp_path / name,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name in ("a", "b")
    ]
    results = [process.communicate(timeout=60) for process in processes]
    assert [process.returncode for process in processes] == [0, 0], results
    (a_shim, a_script), (b_shim, b_script) = (
        output.split("shim:", 1)[1].split("\n", 1) for output, _ in results
    )
    assert len({a_shim, b_shim, str(old / "bun-node/node")}) == 3
    assert "# other revision" not in a_script and "# other revision" in b_script
    assert Path(a_shim).read_text() == a_script
    assert adds(registry) == ["2026.9.13", "2026.9.13"]
    assert not old_launcher.exists()


def test_a_running_check_never_reads_a_partly_written_file(tmp_path: Path) -> None:
    import threading

    import tool_setup

    target = tmp_path / "node"
    scripts = ["#!/bin/sh\n" + "a" * 50000, "#!/bin/sh\n" + "b" * 50000]
    tool_setup.replace_file(target, scripts[0], 0o755)
    seen: set[str] = set()
    done = threading.Event()

    def read() -> None:
        while not done.is_set():
            seen.add(target.read_text())

    reader = threading.Thread(target=read)
    reader.start()
    for index in range(400):
        tool_setup.replace_file(target, scripts[index % 2], 0o755)
    done.set()
    reader.join()
    assert seen <= set(scripts)
    assert os.access(target, os.X_OK)
    assert [path.name for path in tmp_path.iterdir()] == ["node"]


def test_push_snapshots_reuse_their_checkout_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A push checks a fresh temporary copy; its own folder would reinstall every tool."""
    import ship_actions
    import tool_setup
    from conftest import commit, init

    root = tmp_path / "project"
    init(root)
    (root / "README.md").write_text("x")
    revision = commit(root, "start")
    shared = tmp_path / "tools"
    environment = os.environ.copy()
    with ship_actions.snapshot(root, revision, environment) as checkout:
        storages = []
        for path, env in (
            (root, os.environ.copy()),
            (checkout, environment),
            (tmp_path / "other", environment),
        ):
            monkeypatch.setattr(tool_setup, "CHECKOUT", path.resolve())
            monkeypatch.setattr(tool_setup, "HELD", [])
            monkeypatch.setattr(os, "environ", env)
            storages.append(tool_setup.checkout_storage(shared))
            tool_setup.HELD[0].close()
    assert storages[0] == storages[1] != storages[2]
    assert (storages[1] / "checkout").read_text() == str(root.resolve())


def test_deleted_checkouts_lose_their_tools_unless_a_check_holds_them(
    tmp_path: Path,
) -> None:
    import tool_setup

    checkouts = tmp_path / "checkouts"
    for name, owner in (
        ("gone", tmp_path / "deleted"),
        ("held", tmp_path / "deleted"),
        ("live", tmp_path),
    ):
        (checkouts / name / "mise").mkdir(parents=True)
        (checkouts / name / "checkout").write_text(str(owner))
    with (checkouts / "held/lock").open("a") as running_check:
        fcntl.flock(running_check, fcntl.LOCK_SH)
        tool_setup.prune_checkouts(checkouts)
    assert sorted(path.name for path in checkouts.iterdir()) == ["held", "live"]


def test_push_copies_and_tools_stay_out_of_a_hidden_temporary_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Biome skipped its React rules below a hidden TMPDIR and failed every suppression."""
    from unittest.mock import Mock

    import ship_actions
    import tool_setup
    from conftest import commit, init, use_installed_mise

    hidden, visible = tmp_path / ".cache/tmp", tmp_path / "visible"
    for directory in (hidden, visible):
        directory.mkdir(parents=True)
    monkeypatch.setattr(tool_setup.tempfile, "gettempdir", lambda: str(hidden))
    monkeypatch.setattr(tool_setup, "VISIBLE_TEMP", visible)
    monkeypatch.setattr(tool_setup, "HELD", [])
    for name in ("RUNNER_TEMP", "MISE_DATA_DIR", "BUN_INSTALL_CACHE_DIR"):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "project"
    init(root)
    (root / "README.md").write_text("x")
    revision = commit(root, "start")
    with ship_actions.snapshot(root, revision, os.environ.copy()) as checkout:
        assert checkout.is_relative_to(visible)
    use_installed_mise(tmp_path, monkeypatch)
    native = Mock(return_value=subprocess.CompletedProcess([], 0, '{"PATH": ""}', ""))
    monkeypatch.setattr(subprocess, "run", native)
    tool_setup.provision_batch(["aqua:gitleaks/gitleaks@latest"], 30)
    tool_setup.HELD[0].close()
    environment = native.call_args.kwargs["env"]
    for name in ("MISE_DATA_DIR", "BUN_INSTALL_CACHE_DIR"):
        assert Path(environment[name]).is_relative_to(visible)


def test_a_check_skips_a_stale_folder_another_check_just_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tool_setup

    stale = tmp_path / "checkouts/gone"
    stale.mkdir(parents=True)
    (stale / "checkout").write_text(str(tmp_path / "deleted"))
    exists = Path.exists

    def other_check_prunes_first(path: Path) -> bool:
        if path == tmp_path / "deleted":
            shutil.rmtree(stale)
        return exists(path)

    monkeypatch.setattr(Path, "exists", other_check_prunes_first)
    tool_setup.prune_checkouts(tmp_path / "checkouts")
    assert not stale.exists()
