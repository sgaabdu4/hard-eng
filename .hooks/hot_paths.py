"""HE-HOT-PATH: known slow patterns fail on added lines; judgment cases print as notes."""

import json
import subprocess
from pathlib import Path

from comments import JAVASCRIPT, UNOWNED, diff_lines
from gate_config import generated_sources
from plans import default_branch_point
from tool_setup import managed_command

RULES = ".agents/skills/he/semgrep/performance.yaml"
SUFFIXES = {".py", ".dart", ".swift", ".sql", ".prisma", *JAVASCRIPT}


def findings(root: Path, targets: list[str], timeout: float) -> list[dict[str, object]]:
    command = managed_command(
        ["semgrep", "scan", "--config", str(root / RULES), "--metrics=off"]
    )
    result = subprocess.run(
        [*command, "--quiet", "--json", "--timeout", "60", *targets],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"HE-HOT-PATH scan failed: {result.stderr[-500:]}") from error
    if report.get("errors"):
        raise ValueError(f"HE-HOT-PATH scan errors: {report['errors']}")
    return report["results"]


def describe(result: dict[str, object]) -> str:
    start, extra = result["start"], result["extra"]
    assert isinstance(start, dict) and isinstance(extra, dict)
    return f"{result['path']}:{start['line']} {extra['message']}"


def scan_changes(root: Path, base: str | None, timeout: float) -> None:
    """Fail on blocking findings that touch added lines; print the others as notes."""
    added, _ = diff_lines(root, base or default_branch_point(root) or "HEAD")
    names = [
        name
        for name in sorted(added)
        if Path(name).suffix in SUFFIXES
        and not name.startswith(UNOWNED)
        and (root / name).is_file()
    ]
    names = [name for name in names if name not in generated_sources(root, names)]
    if not names:
        return
    lines = {name: {number for number, _ in added[name]} for name in names}
    blocked, notes = [], []
    for result in findings(root, names, timeout):
        start, end, extra = result["start"], result["end"], result["extra"]
        assert isinstance(start, dict) and isinstance(end, dict)
        assert isinstance(extra, dict)
        span = range(start["line"], end["line"] + 1)
        if not lines.get(str(result["path"]), set()).intersection(span):
            continue
        (blocked if extra["severity"] == "ERROR" else notes).append(describe(result))
    for note in notes:
        print(f"Performance note (HE-HOT-PATH): {note}")
    if blocked:
        raise ValueError(
            "HE-HOT-PATH: added code holds a known slow pattern; rewrite it as the "
            "message says: " + "; ".join(blocked)
        )


def scan_all(root: Path, timeout: float) -> int:
    """List every finding in the repository, for a requested hot-path scan."""
    results = findings(root, ["."], timeout)
    for result in results:
        extra = result["extra"]
        assert isinstance(extra, dict)
        kind = "fix" if extra["severity"] == "ERROR" else "note"
        print(f"{kind}: {describe(result)}")
    print(f"HE-HOT-PATH: {len(results)} findings")
    return 0
