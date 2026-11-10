"""Read a Dart package's Dart Decimate boundary rules and refuse unusable ones."""

import json
import subprocess
from pathlib import Path


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
