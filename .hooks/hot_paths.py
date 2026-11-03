"""HE-HOT-PATH: Hard Eng's Semgrep rules join every security gate; `hot-paths` lists findings."""

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath

from gate_config import Gate, Group, generated_sources, repository_files
from tool_setup import managed_command

RULES = (
    Path(__file__).resolve().parents[1] / ".agents/skills/he/semgrep/performance.yaml"
)
PYTHON_RULES = RULES.with_name("python.yaml")
GLOB_SPECIAL = re.compile(r"[][*?]")


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
    require_parsed(report.get("errors", []))
    return report["results"]


def require_parsed(errors: list[dict[str, object]]) -> None:
    """Fail on scan errors except files Semgrep parsed only in part; print those gaps."""
    spans = [
        kind[1]
        for kind in (error.get("type") for error in errors)
        if isinstance(kind, list) and kind[0] == "PartialParsing"
    ]
    if len(spans) != len(errors):
        raise ValueError(f"Semgrep reports scan errors: {str(errors)[:1000]}")
    for span in (span for gaps in spans for span in gaps):
        print(f"Semgrep partly scanned {span['path']}:{span['start']['line']}")


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


def unowned_paths(names: list[str], generated: set[str]) -> list[str]:
    """Generated files, as their highest folder that holds nothing else."""
    files: Counter[PurePosixPath] = Counter()
    made: Counter[PurePosixPath] = Counter()
    for name in names:
        for folder in PurePosixPath(name).parents[:-1]:
            files[folder] += 1
            made[folder] += name in generated
    paths = set()
    for name in generated:
        folders = [
            folder
            for folder in PurePosixPath(name).parents[:-1]
            if made[folder] == files[folder]
        ]
        paths.add(f"{folders[-1]}/" if folders else name)
    return sorted(paths)


def git_prefix(directory: Path) -> str:
    """The folder's path from the Git root, which Semgrep anchors excludes to."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-prefix"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def semgrep_options(
    root: Path, group: Group, gate: Gate, command: list[str]
) -> list[str]:
    """Add Hard Eng's rules to security scans, skip generated files, limit each rule to 60 s."""
    directory = root / group["path"]
    if gate.get("role") == "security" and "p/python" in command:
        index = command.index("p/python") + 1
        command = [
            *command[:index],
            "--config",
            os.path.relpath(PYTHON_RULES, directory),
            "--exclude-rule",
            "python.lang.security.insecure-hash-algorithms.insecure-hash-algorithm-sha1",
            *command[index:],
        ]
    index = command.index("scan") if "scan" in command else 0
    if not index or Path(command[index - 1]).name.split("@")[0] != "semgrep":
        return command
    if gate.get("role") == "security":
        names = [
            path.relative_to(directory).as_posix()
            for path in repository_files(directory)
        ]
        unowned = unowned_paths(names, generated_sources(directory, names))
        prefix = git_prefix(directory)
        skipped = [
            "--exclude=/" + GLOB_SPECIAL.sub(r"\\\g<0>", prefix + name)
            for name in unowned
        ]
        rules = ["--config", os.path.relpath(RULES, directory), *skipped]
        # --strict fails valid code Semgrep parses only in part; the report check prints those gaps.
        rest = [part for part in command[index + 1 :] if part != "--strict"]
        command = [*command[: index + 1], *rules, *rest]
    if "--timeout" not in command:
        # Semgrep's 5 s per-rule limit times out under parallel load, and the report check then fails the gate.
        command = [*command[: index + 1], "--timeout", "60", *command[index + 1 :]]
    return command
