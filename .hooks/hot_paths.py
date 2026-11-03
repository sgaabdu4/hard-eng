"""HE-HOT-PATH: the security gate runs these rules; `hot-paths` lists their findings."""

import json
import subprocess
from pathlib import Path

from tool_setup import managed_command

RULES = (
    Path(__file__).resolve().parents[1] / ".agents/skills/he/semgrep/performance.yaml"
)


def findings(root: Path, targets: list[str], timeout: float) -> list[dict[str, object]]:
    command = managed_command(
        ["semgrep", "scan", "--config", str(RULES), "--metrics=off"]
    )
    try:
        result = subprocess.run(
            [*command, "--quiet", "--json", "--timeout", "60", *targets],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"HE-HOT-PATH scan ran over {timeout:.0f}s") from error
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"HE-HOT-PATH scan failed: {result.stderr[-500:]}") from error
    errors = report.get("errors", [])
    if any("PartialParsing" not in str(error.get("type")) for error in errors):
        raise ValueError(f"HE-HOT-PATH scan errors: {errors}")
    for error in errors:
        print(f"HE-HOT-PATH: partly scanned: {error.get('message', '')[:300]}")
    return report["results"]


def describe(result: dict[str, object]) -> str:
    start, extra = result["start"], result["extra"]
    assert isinstance(start, dict) and isinstance(extra, dict)
    return f"{result['path']}:{start['line']} {extra['message']}"


def scan_all(root: Path, timeout: float = 600) -> int:
    """List every finding in the repository, for a requested hot-path scan."""
    results = findings(root, ["."], timeout)
    for result in results:
        print(describe(result))
    print(f"HE-HOT-PATH: {len(results)} findings")
    return 1 if results else 0
