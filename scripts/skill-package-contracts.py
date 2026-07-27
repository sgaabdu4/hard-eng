#!/usr/bin/env python3
"""Validate every skill package without relying on host-installed YAML modules."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
KEY = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?:[ ](.*))?$")
NESTED_KEY = re.compile(r"^  ([A-Za-z][A-Za-z0-9_.-]*):(?:[ ](.*))?$")
LINK = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
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


def scalar(value: str | None, continuation: list[str], field: str) -> str:
    raw = "" if value is None else value
    if raw in {"|", "|-", ">", ">-"}:
        if not continuation:
            raise ContractError(f"{field} block scalar is empty")
        parts = [line[2:] for line in continuation if line.strip()]
        result = "\n".join(parts) if raw.startswith("|") else " ".join(part.strip() for part in parts)
        return result.strip()
    if continuation:
        raise ContractError(f"{field} has unsupported nested content")
    raw = raw.strip()
    if not raw:
        return ""
    if raw.startswith('"'):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ContractError(f"{field} has invalid quoted value") from exc
        if not isinstance(parsed, str):
            raise ContractError(f"{field} must be a string")
        return parsed
    if raw.startswith("'"):
        if len(raw) < 2 or not raw.endswith("'"):
            raise ContractError(f"{field} has invalid quoted value")
        return raw[1:-1].replace("''", "'")
    lowered = raw.casefold()
    ambiguous = {
        "null", "~", "true", "false", "yes", "no", "on", "off",
        ".nan", ".inf", "+.inf", "-.inf",
    }
    if (
        raw[0] in "-?:,[]{}#&*!|>'\"%@`"
        or ": " in raw
        or " #" in raw
        or lowered in ambiguous
        or re.fullmatch(r"[-+]?(?:\d[\d_]*)?(?:\.\d[\d_]*)?(?:e[-+]?\d+)?", raw, re.I)
    ):
        raise ContractError(f"{field} has unsafe plain YAML scalar; quote it")
    return raw


def frontmatter(skill_file: Path) -> tuple[dict[str, object], str]:
    text = skill_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ContractError("SKILL.md missing opening frontmatter delimiter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise ContractError("SKILL.md missing closing frontmatter delimiter") from exc

    entries: dict[str, tuple[str | None, list[str]]] = {}
    current: str | None = None
    for line in lines[1:closing]:
        if "\t" in line:
            raise ContractError("frontmatter contains a tab")
        if not line.strip():
            continue
        if line.startswith(" "):
            if current is None or not line.startswith("  "):
                raise ContractError("frontmatter indentation is invalid")
            entries[current][1].append(line)
            continue
        match = KEY.fullmatch(line)
        if match is None:
            raise ContractError(f"invalid frontmatter line: {line}")
        current = match.group(1)
        if current in entries:
            raise ContractError(f"duplicate frontmatter key: {current}")
        entries[current] = (match.group(2), [])

    unexpected = sorted(set(entries) - ALLOWED_FRONTMATTER)
    if unexpected:
        raise ContractError(f"unsupported frontmatter keys: {unexpected}")

    parsed: dict[str, object] = {}
    for key, (value, continuation) in entries.items():
        if key == "metadata":
            if value not in {None, ""}:
                raise ContractError("metadata must be a mapping")
            metadata: dict[str, str] = {}
            for line in continuation:
                match = NESTED_KEY.fullmatch(line)
                if match is None:
                    raise ContractError("metadata contains unsupported nested content")
                nested = match.group(1)
                if nested in metadata:
                    raise ContractError(f"duplicate metadata key: {nested}")
                metadata[nested] = scalar(match.group(2), [], f"metadata.{nested}")
            parsed[key] = metadata
        elif key == "disable-model-invocation":
            raw = "" if value is None else value.strip()
            if continuation or raw not in {"true", "false"}:
                raise ContractError("disable-model-invocation must be true or false")
            parsed[key] = raw == "true"
        else:
            parsed[key] = scalar(value, continuation, key)

    body = "\n".join(lines[closing + 1 :]).strip()
    if not body:
        raise ContractError("SKILL.md body is empty")
    return parsed, body


def local_target(skill: Path, raw: str, base: Path | None = None) -> Path | None:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split(maxsplit=1)[0]
    if not target or target.startswith("#") or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
        return None
    target = unquote(target.split("#", 1)[0])
    resolved = ((base or skill) / target).resolve()
    try:
        resolved.relative_to(skill.resolve())
    except ValueError as exc:
        raise ContractError(f"resource path escapes skill: {raw}") from exc
    return resolved


def markdown_targets(skill: Path, source: Path) -> tuple[Path, ...]:
    targets: list[Path] = []
    for raw in LINK.findall(source.read_text(encoding="utf-8")):
        target = local_target(skill, raw, source.parent)
        if target is None:
            continue
        if not target.is_file():
            raise ContractError(f"{source.relative_to(skill)} references missing resource: {raw}")
        targets.append(target)
    return tuple(targets)


def metadata_yaml(skill: Path, name: str) -> None:
    path = skill / "agents/openai.yaml"
    if not path.is_file():
        raise ContractError("agents/openai.yaml is missing")
    sections: dict[str, dict[str, object]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if "\t" in line:
            raise ContractError("agents/openai.yaml contains a tab")
        if not line.strip():
            continue
        if not line.startswith(" "):
            match = re.fullmatch(r"([a-z_]+):", line)
            if match is None or match.group(1) not in {"interface", "policy"}:
                raise ContractError(f"agents/openai.yaml has unsupported section: {line}")
            current = match.group(1)
            if current in sections:
                raise ContractError(f"agents/openai.yaml duplicates section: {current}")
            sections[current] = {}
            continue
        if current is None or not line.startswith("  ") or line.startswith("   "):
            raise ContractError("agents/openai.yaml indentation is invalid")
        match = NESTED_KEY.fullmatch(line)
        if match is None or match.group(2) is None:
            raise ContractError(f"agents/openai.yaml has invalid field: {line}")
        key, raw = match.group(1), match.group(2)
        if key in sections[current]:
            raise ContractError(f"agents/openai.yaml duplicates field: {current}.{key}")
        if current == "interface":
            if key not in INTERFACE_KEYS:
                raise ContractError(f"agents/openai.yaml has unsupported interface field: {key}")
            if not raw.startswith('"'):
                raise ContractError(f"agents/openai.yaml string must be quoted: interface.{key}")
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ContractError(f"agents/openai.yaml has invalid string: interface.{key}") from exc
            if not isinstance(value, str):
                raise ContractError(f"agents/openai.yaml field must be a string: interface.{key}")
        else:
            if key != "allow_implicit_invocation" or raw not in {"true", "false"}:
                raise ContractError(f"agents/openai.yaml has invalid policy field: {key}")
            value = raw == "true"
        sections[current][key] = value

    interface = sections.get("interface", {})
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
        reachable = {start.resolve()}
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
        references = (skill / "references")
        if references.is_dir():
            orphaned = sorted(
                str(path.relative_to(skill))
                for path in references.rglob("*.md")
                if path.resolve() not in reachable
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
