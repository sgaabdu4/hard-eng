#!/usr/bin/env python3
"""Converge the Copilot no-authorship setting without discarding JSONC comments."""

from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

from jsonc import JsoncError, loads


KEY = "includeCoAuthoredBy"
DRIFT = 5


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup:copilot-settings: {message}")


def skip_ignored(text: str, index: int) -> int:
    while index < len(text):
        if text[index].isspace():
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index + 2)
            index = len(text) if newline == -1 else newline + 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end == -1:
                fail("settings file contains an unterminated comment")
            index = end + 2
            continue
        return index
    return index


def parse_string(text: str, index: int) -> tuple[str, int]:
    if index >= len(text) or text[index] != '"':
        fail("settings object contains a non-string key")
    start = index
    index += 1
    escaped = False
    while index < len(text):
        character = text[index]
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == '"':
            try:
                return loads(text[start : index + 1]), index + 1  # type: ignore[return-value]
            except JsoncError as error:
                fail(f"invalid settings string: {error}")
        index += 1
    fail("settings object contains an unterminated string")


def skip_value(text: str, index: int) -> int:
    index = skip_ignored(text, index)
    if index >= len(text):
        fail("settings object is missing a value")
    if text[index] == '"':
        _, return_index = parse_string(text, index)
        return return_index
    if text[index] in "[{":
        opening = text[index]
        closing = "]" if opening == "[" else "}"
        stack = [closing]
        index += 1
        in_string = False
        escaped = False
        while index < len(text):
            character = text[index]
            following = text[index + 1] if index + 1 < len(text) else ""
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
                index += 1
                continue
            if character == '"':
                in_string = True
                index += 1
                continue
            if text.startswith("//", index):
                newline = text.find("\n", index + 2)
                index = len(text) if newline == -1 else newline + 1
                continue
            if text.startswith("/*", index):
                end = text.find("*/", index + 2)
                if end == -1:
                    fail("settings value contains an unterminated comment")
                index = end + 2
                continue
            if character in "[{":
                stack.append("]" if character == "[" else "}")
            elif character in "]}":
                if not stack or character != stack[-1]:
                    fail("settings value has unbalanced delimiters")
                stack.pop()
                if not stack:
                    return index + 1
            index += 1
        fail("settings value is not closed")
    start = index
    while index < len(text) and text[index] not in ",}]":
        if text.startswith("//", index) or text.startswith("/*", index):
            break
        index += 1
    if start == index:
        fail("settings object contains an empty value")
    return index


def top_level_boolean_edit(text: str) -> str:
    try:
        parsed = loads(text)
    except JsoncError as error:
        fail(f"settings file is not valid JSONC: {error}")
    if not isinstance(parsed, dict):
        fail("settings file must contain a JSON object")

    index = skip_ignored(text, 0)
    if index >= len(text) or text[index] != "{":
        fail("settings file must contain a JSON object")
    index += 1
    target_span: tuple[int, int] | None = None
    property_count = 0
    property_seen = 0
    last_value_end = 0
    last_value_had_comma = False
    closing_index: int | None = None
    while True:
        index = skip_ignored(text, index)
        if index >= len(text):
            fail("settings object is not closed")
        if text[index] == "}":
            closing_index = index
            break
        key, index = parse_string(text, index)
        index = skip_ignored(text, index)
        if index >= len(text) or text[index] != ":":
            fail("settings object key is missing a colon")
        index = skip_ignored(text, index + 1)
        property_seen += 1
        value_start = index
        value_end = skip_value(text, index)
        last_value_end = value_end
        if key == KEY:
            property_count += 1
            if property_count != 1:
                fail(f"settings file contains duplicate {KEY} keys")
            token = text[value_start:value_end].strip()
            if token not in {"true", "false"}:
                fail(f"{KEY} must be a boolean")
            leading = len(text[value_start:value_end]) - len(
                text[value_start:value_end].lstrip()
            )
            target_span = (value_start + leading, value_start + leading + len(token))
        index = skip_ignored(text, value_end)
        if index < len(text) and text[index] == ",":
            last_value_had_comma = True
            index += 1
            continue
        if index < len(text) and text[index] == "}":
            last_value_had_comma = False
            closing_index = index
            break
        fail("settings object property is missing a comma")

    assert closing_index is not None
    if target_span is not None:
        start, end = target_span
        return text[:start] + "false" + text[end:]

    line_break = "\r\n" if "\r\n" in text else "\n"
    property_text = f'  "{KEY}": false{line_break}'
    prefix = text[:closing_index]
    if property_seen == 0 or last_value_had_comma:
        leading = "" if prefix.endswith(("\n", "\r")) else line_break
        return prefix + leading + property_text + text[closing_index:]

    trailing = text[last_value_end:closing_index]
    leading = "" if "\n" in trailing or "\r" in trailing else line_break
    return (
        text[:last_value_end]
        + ","
        + trailing
        + leading
        + property_text
        + text[closing_index:]
    )


def settings_path() -> Path:
    value = os.environ.get("COPILOT_SETTINGS")
    if not value:
        fail("COPILOT_SETTINGS is required")
    path = Path(value)
    if not path.is_absolute():
        fail(f"COPILOT_SETTINGS must be absolute: {value}")
    return path


def read_current(path: Path) -> tuple[bytes, int]:
    if not os.path.lexists(path):
        return b"{\n}\n", 0o600
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode):
        fail(f"settings path is not a regular file: {path}")
    try:
        content = path.read_bytes()
    except OSError as error:
        fail(f"could not read settings file: {error}")
    return content, stat.S_IMODE(metadata.st_mode)


def write_atomic(path: Path, content: bytes, mode: int) -> None:
    parent = path.parent
    if os.path.lexists(parent) and not os.path.isdir(parent):
        fail(f"settings parent is not a directory: {parent}")
    parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        fail(f"refusing to replace symlinked settings file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".hard-eng-copilot-settings.", dir=str(parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"install", "check"}:
        fail("usage: copilot-settings.py install|check")
    path = settings_path()
    current, mode = read_current(path)
    try:
        decoded = current.decode("utf-8")
    except UnicodeDecodeError as error:
        fail(f"settings file is not valid UTF-8: {error}")
    desired = top_level_boolean_edit(decoded)
    desired_bytes = desired.encode("utf-8")
    if desired_bytes == current:
        return 0
    if sys.argv[1] == "check":
        return DRIFT
    write_atomic(path, desired_bytes, mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
