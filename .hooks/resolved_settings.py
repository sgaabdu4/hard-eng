"""Judge the settings that Ruff and Fallow print for each gate, so no spelling of a setting can hide a narrowed rule set."""

import re
import subprocess
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from pathlib import Path

from command_words import unwrapped
from dart_boundaries import nested_package_patterns
from fallow_report import named_config, native_fallow_command
from fallow_resolved import default_rules, fallow_hits
from gate_config import Gate, Group
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


Task = Callable[[], list[str]]


class Defaults:
    """Each tool's own default settings, printed once and shared by every gate that needs them."""

    def __init__(self, pool: ThreadPoolExecutor, root: Path, timeout: float) -> None:
        self.pool, self.root, self.timeout = pool, root, timeout
        self.ruff_runs: dict[tuple[str, ...], Future[str]] = {}
        self.fallow_run: Future[dict[str, object]] | None = None

    def ruff(self, prefix: tuple[str, ...]) -> Future[str]:
        if prefix not in self.ruff_runs:
            self.ruff_runs[prefix] = self.pool.submit(
                printed, list(prefix), ["--isolated"], self.root, self.timeout
            )
        return self.ruff_runs[prefix]

    def fallow(self) -> Future[dict[str, object]]:
        if self.fallow_run is None:
            self.fallow_run = self.pool.submit(default_rules, self.timeout)
        return self.fallow_run


def ruff_tasks(
    root: Path, group: Group, gate: Gate, defaults: Defaults, timeout: float
) -> list[Task]:
    directory = root / group["path"]
    command = managed_command(gate["command"], directory)
    return [
        partial(
            ruff_gate_hits,
            (tuple(prefix), arguments[1:], directory, gate, timeout),
            defaults.ruff(tuple(prefix)),
        )
        for prefix, arguments in ruff_invocations(command, directory)
        if arguments[:1] == ["check"]
    ]


def ruff_gate_hits(
    run: tuple[tuple[str, ...], list[str], Path, Gate, float], baseline: Future[str]
) -> list[str]:
    prefix, arguments, directory, gate, timeout = run
    settings = printed(list(prefix), arguments, directory, timeout)
    return [
        f"gate {gate['name']}: {hit}"
        for hit in ruff_hits(settings, baseline.result(), gate.get("role"))
    ]


def fallow_tasks(
    root: Path,
    groups: list[Group],
    group: Group,
    gate: Gate,
    defaults: Defaults,
    timeout: float,
) -> list[Task]:
    directory = root / group["path"]
    command = unwrapped(managed_command(gate["command"], directory), directory)
    invocation = native_fallow_command(command)
    if invocation is None:
        return []
    children = nested_package_patterns(group, groups, gate.get("role", ""))
    return [
        partial(
            fallow_gate_hits,
            (directory, named_config(invocation), children, gate, timeout),
            defaults.fallow(),
        )
    ]


def fallow_gate_hits(
    run: tuple[Path, str | None, frozenset[str], Gate, float],
    defaults: Future[dict[str, object]],
) -> list[str]:
    directory, config, children, gate, timeout = run
    return [
        f"gate {gate['name']} ({directory.name}): {hit}"
        for hit in fallow_hits(directory, config, children, defaults.result(), timeout)
    ]


def run_task(task: Task) -> list[str]:
    return task()


def validate_resolved(root: Path, groups: list[Group], timeout: float) -> None:
    """Run in the full check after the tools are installed; the Stop hook never runs it."""
    with ThreadPoolExecutor(max_workers=8) as pool:
        defaults = Defaults(pool, root, timeout)
        tasks = [
            task
            for group in groups
            for gate in group["checks"]
            for task in (
                *ruff_tasks(root, group, gate, defaults, timeout),
                *fallow_tasks(root, groups, group, gate, defaults, timeout),
            )
        ]
        refused = [hit for found in pool.map(run_task, tasks) for hit in found]
    if refused:
        raise ValueError(
            "HE-NO-SWITCH-OFF: The settings that Ruff and Fallow print switch a check off or drop files:\n"
            + "\n".join(f"  {line}" for line in dict.fromkeys(refused))
        )
