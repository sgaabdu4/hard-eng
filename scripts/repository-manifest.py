#!/usr/bin/env python3
"""Generate and validate the repository's machine-owned inventory."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "repository.manifest.json"
SKILL_ROW = re.compile(r"^\| `([a-z0-9]+(?:-[a-z0-9]+)*)` \|", re.MULTILINE)


class ManifestError(ValueError):
    pass


def atomic_write(path: Path, content: bytes) -> None:
    parent = path.parent
    parent_metadata = parent.lstat()
    if parent.is_symlink() or not stat.S_ISDIR(parent_metadata.st_mode):
        raise ManifestError("manifest parent must be a real directory")
    try:
        target_metadata = path.lstat()
    except FileNotFoundError:
        mode = 0o644
    else:
        if path.is_symlink() or not stat.S_ISREG(target_metadata.st_mode):
            raise ManifestError("manifest target must be a regular no-follow file")
        mode = stat.S_IMODE(target_metadata.st_mode)
    temporary = parent / f".{path.name}.{secrets.token_hex(16)}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = -1
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            handle.write(content)
            handle.flush()
            os.fchmod(handle.fileno(), mode)
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_flags = os.O_RDONLY
        if hasattr(os, "O_DIRECTORY"):
            directory_flags |= os.O_DIRECTORY
        directory = os.open(parent, directory_flags)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def object_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ManifestError(f"cannot read {path.name}") from error
    if not isinstance(value, dict):
        raise ManifestError(f"{path.name} must contain an object")
    return value


def install_commands(setup: str) -> list[str]:
    match = re.search(r"(?ms)^install_tools\(\) \{\n(?P<body>.*?)^\}", setup)
    if match is None:
        raise ManifestError("setup install command owner is missing")
    commands = re.findall(r"(?m)^  need ([A-Za-z0-9._-]+)$", match.group("body"))
    if not commands or len(commands) != len(set(commands)):
        raise ManifestError("setup install commands are missing or duplicated")
    return commands


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    lock = object_json(root / ".skill-lock.json")
    managed_owner = lock.get("skills")
    if not isinstance(managed_owner, dict):
        raise ManifestError("skill lock has no managed skill map")
    managed = sorted(managed_owner)
    skill_root = root / "skills"
    names = sorted(
        path.name
        for path in skill_root.iterdir()
        if path.is_dir() and not path.is_symlink() and (path / "SKILL.md").is_file()
    )
    missing = sorted(set(managed) - set(names))
    if missing:
        raise ManifestError(f"managed skills are missing: {missing}")
    setup_manifest = object_json(root / "scripts/setup/manifest.json")
    requirements = setup_manifest.get("requirements")
    package = object_json(root / "package.json")
    engines = package.get("engines")
    if not isinstance(requirements, dict) or not isinstance(engines, dict):
        raise ManifestError("runtime requirement owners are invalid")
    node_min = requirements.get("node_min")
    node_engine = engines.get("node")
    if not isinstance(node_min, str) or not isinstance(node_engine, str):
        raise ManifestError("Node requirement owners are invalid")
    setup = (root / "setup.sh").read_text(encoding="utf-8")
    return {
        "generated_by": "scripts/repository-manifest.py",
        "owners": {
            "design": "DESIGN.md",
            "gates": "hard-eng.gates.json",
            "product": "PRODUCT.md",
            "setup": "scripts/setup/manifest.json",
        },
        "runtime": {"node_engine": node_engine, "node_min": node_min, "required_commands": install_commands(setup)},
        "schema_version": 1,
        "skills": {"count": len(names), "local": sorted(set(names) - set(managed)), "managed": managed, "names": names},
    }


def readme_errors(expected: dict[str, Any], readme: str) -> list[str]:
    skills = expected["skills"]
    runtime = expected["runtime"]
    errors: list[str] = []
    if f"| `skills/` | {skills['count']} focused skills " not in readme:
        errors.append("README skill count drifted")
    section = re.search(r"(?ms)^## Skills\n(?P<body>.*?)^## Requirements", readme)
    rows = set(SKILL_ROW.findall(section.group("body") if section else ""))
    if rows != set(skills["names"]):
        errors.append("README skill table drifted")
    node_parts = runtime["node_min"].split(".")
    displayed_node = ".".join(node_parts[:2]) + "+"
    if f"Node.js {displayed_node}" not in readme:
        errors.append("README Node requirement drifted")
    required = (
        "npx -y github:sgaabdu4/hard-eng --global",
        "npx -y github:sgaabdu4/hard-eng --repo",
        "npx -y github:sgaabdu4/hard-eng --repo --ignore",
        "Codex is required",
        "Claude Code and Copilot CLI are supported when installed",
    )
    for value in required:
        if value not in readme:
            errors.append(f"README setup contract drifted: {value}")
    return errors


def check(root: Path = ROOT) -> None:
    expected = build_manifest(root)
    actual = object_json(root / "repository.manifest.json")
    if actual != expected:
        raise ManifestError("repository.manifest.json is stale; run generate")
    readme = (root / "README.md").read_text(encoding="utf-8")
    errors = readme_errors(expected, readme)
    if errors:
        raise ManifestError("; ".join(errors))
    for owner in expected["owners"].values():
        if not (root / owner).is_file():
            raise ManifestError(f"repository owner is missing: {owner}")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("check", "generate"), nargs="?", default="check")
    return value


def main() -> int:
    arguments = parser().parse_args()
    try:
        expected = build_manifest()
        if arguments.command == "generate":
            atomic_write(MANIFEST, (json.dumps(expected, indent=2, sort_keys=True) + "\n").encode())
        else:
            check()
    except (ManifestError, OSError, UnicodeError) as error:
        print(f"repository-manifest: FAIL: {error}", file=sys.stderr)
        return 1
    print(f"repository-manifest: PASS skills={expected['skills']['count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
