"""Refuse a Fallow settings file that raises a health limit, skips files from the complexity analysis or lowers a complexity rule."""

import tomllib

from fallow_report import HEALTH_LIMITS

SETTINGS_FILES = {".fallowrc.json", ".fallowrc.jsonc", "fallow.toml", ".fallow.toml"}
LIMIT_KEYS = {
    "maxCyclomatic": "max_cyclomatic_threshold",
    "maxCognitive": "max_cognitive_threshold",
    "maxCrap": "max_crap_threshold",
    "maxUnitSize": "max_unit_size_threshold",
}


def read_settings(name: str, text: str) -> dict[str, object]:
    if name.endswith(".toml"):
        try:
            return tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            return {}
    from untrusted_input import jsonc_config

    try:
        return jsonc_config(name, text)
    except (ValueError, TypeError):
        return {}


def tables(value: object) -> list[dict[str, object]]:
    items = value if isinstance(value, list) else [value]
    return [item for item in items if isinstance(item, dict)]


def limit_findings(table: dict[str, object]) -> list[tuple[str, str]]:
    found = []
    for key, snake in LIMIT_KEYS.items():
        value = table.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if value > HEALTH_LIMITS[snake] or (key == "maxCrap" and value <= 0):
            found.append((key, f"to {value}, outside the limit {HEALTH_LIMITS[snake]}"))
    return found


def health_findings(config: dict[str, object]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for health in tables(config.get("health")):
        found += limit_findings(health)
        if health.get("ignore"):
            found.append(("ignore", "to skip files from the complexity analysis"))
        for override in tables(health.get("thresholdOverrides")):
            found += limit_findings(override)
    return found


def rule_findings(config: dict[str, object]) -> list[tuple[str, str]]:
    sets = tables(config.get("rules"))
    sets += [
        rules
        for item in tables(config.get("overrides"))
        for rules in tables(item.get("rules"))
    ]
    return [
        (key, f"to {level!r}, below error")
        for rules in sets
        for key, level in rules.items()
        if key.startswith("complexity-") and level != "error"
    ]


def settings_switch_offs(name: str, text: str) -> list[str]:
    """One hit for each key line that raises a limit, lists ignored files or sets a complexity rule below error."""
    config = read_settings(name, text)
    lines = text.splitlines()
    used: set[int] = set()
    found: list[str] = []
    for key, reason in [*health_findings(config), *rule_findings(config)]:
        number = next(
            (n for n, line in enumerate(lines, 1) if key in line and n not in used), 1
        )
        used.add(number)
        found.append(f"{name}:{number} sets {key} {reason}")
    return found
