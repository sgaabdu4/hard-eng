"""Resolve current upstream scanner releases into a repository-local cache."""

from __future__ import annotations

import io
import platform
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from hard_eng.common import GateError, array, checked, object_value, parse_json, state_dir

PYTHON = {
    "ruff": "ruff",
    "pyrefly": "pyrefly",
    "pytest": "pytest",
    "vulture": "vulture",
    "deptry": "deptry",
    "lint-imports": "import-linter",
    "semgrep": "semgrep",
    "zizmor": "zizmor",
}
NODE = {
    "biome": "@biomejs/biome",
    "fallow": "fallow",
    "react-doctor": "react-doctor",
    "dart-decimate": "dart-decimate",
    "jscpd": "jscpd",
    "context-mode": "context-mode",
    "codebase-memory-mcp": "codebase-memory-mcp",
}
NATIVE = {
    "gitleaks": "gitleaks/gitleaks",
    "osv-scanner": "google/osv-scanner",
    "actionlint": "rhysd/actionlint",
    "shellcheck": "koalaman/shellcheck",
    "trivy": "aquasecurity/trivy",
}


@dataclass(frozen=True)
class Tool:
    name: str
    version: str
    command: tuple[str, ...]


def download(url: str) -> bytes:
    if not url.startswith("https://"):
        raise GateError("Tool downloads require HTTPS")
    request = urllib.request.Request(url, headers={"User-Agent": "hard-eng", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()
    except (OSError, urllib.error.URLError) as error:
        raise GateError(f"Cannot check/download tool from {urllib.parse.urlparse(url).hostname}") from error


def release(name: str) -> tuple[str, dict[str, object]]:
    data = parse_json(download(f"https://api.github.com/repos/{NATIVE[name]}/releases/latest").decode())
    version = data.get("tag_name")
    if not isinstance(version, str) or data.get("prerelease") or data.get("draft"):
        raise GateError(f"No stable release for {name}")
    return version, data


def asset_name(name: str, version: str) -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system not in {"darwin", "linux"} or machine not in {"arm64", "aarch64", "x86_64", "amd64"}:
        raise GateError(f"Unsupported scanner platform: {system}/{machine}")
    arm = machine in {"arm64", "aarch64"}
    arch = "arm64" if arm else "amd64"
    number = version.removeprefix("v")
    if name == "osv-scanner":
        return f"osv-scanner_{system}_{arch}"
    if name == "shellcheck":
        return f"shellcheck-{version}.{system}.{'aarch64' if arm else 'x86_64'}.tar.gz"
    if name == "trivy":
        return f"trivy_{number}_{'macOS' if system == 'darwin' else 'Linux'}-{'ARM64' if arm else '64bit'}.tar.gz"
    if name == "gitleaks" and not arm:
        arch = "x64"
    return f"{name}_{number}_{system}_{arch}.tar.gz"


def find_asset(data: dict[str, object], filename: str) -> dict[str, object]:
    for value in array(data.get("assets"), "release assets"):
        asset = object_value(value, "release asset")
        if asset.get("name") == filename:
            return asset
    raise GateError(f"Official release asset missing: {filename}")


def binary(root: Path, name: str, version: str, data: dict[str, object]) -> str:
    filename = asset_name(name, version)
    asset = find_asset(data, filename)
    url = asset.get("browser_download_url")
    if not isinstance(url, str):
        raise GateError(f"Official download URL missing for {filename}")
    directory = state_dir(root) / "tools" / name / version
    executable = directory / name
    if executable.is_file():
        return str(executable)
    payload = download(url)
    directory.mkdir(parents=True, exist_ok=True)
    if filename.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as bundle:
            members = [
                member for member in bundle.getmembers() if Path(member.name).name == name and member.isfile()
            ]
            if len(members) != 1:
                raise GateError(f"Expected one executable in {filename}")
            stream = bundle.extractfile(members[0])
            if stream is None:
                raise GateError(f"Cannot read executable in {filename}")
            executable.write_bytes(stream.read())
    else:
        executable.write_bytes(payload)
    executable.chmod(0o755)
    return str(executable)


def package_version(package: str, ecosystem: str) -> str:
    if ecosystem == "python":
        data = parse_json(download(f"https://pypi.org/pypi/{package}/json").decode())
        value = object_value(data.get("info"), "PyPI info").get("version")
    else:
        url = f"https://registry.npmjs.org/{urllib.parse.quote(package, safe='')}/latest"
        value = parse_json(download(url).decode()).get("version")
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise GateError(f"Invalid latest version: {package}")
    return value


def resolve(root: Path, name: str) -> Tool:
    if name in PYTHON:
        package = PYTHON[name]
        version = package_version(package, "python")
        command = ["uvx", "--cache-dir", str(state_dir(root) / "uv"), "--from", f"{package}=={version}"]
        if name == "pytest":
            coverage = package_version("pytest-cov", "python")
            command = [
                "uv",
                "run",
                "--no-sync",
                "--cache-dir",
                str(state_dir(root) / "uv"),
                "--with",
                f"pytest=={version}",
                "--with",
                f"pytest-cov=={coverage}",
            ]
            version += f"+pytest-cov.{coverage}"
        return Tool(name, version, (*command, name))
    if name in NODE:
        package = NODE[name]
        version = package_version(package, "node")
        command = (
            "npm",
            "exec",
            "--cache",
            str(state_dir(root) / "npm"),
            "--yes",
            "--package",
            f"{package}@{version}",
            "--",
            name,
        )
        if name == "codebase-memory-mcp":
            # Complete the npm bootstrap before its download messages can enter MCP stdout.
            checked([*command, "--version"], root, 180)
        return Tool(name, version, command)
    if name in NATIVE:
        version, data = release(name)
        return Tool(name, version, (binary(root, name, version, data),))
    raise GateError(f"Unsupported managed tool: {name}")
