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


def settings_switch_offs(name: str, text: str) -> list[str]:
    """One hit for each key line that raises a limit, lists ignored files or sets a complexity rule below error."""
    config = read_settings(name, text)
    lines = text.splitlines()
    used: set[int] = set()
    found: list[str] = []

    def hit(key: str, reason: str) -> None:
        number = next(
            (n for n, line in enumerate(lines, 1) if key in line and n not in used), 1
        )
        used.add(number)
        found.append(f"{name}:{number} sets {key} {reason}")

    def limits(table: dict[str, object]) -> None:
        for key, snake in LIMIT_KEYS.items():
            value = table.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if value > HEALTH_LIMITS[snake] or (key == "maxCrap" and value <= 0):
                hit(key, f"to {value}, outside the limit {HEALTH_LIMITS[snake]}")

    for health in tables(config.get("health")):
        limits(health)
        if health.get("ignore"):
            hit("ignore", "to skip files from the complexity analysis")
        for override in tables(health.get("thresholdOverrides")):
            limits(override)
    sets = [*tables(config.get("rules"))]
    sets += [
        rules
        for item in tables(config.get("overrides"))
        for rules in tables(item.get("rules"))
    ]
    for rules in sets:
        for key, level in rules.items():
            if key.startswith("complexity-") and level != "error":
                hit(key, f"to {level!r}, below error")
    return found
