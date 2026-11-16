"""Judge the config Fallow prints for a gate: no check switched off and no file dropped without a reason."""

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from fallow_table import judge
from scope_check import glob_regex, left_out, refusal, tracked


def printed_config(
    directory: Path, config: str | None, timeout: float
) -> dict[str, object]:
    done = subprocess.run(
        ["fallow", "config", *(["-c", config] if config else [])],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if done.returncode:
        raise ValueError(
            f"HE-NO-SWITCH-OFF: fallow cannot read its config: {done.stderr.strip()}"
        )
    return json.loads(done.stdout)


def default_config(timeout: float) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="hard-eng-fallow-") as empty:
        return printed_config(Path(empty), None, timeout)


def pattern_hits(
    directory: Path, children: frozenset[str]
) -> Callable[[list[str]], list[str]]:
    """A check for the patterns of one setting: each tracked source file that a pattern drops must be generated or belong to a child group."""

    def drop(patterns: list[str]) -> list[str]:
        if not patterns:
            return []
        names = tracked(directory, FALLOW_SUFFIXES)
        regexes = [glob_regex(pattern) for pattern in patterns]
        matched = {name for name in names if any(r.fullmatch(name) for r in regexes)}
        left = left_out(
            directory, FALLOW_SUFFIXES, set(names) - matched, children, FALLOW_SKIPPED
        )
        return [f"drops {name}" for name in left[:1]] if left else []

    return drop


FALLOW_SUFFIXES = (
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".mts",
    ".cts",
    ".vue",
    ".svelte",
    ".astro",
)
FALLOW_SKIPPED = frozenset(
    {
        "node_modules",
        "dist",
        "build",
        "coverage",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".output",
        ".turbo",
        ".cache",
    }
)


def listed_files(directory: Path, config: str | None, timeout: float) -> set[str]:
    """The files Fallow discovers for this gate."""
    done = subprocess.run(
        [
            "fallow",
            "list",
            "--files",
            "--format",
            "json",
            *(["-c", config] if config else []),
        ],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if done.returncode:
        raise ValueError(
            f"HE-NO-SWITCH-OFF: fallow cannot list the files of this gate: {done.stderr.strip()}"
        )
    files = json.loads(done.stdout).get("files")
    return (
        {name for name in files if isinstance(name, str)}
        if isinstance(files, list)
        else set()
    )


def entry_sources(
    directory: Path, printed: dict[str, object], timeout: float
) -> dict[str, str]:
    """Each entry point that Fallow finds with no manual `entry` list, with the plugin or package script that finds it."""
    without = {name: value for name, value in printed.items() if name != "entry"}
    with tempfile.TemporaryDirectory(prefix="hard-eng-fallow-") as folder:
        path = Path(folder) / "config.json"
        path.write_text(json.dumps(without))
        done = subprocess.run(
            ["fallow", "list", "--entry-points", "--format", "json", "-c", str(path)],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    if done.returncode:
        raise ValueError(
            f"HE-NO-SWITCH-OFF: fallow cannot list the entry points of this gate: {done.stderr.strip()}"
        )
    items = json.loads(done.stdout).get("entry_points")
    return {
        item["path"]: str(item.get("source", ""))
        for item in items or []
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }


def covering(checked: set[str], found: dict[str, str]) -> Callable[[str], str]:
    """For an entry glob, the names of what finds all its files already, or nothing when any file is found only by the glob."""

    def covered(glob: str) -> str:
        pattern = glob_regex(glob)
        matched = {name for name in checked if pattern.fullmatch(name)}
        if not matched or not matched <= found.keys():
            return ""
        return ", ".join(sorted({found[name] for name in matched}))

    return covered


def fallow_hits(
    directory: Path,
    config: str | None,
    children: frozenset[str],
    defaults: dict[str, object],
    timeout: float,
) -> list[str]:
    printed = printed_config(directory, config, timeout)
    checked = listed_files(directory, config, timeout)
    left = left_out(directory, FALLOW_SUFFIXES, checked, children, FALLOW_SKIPPED)
    drop = pattern_hits(directory, children)
    found = entry_sources(directory, printed, timeout) if printed.get("entry") else {}
    covered = covering(checked, found)
    return [*judge(printed, defaults, drop, covered), *refusal(left)]
