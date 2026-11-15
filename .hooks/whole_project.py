"""The full check judges every tracked file with the patterns of the changed-file checks, old code included."""

import subprocess
import tomllib
from pathlib import Path, PurePosixPath

from comments import (
    UNOWNED,
    pattern_switch_offs,
    security_hits,
    switch_off_refusal,
)
from gate_config import generated_sources
from project_files import GIT_LISTING

LINE_IGNORES = {".gitleaksignore", ".semgrepignore"}


def tracked_files(root: Path) -> list[str]:
    listed = subprocess.check_output(
        [*GIT_LISTING, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
    )
    return sorted(
        {
            name
            for name in listed.split("\0")
            if name and (root / name).is_file() and not (root / name).is_symlink()
        }
    )


def gitleaks_allowlists(name: str, text: str) -> list[str]:
    """Allowlist entries of a Gitleaks config; its detection rules stay."""
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    found = [
        f"{name} holds an allowlist table {key!r}"
        for key in ("allowlist", "allowlists")
        if key in config
    ]
    found += [
        f"{name} holds an allowlist in rule {rule.get('id', '?')!r}"
        for rule in config.get("rules", [])
        if "allowlist" in rule or "allowlists" in rule
    ]
    return found


def switch_offs(root: Path, texts: dict[str, str]) -> list[str]:
    owned = [name for name in texts if not name.startswith(UNOWNED)]
    skipped = generated_sources(root, owned)
    found: list[str] = []
    for name in (name for name in owned if name not in skipped):
        lines = list(enumerate(texts[name].splitlines(), 1))
        base = PurePosixPath(name).name
        found += security_hits(root, name, lines, "holds", base in LINE_IGNORES)
        found += pattern_switch_offs(root, name, lines, "holds")
        if base == ".gitleaks.toml":
            found += gitleaks_allowlists(name, texts[name])
    return found


def validate_whole_project(root: Path) -> None:
    texts = {
        name: (root / name).read_text(errors="replace") for name in tracked_files(root)
    }
    if found := switch_offs(root, texts):
        raise ValueError(switch_off_refusal(found))
