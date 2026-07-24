#!/usr/bin/env python3
"""Validate exact enum/string width claims in a Hard Eng Technical section."""

from __future__ import annotations

import re

from plan_contract import PlanStateError


SCHEMA_ROW = re.compile(r"^\s*-\s+(schema_[a-z][a-z0-9_]*)\s*=")
STRING_FIELDS = re.compile(r"\bstrings?\s+`([^`]*)`")
FIELD_WIDTH = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\(([1-9][0-9]{0,8})\)\??")
ENUM_VALUES = re.compile(r"\b(states|modes|kinds|phases|lifecycles)\s+`([^`]*)`")
ENUM_VALUE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")


def validate_schema_widths(lines: list[str]) -> None:
    seen: set[tuple[str, str]] = set()
    for line in lines:
        schema_match = SCHEMA_ROW.match(line)
        if not schema_match:
            continue
        schema_id = schema_match.group(1)
        widths: dict[str, int] = {}
        for encoded_fields in STRING_FIELDS.findall(line):
            for field, encoded_width in FIELD_WIDTH.findall(encoded_fields):
                width = int(encoded_width)
                if field in widths and widths[field] != width:
                    raise PlanStateError(f"{schema_id}.{field} declares conflicting widths")
                widths[field] = width
        for plural, encoded_values in ENUM_VALUES.findall(line):
            field = plural[:-1]
            key = (schema_id, field)
            values = encoded_values.split("|")
            if (
                key in seen
                or field not in widths
                or not values
                or len(values) != len(set(values))
                or any(not ENUM_VALUE.fullmatch(value) for value in values)
            ):
                raise PlanStateError(f"{schema_id}.{field} enum declaration is invalid")
            seen.add(key)
            oversized = [value for value in values if len(value) > widths[field]]
            if oversized:
                raise PlanStateError(
                    f"{schema_id}.{field} value exceeds width {widths[field]}: "
                    f"{oversized[0][:80]}"
                )
