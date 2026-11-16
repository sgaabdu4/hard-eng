"""Judge the config Fallow prints for a gate: no check switched off and no file dropped without a reason."""

import json
import subprocess
import tempfile
from pathlib import Path

from scope_check import left_out, refusal


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


def default_rules(timeout: float) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="hard-eng-fallow-") as empty:
        rules = printed_config(Path(empty), None, timeout).get("rules")
    return rules if isinstance(rules, dict) else {}


def rule_sets(config: dict[str, object]) -> list[dict[str, object]]:
    overrides = config.get("overrides")
    sets = (
        [config.get("rules")]
        + [item.get("rules") for item in overrides if isinstance(item, dict)]
        if isinstance(overrides, list)
        else [config.get("rules")]
    )
    return [rules for rules in sets if isinstance(rules, dict)]


def switched_off(config: dict[str, object], defaults: dict[str, object]) -> list[str]:
    hits = [
        f"rule {name} is off"
        for rules in rule_sets(config)
        for name, level in rules.items()
        if level == "off" and defaults.get(name) != "off"
    ]
    if config.get("ignoreFindings"):
        hits.append("ignoreFindings hides findings")
    hits += [
        f"entry {entry!r} marks every file it matches as used"
        for entry in as_list(config.get("entry"))
        if isinstance(entry, str) and "**" in entry
    ]
    duplicates = config.get("duplicates")
    if isinstance(duplicates, dict) and duplicates.get("enabled") is False:
        hits.append("duplicates.enabled is false")
    return hits


def as_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


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
    return {name for name in as_list(files) if isinstance(name, str)}


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
    return [*switched_off(printed, defaults), *refusal(left)]
