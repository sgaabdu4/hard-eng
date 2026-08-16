"""Small JSONC reader shared by Copilot state owners."""

from __future__ import annotations

import json


class JsoncError(ValueError):
    """Raised when a JSONC document cannot be parsed."""


def strip_comments(text: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    line_comment = False
    block_comment = False
    while index < len(text):
        character = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if line_comment:
            if character == "\n":
                line_comment = False
                output.append(character)
            else:
                output.append(" ")
            index += 1
            continue
        if block_comment:
            if character == "*" and following == "/":
                output.extend((" ", " "))
                block_comment = False
                index += 2
            else:
                output.append("\n" if character == "\n" else " ")
                index += 1
            continue
        if in_string:
            output.append(character)
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
            output.append(character)
            index += 1
        elif character == "/" and following == "/":
            output.extend((" ", " "))
            line_comment = True
            index += 2
        elif character == "/" and following == "*":
            output.extend((" ", " "))
            block_comment = True
            index += 2
        else:
            output.append(character)
            index += 1
    if block_comment or in_string:
        raise JsoncError("unterminated JSONC comment or string")
    return "".join(output)


def strip_trailing_commas(text: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        character = text[index]
        if in_string:
            output.append(character)
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
            output.append(character)
            index += 1
            continue
        if character == ",":
            lookahead = index + 1
            while lookahead < len(text) and text[lookahead].isspace():
                lookahead += 1
            if lookahead < len(text) and text[lookahead] in "]}":
                index += 1
                continue
        output.append(character)
        index += 1
    return "".join(output)


def loads(text: str) -> object:
    try:
        return json.loads(strip_trailing_commas(strip_comments(text)))
    except (JsoncError, json.JSONDecodeError) as error:
        raise JsoncError(str(error)) from error
