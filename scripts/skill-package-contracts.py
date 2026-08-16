#!/usr/bin/env python3
"""Validate every skill package with pinned YAML and CommonMark parsers."""

from __future__ import annotations

import json
import os
import re
import sys
import stat
from pathlib import Path
from pathlib import PurePosixPath
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
DETERMINISTIC_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

from bounded_run import run_captured  # noqa: E402


PARSER = ROOT / "scripts/skill-package-parser.mjs"
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ALLOWED_FRONTMATTER = {
    "name",
    "description",
    "license",
    "metadata",
    "allowed-tools",
    "disable-model-invocation",
    "argument-hint",
}
INTERFACE_KEYS = {
    "display_name",
    "short_description",
    "icon_small",
    "icon_large",
    "brand_color",
    "default_prompt",
}


class ContractError(ValueError):
    pass


def parsed(path: Path, mode: str) -> object:
    result = run_captured(
        ["node", str(PARSER), mode, str(path)],
        timeout=20,
        grace=1,
        env={key: os.environ[key] for key in ("PATH",) if key in os.environ},
    )
    if result.returncode:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise ContractError(detail or f"cannot parse {path.name}")
    try:
        return json.loads(result.stdout)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"parser returned invalid JSON for {path.name}") from error


def frontmatter(skill_file: Path) -> tuple[dict[str, object], str]:
    result = parsed(skill_file, "frontmatter")
    if not isinstance(result, dict):
        raise ContractError("frontmatter parser returned an invalid document")
    document = result.get("data")
    body = result.get("body")
    if not isinstance(document, dict) or not isinstance(body, str):
        raise ContractError("frontmatter parser returned an invalid document")
    unexpected = sorted(set(document) - ALLOWED_FRONTMATTER)
    if unexpected:
        raise ContractError(f"unsupported frontmatter keys: {unexpected}")
    metadata = document.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict)
        or any(not isinstance(key, str) or not isinstance(value, str) for key, value in metadata.items())
    ):
        raise ContractError("metadata must map string keys to string values")
    invocation = document.get("disable-model-invocation")
    if invocation is not None and not isinstance(invocation, bool):
        raise ContractError("disable-model-invocation must be true or false")
    for key in ALLOWED_FRONTMATTER - {"metadata", "disable-model-invocation"}:
        if key in document and not isinstance(document[key], str):
            raise ContractError(f"{key} must be a string")
    return document, body


def local_target(skill: Path, raw: str, base: Path | None = None) -> Path | None:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split(maxsplit=1)[0]
    if not target or target.startswith("#") or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
        return None
    target = unquote(target.split("#", 1)[0])
    pure = PurePosixPath(target)
    if pure.is_absolute() or any(part == "" for part in pure.parts):
        raise ContractError(f"resource path is not a literal child: {raw}")
    root = Path(os.path.abspath(skill))
    candidate = Path(os.path.abspath((base or skill) / Path(*pure.parts)))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"resource path escapes skill: {raw}") from exc
    cursor = root
    for part in relative.parts:
        cursor = cursor / part
        try:
            metadata = cursor.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(metadata.st_mode):
            raise ContractError(f"resource path contains a symlink: {raw}")
        if cursor != candidate and not stat.S_ISDIR(metadata.st_mode):
            raise ContractError(f"resource path has a non-directory ancestor: {raw}")
    return candidate


def markdown_targets(skill: Path, source: Path) -> tuple[Path, ...]:
    targets: list[Path] = []
    raw_targets = parsed(source, "markdown")
    if not isinstance(raw_targets, list) or not all(isinstance(item, str) for item in raw_targets):
        raise ContractError("Markdown parser returned invalid targets")
    for raw in raw_targets:
        target = local_target(skill, raw, source.parent)
        if target is None:
            continue
        if not target.exists():
            raise ContractError(f"{source.relative_to(skill)} references missing resource: {raw}")
        targets.append(target)
    return tuple(targets)


def metadata_yaml(skill: Path, name: str) -> None:
    path = skill / "agents/openai.yaml"
    if not path.is_file():
        raise ContractError("agents/openai.yaml is missing")
    result = parsed(path, "yaml")
    if not isinstance(result, dict) or not isinstance(result.get("data"), dict):
        raise ContractError("agents/openai.yaml parser returned an invalid document")
    sections = result["data"]
    styles = result.get("styles")
    if not isinstance(styles, dict):
        raise ContractError("agents/openai.yaml parser omitted scalar styles")
    if set(sections) - {"interface", "policy"}:
        raise ContractError("agents/openai.yaml has an unsupported section")
    if any(not isinstance(value, dict) for value in sections.values()):
        raise ContractError("agents/openai.yaml sections must be mappings")
    interface = sections.get("interface", {})
    policy = sections.get("policy", {})
    if set(interface) - INTERFACE_KEYS:
        raise ContractError("agents/openai.yaml has an unsupported interface field")
    if set(policy) - {"allow_implicit_invocation"}:
        raise ContractError("agents/openai.yaml has an unsupported policy field")
    for key, value in interface.items():
        if not isinstance(value, str) or styles.get(f"interface.{key}") != "QUOTE_DOUBLE":
            raise ContractError(f"agents/openai.yaml string must be quoted: interface.{key}")
    if "allow_implicit_invocation" in policy and not isinstance(policy["allow_implicit_invocation"], bool):
        raise ContractError("agents/openai.yaml has an invalid policy field")

    required = {"display_name", "short_description", "default_prompt"}
    missing = sorted(required - set(interface))
    if missing:
        raise ContractError(f"agents/openai.yaml missing interface fields: {missing}")
    display = interface["display_name"]
    short = interface["short_description"]
    prompt = interface["default_prompt"]
    if not isinstance(display, str) or not display.strip():
        raise ContractError("interface.display_name is empty")
    if not isinstance(short, str) or not 25 <= len(short) <= 64:
        raise ContractError("interface.short_description must be 25-64 characters")
    prompt_token = re.compile(
        rf"(?<![A-Za-z0-9$-]){re.escape(name)}(?![A-Za-z0-9-])"
    )
    if not isinstance(prompt, str) or prompt_token.search(prompt) is None:
        raise ContractError(
            f"interface.default_prompt must mention {name} without a runtime sigil"
        )
    color = interface.get("brand_color")
    if color is not None and (not isinstance(color, str) or re.fullmatch(r"#[0-9A-Fa-f]{6}", color) is None):
        raise ContractError("interface.brand_color must be a six-digit hex color")
    for icon in ("icon_small", "icon_large"):
        raw = interface.get(icon)
        if raw is None:
            continue
        target = local_target(skill, str(raw))
        if target is None or not target.is_file():
            raise ContractError(f"interface.{icon} references a missing asset")


def validate_skill(skill: Path, require_metadata: bool) -> None:
    if skill.is_symlink():
        raise ContractError("skill directory must not be a symlink")
    document, _ = frontmatter(skill / "SKILL.md")
    name = document.get("name")
    description = document.get("description")
    if not isinstance(name, str) or not NAME.fullmatch(name) or not 1 <= len(name) <= 64:
        raise ContractError("name must be 1-64 lowercase letters, digits, or single hyphens")
    if name != skill.name:
        raise ContractError(f"name must match parent directory: {skill.name}")
    if not isinstance(description, str) or not description or len(description) > 1024:
        raise ContractError("description must be 1-1024 characters")
    if "<" in description or ">" in description:
        raise ContractError("description cannot contain angle brackets")
    start = skill / "SKILL.md"
    direct = markdown_targets(skill, start)
    if require_metadata:
        metadata_yaml(skill, name)
    reachable = {Path(os.path.abspath(start))}
    pending = [target for target in direct if target.suffix.lower() == ".md"]
    while pending:
        source = pending.pop()
        if source in reachable:
            continue
        reachable.add(source)
        pending.extend(
            target for target in markdown_targets(skill, source)
            if target.suffix.lower() == ".md" and target not in reachable
        )
    references = skill / "references"
    if references.is_dir():
        orphaned = sorted(
            str(path.relative_to(skill))
            for path in references.rglob("*.md")
            if Path(os.path.abspath(path)) not in reachable
        )
        if orphaned:
            raise ContractError(f"orphan reference files: {orphaned}")


def validate_repository(root: Path = ROOT) -> tuple[int, int]:
    lock = json.loads((root / ".skill-lock.json").read_text(encoding="utf-8"))
    managed = set(lock.get("skills", {}))
    skill_root = root / "skills"
    directories = sorted(path for path in skill_root.iterdir() if path.is_dir())
    failures: list[str] = []
    local_count = 0
    for skill in directories:
        if not (skill / "SKILL.md").is_file():
            failures.append(f"{skill.name}: SKILL.md is missing")
            continue
        local = skill.name not in managed
        local_count += int(local)
        try:
            validate_skill(skill, require_metadata=local)
        except (ContractError, OSError, UnicodeError) as exc:
            failures.append(f"{skill.name}: {exc}")
    if failures:
        raise ContractError("; ".join(failures))
    return len(directories), local_count


def main() -> int:
    try:
        skill_count, local_count = validate_repository()
    except (ContractError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"skill-packages: FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"skill-packages: PASS | skills={skill_count} local_metadata={local_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
