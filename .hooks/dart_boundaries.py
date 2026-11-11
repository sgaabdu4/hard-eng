"""Read a Dart package's Dart Decimate boundary rules and refuse unusable ones."""

import json
import subprocess
from pathlib import Path

SETTINGS_FILES = (
    ".dart-decimaterc",
    ".dart-decimaterc.json",
    ".dart-decimaterc.jsonc",
    "dart-decimate.toml",
    ".dart-decimate.toml",
)


def has_dart_file(directory: Path, prefix: str) -> bool:
    """Looks only below the prefix: this runs in every check, and a walk of all of lib/ is slow."""
    parent, _, start = prefix.rpartition("/")
    folder = directory / parent
    return folder.is_dir() and any(
        entry.suffix == ".dart"
        if entry.is_file()
        else next(entry.rglob("*.dart"), None) is not None
        for entry in folder.iterdir()
        if entry.name.startswith(start)
    )


def validate_dart_boundaries(
    command: list[str], directory: Path, timeout: float
) -> None:
    if command[:3] != ["dart-decimate", "check", "."]:
        return
    from tool_setup import managed_command

    try:
        output = subprocess.check_output(
            managed_command(["dart-decimate", "config", ".", "--format", "json"]),
            cwd=directory,
            text=True,
            timeout=timeout,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as error:
        lines = (error.stderr or error.output or "").strip().splitlines()
        raise ValueError(
            f"{directory.name}: dart-decimate config failed: " + " ".join(lines[-3:])
        ) from error
    settings = json.loads(output)["config"]
    boundaries = settings.get("boundaries")
    if (
        not isinstance(boundaries, list)
        or not boundaries
        or any(
            not isinstance(rule, dict)
            or not all(
                isinstance(rule.get(key), str)
                and rule[key].strip()
                and not any(mark in rule[key] for mark in "*?")
                for key in ("from", "disallow")
            )
            for rule in boundaries
        )
    ):
        raise ValueError(
            "Dart boundaries are missing or not usable: each rule needs a `from` and a "
            "`disallow` folder prefix of this project, with no `*` or `?`. Set "
            '"boundaries": [{"from": "lib/domain", "disallow": "lib/ui"}] with your own '
            "prefixes in the package's Dart Decimate settings file; if the package "
            "has none, make .dart-decimaterc.json for it"
        )
    settings_file = next(
        (name for name in SETTINGS_FILES if (directory / name).exists()),
        "the Dart Decimate settings file",
    )
    for rule in boundaries:
        for prefix in (rule["from"], rule["disallow"]):
            if not has_dart_file(directory, prefix):
                raise ValueError(
                    f"{directory.name}: the boundary prefix {prefix} in {settings_file} "
                    "matches no .dart file; correct the prefix or remove the rule"
                )
