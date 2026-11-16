"""Judge the settings that Ruff and Fallow print for each gate, so no spelling of a setting can hide a narrowed rule set."""

import subprocess
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from pathlib import Path

from command_words import unwrapped
from dart_boundaries import nested_package_patterns
from fallow_report import named_config, native_fallow_command
from fallow_resolved import default_config, fallow_hits
from gate_config import Gate, Group
from ruff_settings import ruff_invocations
from ruff_table import ruff_hits
from scope_check import left_out, nested_configs, refusal
from tool_setup import managed_command


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
        raise ValueError(
            f"HE-NO-SWITCH-OFF: ruff could not print its settings for this gate: {done.stderr.strip()}"
        )
    return done.stdout


def shown(
    prefix: list[str], arguments: list[str], directory: Path, timeout: float
) -> set[str]:
    """The files that ruff checks for this gate, relative to the gate folder."""
    done = subprocess.run(
        [*prefix, "check", "--show-files", *arguments],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if done.returncode:
        raise ValueError(
            f"HE-NO-SWITCH-OFF: ruff could not list the files of this gate: {done.stderr.strip()}"
        )
    base = directory.resolve()
    return {
        Path(line).resolve().relative_to(base).as_posix()
        for line in done.stdout.splitlines()
        if line.strip() and Path(line).resolve().is_relative_to(base)
    }


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
            self.fallow_run = self.pool.submit(default_config, self.timeout)
        return self.fallow_run


def group_roots(root: Path, every: list[Group]) -> frozenset[Path]:
    return frozenset((root / group["path"]).resolve() for group in every)


def ruff_tasks(
    root: Path,
    every: list[Group],
    group: Group,
    gate: Gate,
    defaults: Defaults,
    timeout: float,
) -> list[Task]:
    directory = root / group["path"]
    command = managed_command(gate["command"], directory)
    children = nested_package_patterns(group, every, gate.get("role", ""))
    roots = group_roots(root, every)
    return [
        partial(
            ruff_gate_hits,
            (tuple(prefix), arguments[1:], directory, gate, timeout),
            (children, roots),
            defaults.ruff(tuple(prefix)),
        )
        for prefix, arguments in ruff_invocations(command, directory)
        if arguments[:1] == ["check"]
    ]


def ruff_gate_hits(
    run: tuple[tuple[str, ...], list[str], Path, Gate, float],
    scope: tuple[frozenset[str], frozenset[Path]],
    baseline: Future[str],
) -> list[str]:
    children, roots = scope
    prefix, arguments, directory, gate, timeout = run
    settings = printed(list(prefix), arguments, directory, timeout)
    checked = shown(list(prefix), arguments, directory, timeout)
    hits = ruff_hits(settings, baseline.result(), gate.get("role"))
    left = left_out(directory, (".py", ".pyi"), checked, children)
    nested = nested_configs(directory, "ruff", roots)
    return [f"gate {gate['name']}: {hit}" for hit in [*hits, *refusal(left), *nested]]


def fallow_tasks(
    root: Path,
    every: list[Group],
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
    children = nested_package_patterns(group, every, gate.get("role", ""))
    return [
        partial(
            fallow_gate_hits,
            (directory, named_config(invocation), children, gate, timeout),
            group_roots(root, every),
            defaults.fallow(),
        )
    ]


def fallow_gate_hits(
    run: tuple[Path, str | None, frozenset[str], Gate, float],
    roots: frozenset[Path],
    defaults: Future[dict[str, object]],
) -> list[str]:
    directory, config, children, gate, timeout = run
    hits = fallow_hits(directory, config, children, defaults.result(), timeout)
    return [
        f"gate {gate['name']} ({directory.name}): {hit}"
        for hit in [*hits, *nested_configs(directory, "fallow", roots)]
    ]


def run_task(task: Task) -> list[str]:
    return task()


def validate_resolved(
    root: Path,
    groups: list[Group],
    timeout: float,
    every: list[Group] | None = None,
) -> None:
    """Run in the full check after the tools are installed; the Stop hook never runs it. `groups` are judged, `every` names all groups, so a parent knows its children."""
    every = groups if every is None else every
    with ThreadPoolExecutor(max_workers=8) as pool:
        defaults = Defaults(pool, root, timeout)
        tasks = [
            task
            for group in groups
            for gate in group["checks"]
            for task in (
                *ruff_tasks(root, every, group, gate, defaults, timeout),
                *fallow_tasks(root, every, group, gate, defaults, timeout),
            )
        ]
        refused = [hit for found in pool.map(run_task, tasks) for hit in found]
    if refused:
        raise ValueError(
            "HE-NO-SWITCH-OFF: The settings that Ruff and Fallow print switch a check off or drop files:\n"
            + "\n".join(f"  {line}" for line in dict.fromkeys(refused))
        )
