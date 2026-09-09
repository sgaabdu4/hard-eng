"""Provision current native tools before concurrent gate execution."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from gate_config import Group


def managed_command(command: list[str]) -> list[str]:
    if command[0] in {"ruff", "pyrefly", "vulture", "semgrep", "zizmor", "poetry"}:
        return ["uvx", command[0] + "@latest", *command[1:]]
    return command


def provision_tools(root: Path, groups: list[Group], timeout: float) -> None:
    packages = {
        "gitleaks": "aqua:gitleaks/gitleaks",
        "osv-scanner": "aqua:google/osv-scanner",
        "actionlint": "aqua:rhysd/actionlint",
        "shellcheck": "aqua:koalaman/shellcheck",
        "trivy": "aqua:aquasecurity/trivy",
        "biome": "npm:@biomejs/biome",
        "tsc": "npm:typescript",
        "fallow": "npm:fallow",
        "react-doctor": "npm:react-doctor",
        "jscpd": "npm:jscpd",
        "lhci": "npm:@lhci/cli",
        "k6": "aqua:grafana/k6",
    }
    executables = {gate["command"][0] for group in groups for gate in group["checks"]}
    selected = sorted(
        packages[name] + "@latest" for name in executables & packages.keys()
    )
    storage = Path(tempfile.gettempdir()) / "hard-eng-tools"
    if selected:
        command = [
            "env",
            f"MISE_DATA_DIR={storage / 'mise/data'}",
            f"MISE_CACHE_DIR={storage / 'mise/cache'}",
            f"MISE_STATE_DIR={storage / 'mise/state'}",
            f"PNPM_CONFIG_STORE_DIR={storage / 'pnpm/store'}",
            f"PNPM_CONFIG_CACHE_DIR={storage / 'pnpm/cache'}",
            "MISE_FETCH_REMOTE_VERSIONS_CACHE=0s",
            "MISE_PREFER_OFFLINE=false",
            "MISE_USE_VERSIONS_HOST=false",
            "MISE_MINIMUM_RELEASE_AGE=0s",
            "pnpm",
            "dlx",
            "--allow-build=@jdxcode/mise",
            "--package=@jdxcode/mise@latest",
            "mise",
            "--no-config",
            "env",
            "--json",
            *selected,
        ]
        print("Prepare latest native tools: " + ", ".join(selected), flush=True)
        result = subprocess.run(
            command,
            cwd=root,
            text=True,
            timeout=timeout,
            capture_output=True,
            check=False,
        )
        print(result.stderr, file=sys.stderr, end="")
        result.check_returncode()
        if "Failed to resolve tool version" in result.stderr:
            raise ValueError(
                "Latest tool versions could not be resolved; retry provisioning"
            )
        environment = json.loads(result.stdout)
        if not isinstance(environment, dict) or not isinstance(
            environment.get("PATH"), str
        ):
            raise TypeError("Native tool setup did not return an executable PATH")
        tool_paths = [
            path
            for path in environment["PATH"].split(os.pathsep)
            if Path(path).resolve().is_relative_to(storage.resolve())
        ]
        os.environ["PATH"] = os.pathsep.join([*tool_paths, os.environ["PATH"]])
    if "dart-decimate" in executables:
        subprocess.run(
            [
                "cargo",
                "install",
                "--git",
                "https://github.com/sgaabdu4/dart-decimate",
                "--locked",
                "--root",
                str(storage / "decimate"),
                "dart-decimate",
            ],
            cwd=root,
            check=True,
            timeout=timeout,
        )
        os.environ["PATH"] = (
            str(storage / "decimate/bin") + os.pathsep + os.environ["PATH"]
        )
