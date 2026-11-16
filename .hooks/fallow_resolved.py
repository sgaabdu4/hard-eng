"""Judge the config Fallow prints for a gate: no check switched off and no file dropped without a reason."""

import json
import re
import subprocess
import tempfile
from pathlib import Path

from fallow_settings import HOOKS_PATTERN
from gate_config import generated_sources
from project_files import GIT_LISTING


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


def glob_regex(pattern: str) -> re.Pattern[str]:
    """A glob as Fallow reads it; `*` is taken to cross folders, so a pattern never drops fewer files than it names."""
    pattern = pattern + "**" if pattern.endswith("/") else pattern
    out = "" if "/" in pattern else "(?:.*/)?"
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out += "(?:.*/)?"
            index += 3
        elif pattern[index] == "*":
            out += ".*"
            index += 2 if pattern.startswith("**", index) else 1
        elif pattern[index] == "?":
            out += "[^/]"
            index += 1
        else:
            out += re.escape(pattern[index])
            index += 1
    return re.compile(out)


def tracked(directory: Path) -> list[str]:
    listed = subprocess.run(
        [*GIT_LISTING, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return [name for name in listed.split("\0") if name]


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


def dropped(
    config: dict[str, object], directory: Path, children: frozenset[str]
) -> list[str]:
    """Patterns that drop a file which is neither marked linguist-generated nor inside a nested package that runs Fallow itself."""
    patterns = [
        pattern
        for pattern in as_list(config.get("ignorePatterns"))
        if isinstance(pattern, str) and pattern != HOOKS_PATTERN
    ]
    if not patterns:
        return []
    names = tracked(directory)
    generated = generated_sources(directory, names, generated_only=True)
    nested = [glob_regex(child) for child in children]
    hits = []
    for pattern in patterns:
        regex = glob_regex(pattern)
        left = [
            name
            for name in names
            if regex.fullmatch(name)
            and name not in generated
            and not any(child.fullmatch(name) for child in nested)
        ]
        if left:
            more = f" and {len(left) - 1} more" if len(left) > 1 else ""
            hits.append(
                f"ignorePatterns entry {pattern!r} drops {left[0]}{more}, which no linguist-generated mark or nested Fallow gate covers"
            )
    return hits


def fallow_hits(
    directory: Path,
    config: str | None,
    children: frozenset[str],
    defaults: dict[str, object],
    timeout: float,
) -> list[str]:
    printed = printed_config(directory, config, timeout)
    return [*switched_off(printed, defaults), *dropped(printed, directory, children)]
