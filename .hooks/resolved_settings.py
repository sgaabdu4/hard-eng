"""Judge the settings that Ruff prints for each gate, so no spelling of a setting can hide a narrowed rule set."""

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from gate_config import Group
from ruff_settings import ruff_invocations
from tool_setup import managed_command

COMPLEXITY_LIMITS = {
    "linter.mccabe.max_complexity": 10,
    "linter.pylint.max_branches": 12,
    "linter.pylint.max_statements": 50,
}
COMPLEXITY_CODES = {"C901", "PLR0912", "PLR0915"}
EMPTY_KEYS = (
    "linter.per_file_ignores",
    "file_resolver.extend_exclude",
    "linter.exclude",
)
CODE = re.compile(r"\((\w+)\)")


def printed(
    prefix: list[str], arguments: list[str], directory: Path, timeout: float
) -> str:
    done = subprocess.run(
        [*prefix, "check", "--show-settings", *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if done.returncode:
        raise RuntimeError(f"ruff could not print its settings: {done.stderr}")
    return done.stdout


def assignment(text: str, key: str) -> list[str]:
    """The entries of one printed setting, or none when it is empty or missing."""
    lines = text.splitlines()
    for number, line in enumerate(lines):
        if line.startswith(f"{key} = "):
            rest = line.removeprefix(f"{key} = ")
            if rest in ("[]", "{}"):
                return []
            if rest not in ("[", "{"):
                return [rest]
            body = []
            for inner in lines[number + 1 :]:
                if inner in ("]", "}"):
                    break
                body.append(inner.strip().rstrip(","))
            return body
    return []


def enabled(text: str) -> set[str]:
    return {
        found[1]
        for line in assignment(text, "linter.rules.enabled")
        if (found := CODE.search(line))
    }


def limit_hits(settings: str) -> list[str]:
    hits = []
    for key, limit in COMPLEXITY_LIMITS.items():
        value = assignment(settings, key)
        if not value or not value[0].isdigit() or int(value[0]) > limit:
            hits.append(
                f"the resolved {key} is {value[0] if value else 'missing'}, above the limit {limit}"
            )
    return hits


def lacking(lost: set[str], what: str) -> str:
    names = sorted(lost)
    more = f" and {len(names) - 3} more" if len(names) > 3 else ""
    return (
        f"the resolved rule set lacks {len(names)} {what}: {', '.join(names[:3])}{more}"
    )


def ruff_hits(settings: str, defaults: str, role: object) -> list[str]:
    """What the resolved settings of one gate drop, compared with Ruff's own defaults."""
    hits = [
        f"the resolved {key} is not empty"
        for key in EMPTY_KEYS
        if assignment(settings, key)
    ]
    skipped = set(assignment(settings, "file_resolver.exclude"))
    if skipped - set(assignment(defaults, "file_resolver.exclude")):
        hits.append(
            "the resolved file_resolver.exclude skips more than Ruff's own folders"
        )
    codes = enabled(settings)
    if role == "lint" and (lost := enabled(defaults) - codes):
        hits.append(lacking(lost, "of Ruff's default rules"))
    if role == "complexity":
        if lost := COMPLEXITY_CODES - codes:
            hits.append(lacking(lost, "of the complexity rules"))
        hits += limit_hits(settings)
    return hits


def gate_jobs(
    root: Path, groups: list[Group]
) -> list[tuple[str, list[str], list[str], Path, str | None]]:
    jobs = []
    for group in groups:
        directory = root / group["path"]
        for gate in group["checks"]:
            command = managed_command(gate["command"], directory)
            for prefix, arguments in ruff_invocations(command, directory):
                if arguments[:1] == ["check"]:
                    jobs.append(
                        (
                            gate["name"],
                            prefix,
                            arguments[1:],
                            directory,
                            gate.get("role"),
                        )
                    )
    return jobs


def validate_resolved(root: Path, groups: list[Group], timeout: float) -> None:
    """Run in the full check after the tools are installed; the Stop hook never runs it."""
    jobs = gate_jobs(root, groups)
    if not jobs:
        return
    with ThreadPoolExecutor(max_workers=8) as pool:
        base = {
            tuple(prefix): pool.submit(printed, prefix, ["--isolated"], root, timeout)
            for _, prefix, _, _, _ in jobs
        }
        runs = [
            pool.submit(printed, prefix, arguments, directory, timeout)
            for _, prefix, arguments, directory, _ in jobs
        ]
        refused = [
            f"gate {name}: {hit}"
            for (name, prefix, _, _, role), run in zip(jobs, runs, strict=True)
            for hit in ruff_hits(run.result(), base[tuple(prefix)].result(), role)
        ]
    if refused:
        raise ValueError(
            "HE-NO-SWITCH-OFF: A ruff gate must keep Ruff's default rules and its own limits:\n"
            + "\n".join(f"  {line}" for line in refused)
        )
