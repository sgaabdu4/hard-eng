"""Provision current native tools before concurrent gate execution."""

import fcntl
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from fallow_report import native_scanner_command
from gate_config import Group
from project_setup import package_script_invocation

NATIVE_SCANNERS = {
    "dart-decimate": "dart-decimate",
    "react-doctor": "React Doctor",
}
MANAGED_PYTHON_SCANNERS = {"ruff", "pyrefly", "vulture", "semgrep", "zizmor", "poetry"}
MISE_PACKAGE = "@jdxcode/mise"
MISE_LATEST = MISE_PACKAGE + "@latest"
MISE_BINARY = Path("node_modules/@jdxcode/mise/bin/mise")
NOT_INSTALLED = (
    "Tools are not installed yet and cannot be fetched now: {error}. "
    "Connect once or run the full check (python3 .hooks/hard-eng.py check) to install them."
)


def quick_mode() -> bool:
    return "--quick" in sys.argv


def ensure_python_runtime() -> None:
    """Run the installed CLI with its YAML dependency without changing host Python."""
    if importlib.util.find_spec("yaml") is None:
        os.execvp(
            "uv",
            [
                "uv",
                "run",
                "--no-project",
                "--with",
                "pyyaml",
                "--python",
                sys.executable,
                "python",
                *sys.argv,
            ],
        )


def entry_point_names(directory: Path) -> list[str]:
    """Functions the project's console scripts call, which vulture cannot see being used."""
    try:
        project = tomllib.loads((directory / "pyproject.toml").read_text())["project"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return []
    targets = [
        target
        for table in ("scripts", "gui-scripts")
        for target in project.get(table, {}).values()
        if isinstance(target, str)
    ]
    return sorted(
        {
            target.split(":")[-1].split("[")[0].split(".")[-1].strip()
            for target in targets
        }
        - {""}
    )


def with_entry_points(command: list[str], directory: Path) -> list[str]:
    names = entry_point_names(directory)
    if command[0] != "vulture" or not names:
        return command
    return [*command, "--ignore-names", ",".join(names)]


def managed_command(command: list[str], directory: Path | None = None) -> list[str]:
    if directory is not None:
        command = with_entry_points(
            managed_scanner_command(command, directory), directory
        )
    if command[0] in MANAGED_PYTHON_SCANNERS:
        offline = ["--offline"] if quick_mode() else []
        return ["uvx", *offline, command[0] + "@latest", *command[1:]]
    return command


def managed_scanner_command(command: list[str], directory: Path) -> list[str]:
    """Keep supported scanner arguments without a stale package-local binary."""
    arguments, resolved = package_script_invocation(command, directory)
    invocation = native_scanner_command(arguments)
    if invocation is not None:
        scanner = (
            "Fallow" if invocation[0] == "fallow" else NATIVE_SCANNERS[invocation[0]]
        )
        if resolved.resolve() != directory.resolve():
            raise ValueError(
                f"Configure the {scanner} gate in its explicit package directory"
            )
        if any(value in arguments for value in ("&&", "||", ";", "|", ">", "2>")):
            if scanner == "Fallow":
                raise ValueError(
                    "Fallow audit must be one native invocation with its arguments"
                )
            raise ValueError(
                f"{scanner} must be one native invocation with its arguments"
            )
        return invocation
    return command


def provision_tools(root: Path, groups: list[Group], timeout: float) -> None:
    packages = {
        "uv": "uv",
        "gitleaks": "aqua:gitleaks/gitleaks",
        "osv-scanner": "aqua:google/osv-scanner",
        "actionlint": "aqua:rhysd/actionlint",
        "shellcheck": "aqua:koalaman/shellcheck",
        "trivy": "aqua:aquasecurity/trivy",
        "biome": "npm:@biomejs/biome",
        "tsc": "npm:typescript",
        "fallow": "npm:fallow",
        "dart-decimate": 'npm:dart-decimate[allow_builds=["dart-decimate"]]',
        "react-doctor": "npm:react-doctor",
        "jscpd": "npm:jscpd",
        "lhci": "npm:@lhci/cli",
        "k6": "aqua:grafana/k6",
    }
    commands = [
        package_script_invocation(
            managed_scanner_command(gate["command"], root / group["path"]),
            root / group["path"],
        )[0]
        for group in groups
        for gate in group["checks"]
    ]
    executables = {command[0] for command in commands}
    if executables & MANAGED_PYTHON_SCANNERS:
        executables.add("uv")
    executables.update(
        argument
        for command in commands
        for argument in command[1:]
        if argument in packages
    )
    selected = sorted(
        packages[name] + "@latest" for name in executables & packages.keys()
    )
    if quick_mode():
        warm_python_scanners(sorted(executables & MANAGED_PYTHON_SCANNERS), timeout)
    if selected:
        provision_batch(selected, timeout)


def scanner_runs(name: str, offline: bool, timeout: float) -> bool:
    try:
        subprocess.run(
            ["uvx", *(["--offline"] if offline else []), name + "@latest", "--version"],
            capture_output=True,
            timeout=timeout,
            check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return False
    return True


def warm_python_scanners(names: list[str], timeout: float) -> None:
    """Quick checks run scanners from uv's cache; fetch one only when it was never cached."""
    for name in names:
        if not (
            scanner_runs(name, True, timeout) or scanner_runs(name, False, timeout)
        ):
            raise ValueError(NOT_INSTALLED.format(error=f"{name} could not be run"))


def provision_batch(batch: list[str], timeout: float) -> None:
    storage = (
        Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "hard-eng-tools"
    )
    environment = os.environ.copy()
    for name, directory in {
        "MISE_DATA_DIR": "mise/data",
        "MISE_CACHE_DIR": "mise/cache",
        "MISE_STATE_DIR": "mise/state",
        "PNPM_CONFIG_STORE_DIR": "pnpm/store",
        "PNPM_CONFIG_CACHE_DIR": "pnpm/cache",
    }.items():
        environment.setdefault(name, str(storage / directory))
    if shutil.which("gh"):
        environment.setdefault(
            "MISE_GITHUB_CREDENTIAL_COMMAND",
            'gh auth token --hostname "$MISE_CREDENTIAL_HOST"',
        )
    if quick_mode():
        try:
            if use_installed_tools(batch, storage, environment, timeout):
                return
            print("Install missing native tools: " + ", ".join(batch), flush=True)
            provision_latest(batch, storage, environment, timeout)
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            raise ValueError(NOT_INSTALLED.format(error=error)) from error
        return
    print("Prepare latest native tools: " + ", ".join(batch), flush=True)
    provision_latest(batch, storage, environment, timeout)


def newest_launcher(launchers: Path) -> Path | None:
    found = [
        path for path in launchers.glob("[0-9]*/") if (path / MISE_BINARY).is_file()
    ]
    return max(
        found,
        key=lambda path: [int(part) for part in re.findall(r"\d+", path.name)],
        default=None,
    )


def use_installed_tools(
    batch: list[str], storage: Path, environment: dict[str, str], timeout: float
) -> bool:
    """Resolve already-installed tool versions without any network request."""
    launcher = newest_launcher(storage / "mise-launcher")
    if launcher is None:
        return False
    result = subprocess.run(
        [str(launcher / MISE_BINARY), "--no-config", "env", "--json", *batch],
        cwd=storage,
        text=True,
        timeout=timeout,
        capture_output=True,
        check=False,
        env={**environment, "MISE_OFFLINE": "1", "MISE_NPM_PACKAGE_MANAGER": "pnpm"},
    )
    if result.returncode != 0 or "Failed to resolve tool version" in result.stderr:
        return False
    export_tool_paths(result.stdout, Path(environment["MISE_DATA_DIR"]))
    return True


def provision_latest(
    batch: list[str], storage: Path, environment: dict[str, str], timeout: float
) -> None:
    with mise_launcher(storage / "mise-launcher", environment, timeout) as mise:
        environment["PATH"] = os.pathsep.join(
            [str(mise.parent), environment.get("PATH", os.defpath)]
        )
        command = [
            "env",
            "MISE_NPM_PACKAGE_MANAGER=pnpm",
            "MISE_PREFER_OFFLINE=false",
            "MISE_USE_VERSIONS_HOST=false",
            "MISE_MINIMUM_RELEASE_AGE=0s",
            "mise",
            "--no-config",
        ]
        for arguments in (["install", *batch], ["env", "--json", *batch]):
            result = subprocess.run(
                [*command, *arguments],
                # The project's packageManager pin would otherwise pick the pnpm mise drives.
                cwd=storage,
                text=True,
                timeout=timeout,
                capture_output=True,
                check=False,
                env={
                    **environment,
                    "MISE_FETCH_REMOTE_VERSIONS_CACHE": "0s"
                    if arguments[0] == "install"
                    else "1h",
                },
            )
            print(result.stderr, file=sys.stderr, end="")
            result.check_returncode()
            if "Failed to resolve tool version" in result.stderr:
                raise ValueError(
                    "Latest tool versions could not be resolved; retry provisioning"
                )
    export_tool_paths(result.stdout, Path(environment["MISE_DATA_DIR"]))


def export_tool_paths(output: str, data_directory: Path) -> None:
    environment = json.loads(output)
    if not isinstance(environment, dict) or not isinstance(
        environment.get("PATH"), str
    ):
        raise TypeError("Native tool setup did not return an executable PATH")
    tool_paths = [
        path
        for path in environment["PATH"].split(os.pathsep)
        if Path(path).resolve().is_relative_to(data_directory.resolve())
    ]
    os.environ["PATH"] = os.pathsep.join([*tool_paths, os.environ["PATH"]])


@contextmanager
def mise_launcher(
    launchers: Path, environment: dict[str, str], timeout: float
) -> Generator[Path]:
    """Yield the newest published mise, installed once per version and held while used."""
    launchers.mkdir(parents=True, exist_ok=True)
    version = json.loads(
        subprocess.run(
            ["pnpm", "view", MISE_LATEST, "version", "--json"],
            cwd=launchers,
            env=environment,
            text=True,
            timeout=timeout,
            capture_output=True,
            check=True,
        ).stdout
    )
    if not isinstance(version, str) or not re.fullmatch(r"\d[\w.+-]*", version):
        raise TypeError("pnpm did not return a usable latest mise version")
    installation = launchers / version
    with (launchers / f"{version}.lock").open("a") as use:
        fcntl.flock(use, fcntl.LOCK_SH)
        with (launchers / "install.lock").open("a") as install:
            try:
                fcntl.flock(
                    install,
                    fcntl.LOCK_EX | (fcntl.LOCK_NB if installation.is_dir() else 0),
                )
            except BlockingIOError:
                pass
            else:
                if not installation.is_dir():
                    install_launcher(installation, environment, timeout)
                prune_launchers(launchers, version)
        yield installation / MISE_BINARY


def install_launcher(
    installation: Path, environment: dict[str, str], timeout: float
) -> None:
    staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=installation.parent))
    try:
        (staging / "package.json").write_text('{"private": true}\n')
        result = subprocess.run(
            [
                "pnpm",
                "add",
                "--dir",
                str(staging),
                "--config.ignore-scripts=false",
                f"--allow-build={MISE_PACKAGE}",
                f"{MISE_PACKAGE}@{installation.name}",
            ],
            cwd=staging,
            env=environment,
            text=True,
            timeout=timeout,
            capture_output=True,
            check=False,
        )
        print(result.stderr, file=sys.stderr, end="")
        result.check_returncode()
        reported = subprocess.run(
            [str(staging / MISE_BINARY), "--version"],
            text=True,
            timeout=timeout,
            capture_output=True,
            check=False,
        ).stdout.split()
        if reported[:1] != [installation.name]:
            raise ValueError(f"mise {installation.name} failed its installation check")
        staging.rename(installation)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def prune_launchers(launchers: Path, current: str) -> None:
    """Under the install lock, drop interrupted installs and unheld older versions."""
    for path in launchers.iterdir():
        if path.name.startswith(".staging-"):
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_dir() and path.name != current:
            with (launchers / f"{path.name}.lock").open("a") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                shutil.rmtree(path, ignore_errors=True)
