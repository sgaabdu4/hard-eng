#!/usr/bin/env python3
"""Live tracker readiness: credentials from the environment or the checkout's .env, one authenticated probe each."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DETERMINISTIC_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
for candidate in (SCRIPT_DIR, DETERMINISTIC_SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bounded_run import run_captured
from git_env import git_env

ADAPTERS = ("github", "jira", "azdo")
CREDENTIAL_NAMES = {
    "github": ("GITHUB_REPOSITORY",),
    "jira": ("JIRA_SITE", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT"),
    "azdo": ("AZDO_ORG", "AZDO_PROJECT", "AZDO_PAT"),
}
SECRET_NAMES = ("JIRA_API_TOKEN", "AZDO_PAT")
ENV_EXAMPLE_START = "# >>> hard-eng trackers >>>"
ENV_EXAMPLE_END = "# <<< hard-eng trackers <<<"
ENV_FILE = ".env"
ENV_EXAMPLE_FILE = ".env.example"
PROBE_TIMEOUT = 15
ENV_LINE = re.compile(r"^(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=\s*(.*)$")
API_VERSION = "7.1"


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file() or path.is_symlink():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_LINE.match(line)
        if match is None:
            continue
        name, value = match.groups()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def credentials(repo: Path, environ: dict[str, str] | None = None) -> dict[str, str]:
    source = os.environ if environ is None else environ
    merged = read_env_file(repo / ENV_FILE)
    for names in CREDENTIAL_NAMES.values():
        for name in names:
            if source.get(name):
                merged[name] = source[name]
    return merged


def redact(text: str, values: dict[str, str]) -> str:
    for name in SECRET_NAMES:
        secret = values.get(name)
        if secret:
            text = text.replace(secret, f"<{name}>")
            text = text.replace(base64.b64encode(secret.encode()).decode(), f"<{name}>")
    return text


def missing_names(adapter: str, values: dict[str, str]) -> list[str]:
    return [name for name in CREDENTIAL_NAMES[adapter] if not values.get(name)]


def _basic_header(user: str, secret: str) -> str:
    return "Basic " + base64.b64encode(f"{user}:{secret}".encode()).decode()


def _get(url: str, authorization: str, timeout: float = PROBE_TIMEOUT) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"Authorization": authorization, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(4096).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(4096).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError) as error:
        return 0, str(error)


def jira_base(values: dict[str, str]) -> str:
    site = values["JIRA_SITE"].rstrip("/")
    return site if site.startswith(("http://", "https://")) else f"https://{site}"


def azdo_base(values: dict[str, str]) -> str:
    org = values["AZDO_ORG"].rstrip("/")
    return org if org.startswith(("http://", "https://")) else f"https://dev.azure.com/{org}"


def jira_authorization(values: dict[str, str]) -> str:
    return _basic_header(values["JIRA_EMAIL"], values["JIRA_API_TOKEN"])


def azdo_authorization(values: dict[str, str]) -> str:
    return _basic_header("", values["AZDO_PAT"])


def probe_github(repo: Path, values: dict[str, str]) -> dict[str, object]:
    if shutil.which("gh") is None:
        return {"adapter": "github", "available": False, "detail": "gh CLI is not installed", "missing": ["gh"]}
    captured = run_captured(["gh", "auth", "status"], PROBE_TIMEOUT, cwd=str(repo), env=git_env())
    if captured.returncode != 0:
        text = (captured.stderr or captured.stdout).decode("utf-8", "replace").strip().splitlines()
        detail = text[-1] if text else f"gh auth status exit {captured.returncode}"
        return {"adapter": "github", "available": False, "detail": detail, "missing": ["gh auth login"]}
    return {"adapter": "github", "available": True, "detail": "gh auth status ok", "missing": []}


def probe_jira(repo: Path, values: dict[str, str]) -> dict[str, object]:
    missing = missing_names("jira", values)
    if missing:
        return {"adapter": "jira", "available": False, "detail": "missing " + ", ".join(missing), "missing": missing}
    status, body = _get(f"{jira_base(values)}/rest/api/3/myself", jira_authorization(values))
    if status != 200:
        detail = redact(f"GET /rest/api/3/myself returned {status}: {body[:120]}", values)
        return {"adapter": "jira", "available": False, "detail": detail, "missing": ["valid JIRA_API_TOKEN"]}
    return {"adapter": "jira", "available": True, "detail": "Jira Cloud myself ok", "missing": []}


def probe_azdo(repo: Path, values: dict[str, str]) -> dict[str, object]:
    missing = missing_names("azdo", values)
    if missing:
        return {"adapter": "azdo", "available": False, "detail": "missing " + ", ".join(missing), "missing": missing}
    url = f"{azdo_base(values)}/_apis/projects/{values['AZDO_PROJECT']}?api-version={API_VERSION}"
    status, body = _get(url, azdo_authorization(values))
    if status != 200:
        detail = redact(f"GET project returned {status}: {body[:120]}", values)
        return {"adapter": "azdo", "available": False, "detail": detail, "missing": ["valid AZDO_PAT"]}
    return {"adapter": "azdo", "available": True, "detail": "Azure DevOps project ok", "missing": []}


PROBES = {"github": probe_github, "jira": probe_jira, "azdo": probe_azdo}


def probe_all(repo: Path, environ: dict[str, str] | None = None) -> list[dict[str, object]]:
    values = credentials(repo, environ)
    return [PROBES[adapter](repo, values) for adapter in ADAPTERS]


def env_example_block() -> str:
    names = [name for adapter in ("jira", "azdo") for name in CREDENTIAL_NAMES[adapter]]
    body = "\n".join(f"{name}=" for name in names)
    return f"{ENV_EXAMPLE_START}\n{body}\n{ENV_EXAMPLE_END}\n"


def write_env_example(repo: Path) -> bool:
    path = repo / ENV_EXAMPLE_FILE
    if path.is_symlink():
        raise OSError(f"{ENV_EXAMPLE_FILE} is a symlink")
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    block = env_example_block()
    if block in current:
        return False
    if ENV_EXAMPLE_START in current or ENV_EXAMPLE_END in current:
        raise OSError(f"{ENV_EXAMPLE_FILE} has a malformed hard-eng trackers block")
    separator = "" if not current or current.endswith("\n") else "\n"
    path.write_text(current + separator + block, encoding="utf-8")
    return True


def emit_lines(results: list[dict[str, object]]) -> list[str]:
    lines: list[str] = []
    for index, result in enumerate(results, start=1):
        available = "yes" if result["available"] else "no"
        lines.append(f"tracker_{index}={result['adapter']}")
        lines.append(f"tracker_{index}_available={available}")
        lines.append(f"tracker_{index}_detail={result['detail']}")
    return lines


def main() -> int:
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    results = probe_all(repo)
    print("\n".join(emit_lines(results)))
    print(json.dumps({"probes": results}, indent=2), file=sys.stderr)
    return 0 if any(result["available"] for result in results) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.SubprocessError) as error:
        print(f"tracker-probe: {error}", file=sys.stderr)
        raise SystemExit(4) from error
