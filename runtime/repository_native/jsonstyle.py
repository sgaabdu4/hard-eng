"""Render JSON the way Biome and Prettier print it, so a repository's own format check accepts generated files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_WIDTH = 80
DEFAULT_INDENT_WIDTH = 2
BIOME_CONFIGS = ("biome.json", "biome.jsonc")
SCALARS = (str, int, float, bool, type(None))


@dataclass(frozen=True)
class JsonStyle:
    width: int = DEFAULT_WIDTH
    indent: str = " " * DEFAULT_INDENT_WIDTH
    indent_columns: int = DEFAULT_INDENT_WIDTH


def style_for(path: Path) -> JsonStyle:
    """The formatter settings of the repository that owns path; Prettier defaults when nothing is configured."""
    directory = path if path.is_dir() else path.parent
    for candidate in (directory, *directory.parents):
        style = _biome_style(candidate)
        if style is not None:
            return style
        if (candidate / ".git").exists():
            break
    return JsonStyle()


def render(value: object, style: JsonStyle, *, sort_keys: bool = False) -> str:
    return _render(value, style, 0, 0, sort_keys) + "\n"


def _biome_style(directory: Path) -> JsonStyle | None:
    for name in BIOME_CONFIGS:
        config = directory / name
        if not config.is_file():
            continue
        try:
            value = json.loads(_without_comments(config.read_text(encoding="utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError):
            value = {}
        formatter = {**_section(value, "formatter"), **_section(value, "json", "formatter")}
        indent_width = _positive(formatter.get("indentWidth"), DEFAULT_INDENT_WIDTH)
        width = _positive(formatter.get("lineWidth"), DEFAULT_WIDTH)
        if formatter.get("indentStyle", "tab") == "space":
            return JsonStyle(width=width, indent=" " * indent_width, indent_columns=indent_width)
        return JsonStyle(width=width, indent="\t", indent_columns=indent_width)
    return None


def _positive(value: object, default: int) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    return default


def _section(value: object, *keys: str) -> dict[str, object]:
    for key in keys:
        if not isinstance(value, dict):
            return {}
        value = value.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _without_comments(text: str) -> str:
    kept: list[str] = []
    index = 0
    in_string = False
    while index < len(text):
        char = text[index]
        if in_string:
            kept.append(char)
            if char == "\\" and index + 1 < len(text):
                index += 1
                kept.append(text[index])
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
            kept.append(char)
        elif text.startswith("//", index):
            end = text.find("\n", index)
            index = len(text) if end < 0 else end
            continue
        elif text.startswith("/*", index):
            end = text.find("*/", index + 2)
            index = len(text) if end < 0 else end + 2
            continue
        else:
            kept.append(char)
        index += 1
    return "".join(kept)


def _render(value: object, style: JsonStyle, depth: int, used: int, sort_keys: bool) -> str:
    """used = columns already taken on the line before value, plus the comma that follows it."""
    if isinstance(value, dict):
        if not value:
            return "{}"
        keys = sorted(value) if sort_keys else list(value)
        lines: list[str] = []
        for position, key in enumerate(keys):
            label = f"{_scalar(key)}: "
            prefix = style.indent_columns * (depth + 1) + len(label) + (1 if position < len(keys) - 1 else 0)
            lines.append(style.indent * (depth + 1) + label + _render(value[key], style, depth + 1, prefix, sort_keys))
        return "{\n" + ",\n".join(lines) + "\n" + style.indent * depth + "}"
    if isinstance(value, list):
        if not value:
            return "[]"
        if all(isinstance(item, SCALARS) for item in value):
            inline = "[" + ", ".join(_scalar(item) for item in value) + "]"
            if used + len(inline) <= style.width:
                return inline
        lines = []
        for position, item in enumerate(value):
            prefix = style.indent_columns * (depth + 1) + (1 if position < len(value) - 1 else 0)
            lines.append(style.indent * (depth + 1) + _render(item, style, depth + 1, prefix, sort_keys))
        return "[\n" + ",\n".join(lines) + "\n" + style.indent * depth + "]"
    return _scalar(value)


def _scalar(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)
