#!/usr/bin/env python3
"""Fail-closed secret scanning for Hard Eng audit evidence."""

from __future__ import annotations

import re
from pathlib import Path


SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b((?:[a-z0-9]+[_-])*api[_-]?key|access[_-]?token|oauth[_-]?token|refresh[_-]?token|"
    r"client[_-]?secret|password|passwd|database[_-]?url|sentry[_-]?auth[_-]?token|"
    r"aws[_-]?secret[_-]?access[_-]?key)\b\s*[:=]\s*[\"']?([A-Za-z0-9_./+=:@-]{16,})"
)
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
SECRET_PREFIX = re.compile(
    r"(?:sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,})"
)
GENERIC_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:[a-z0-9]+[_-])*(?:token|secret|credential)\b\s*[:=]\s*[\"']?"
    r"((?=[A-Za-z0-9_./+=:@-]{24,})(?=[A-Za-z0-9_./+=:@-]*[A-Za-z])"
    r"(?=[A-Za-z0-9_./+=:@-]*[0-9])[A-Za-z0-9_./+=:@-]{24,})"
)
QUOTED_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?<![a-z0-9_-])([\"']?)(?:[a-z0-9]+[_-])*(?:api[_-]?key|access[_-]?token|oauth[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|password|passwd|database[_-]?url|"
    r"sentry[_-]?auth[_-]?token|aws[_-]?secret[_-]?access[_-]?key|secret|credential)\b"
    r"\1\s*[:=]\s*([\"'`])((?:\\.|(?!\2).)*)\2([^\r\n]*)"
)
ENV_ACCESSOR = re.compile(
    r"""(?x)
    (?:
        (?:process\.env|import\.meta\.env)(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\])
      | Platform\.environment\[\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\]
      | os\.environ(?:\[\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\]|\.get\(\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\))
      | (?:os\.(?:getenv|Getenv)|System\.(?:getenv|get_env)|Deno\.env\.get|Environment\.GetEnvironmentVariable|std::getenv|(?:std::)?env::var|getenv)\(\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\)
      | ProcessInfo\.processInfo\.environment\[\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\]
      | String\.fromEnvironment\(\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\)
      | ENV\[\s*["'][A-Za-z_][A-Za-z0-9_]*["']\s*\]
    )
    """
)
TYPE_SUFFIX = re.compile(r"^as\s+[A-Za-z_][A-Za-z0-9_?<>., ]*")
EXPRESSION_REFERENCE = re.compile(
    r"^[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*"
    r"(?:\([^\"'`\r\n()]*\))?"
)
EXPRESSION_WORD = re.compile(
    r"(?i)(?:auth|config|credential|env|generate|key|password|secret|temporary|token|value|vault)"
)
PLACEHOLDER_VALUES = {
    "", "example", "dummy", "fixture", "placeholder", "changeme", "redacted", "test",
    "replace_me", "your_api_key_here",
}
TEST_PATH_PARTS = {"test", "tests", "__tests__", "fixture", "fixtures", "mock", "mocks"}
SYNTHETIC_TEST_VALUE = re.compile(
    r"(?i)^(?:key|(?:new|owner|admin|user|test|fake|fixture|dummy)[/_-]"
    r"(?:pass|password|key|token|secret)(?:[/_-][0-9]{1,6})?)$"
)
ENCODED_BOMS = (
    (b"\xff\xfe\x00\x00", "utf-32"), (b"\x00\x00\xfe\xff", "utf-32"),
    (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16"), (b"\xef\xbb\xbf", "utf-8-sig"),
)


class EncodedTextError(ValueError):
    pass


def readable_ratio(text: str) -> float:
    return sum(character.isprintable() or character in "\r\n\t" for character in text) / max(1, len(text))


def nul_encoding(data: bytes) -> str | None:
    ratios = tuple(
        sum(byte == 0 for byte in data[offset::4]) / max(1, len(data[offset::4]))
        for offset in range(4)
    )
    if len(data) >= 8 and ratios[0] < 0.25 and min(ratios[1:]) > 0.6:
        return "utf-32-le"
    if len(data) >= 8 and ratios[3] < 0.25 and min(ratios[:3]) > 0.6:
        return "utf-32-be"
    even = sum(byte == 0 for byte in data[0::2]) / max(1, len(data[0::2]))
    odd = sum(byte == 0 for byte in data[1::2]) / max(1, len(data[1::2]))
    if odd > 0.6 and even < 0.25:
        return "utf-16-le"
    if even > 0.6 and odd < 0.25:
        return "utf-16-be"
    return None


def decode_text_bytes(data: bytes) -> str | None:
    encoding = next((encoding for marker, encoding in ENCODED_BOMS if data.startswith(marker)), None)
    if encoding is None and b"\0" in data:
        encoding = nul_encoding(data)
        if encoding is None:
            return None
    if encoding is not None:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError as exc:
            raise EncodedTextError("malformed encoded text") from exc
        return text if readable_ratio(text) >= 0.85 else None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
        return text if readable_ratio(text) >= 0.85 else None


def sensitive_path(relative: str) -> bool:
    path = Path(relative)
    name = path.name.lower()
    safe_env = {".env.example", ".env.sample", ".env.template"}
    parts = {part.lower() for part in path.parts}
    return (
        name == ".env"
        or (name.startswith(".env.") and name not in safe_env)
        or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
        or name in {
            ".netrc", ".npmrc", ".pypirc", ".sentryclirc", "auth.json", "credentials.json",
            "oauth.json", "secrets.json", "secrets.yaml", "secrets.yml", "service-account.json",
            "application_default_credentials.json", "id_rsa", "id_ed25519",
        }
        or (".aws" in parts and name == "credentials")
        or (".docker" in parts and name == "config.json")
        or ("gh" in parts and name in {"hosts.yml", "hosts.yaml"})
    )


def safe_fallback(suffix: str) -> str | None:
    operator = re.match(r"^(?:\?\?|\|\|)\s*", suffix)
    if operator is None:
        return suffix
    remainder = suffix[operator.end():]
    keyword = re.match(r"^(?:null|undefined)\b", remainder)
    if keyword:
        return remainder[keyword.end():]
    quoted = re.match(r"^([\"'])([^\"']*)\1", remainder)
    if quoted and quoted.group(2).casefold() in PLACEHOLDER_VALUES:
        return remainder[quoted.end():]
    return None


def environment_reference(text: str, match: re.Match[str], group: int) -> bool:
    line_end = text.find("\n", match.start(group))
    rhs = text[match.start(group):line_end if line_end >= 0 else len(text)].strip()
    accessor = ENV_ACCESSOR.match(rhs)
    if accessor is None:
        return False
    suffix = rhs[accessor.end():].lstrip()
    if suffix.startswith("!"):
        suffix = suffix[1:].lstrip()
    if typed := TYPE_SUFFIX.match(suffix):
        suffix = suffix[typed.end():].lstrip()
    suffix = safe_fallback(suffix)
    if suffix is None:
        return False
    suffix = suffix.lstrip()
    return not suffix or suffix[0] in ",;})]"


def credential_expression_reference(text: str, match: re.Match[str], group: int) -> bool:
    line_end = text.find("\n", match.start(group))
    rhs = text[match.start(group):line_end if line_end >= 0 else len(text)].strip()
    reference = EXPRESSION_REFERENCE.match(rhs)
    if reference is None:
        return False
    value = reference.group()
    structured = (
        any(marker in value for marker in (".", "(", "_", "$"))
        or re.search(r"[a-z][A-Z]", value) is not None
    )
    if not structured or not EXPRESSION_WORD.search(value):
        return False
    suffix = rhs[reference.end():].lstrip()
    if suffix.startswith("!"):
        suffix = suffix[1:].lstrip()
    if typed := TYPE_SUFFIX.match(suffix):
        suffix = suffix[typed.end():].lstrip()
    suffix = safe_fallback(suffix)
    if suffix is None:
        return False
    suffix = suffix.lstrip()
    return not suffix or suffix[0] in ",;})]"


def inside_quoted_literal(text: str, position: int) -> bool:
    start = text.rfind("\n", 0, position) + 1
    quote = None
    escaped = False
    for character in text[start:position]:
        if escaped:
            escaped = False
        elif character == "\\":
            escaped = True
        elif quote == character:
            quote = None
        elif quote is None and character in "\"'`":
            quote = character
    return quote is not None


def synthetic_test_placeholder(value: str, relative: str | None) -> bool:
    if not relative:
        return False
    path = Path(relative)
    lowered = {part.lower() for part in path.parts}
    test_path = bool(lowered & TEST_PATH_PARTS) or bool(
        re.search(r"(?:^|[._-])test(?:[._-]|$)", path.name, re.IGNORECASE)
    )
    return test_path and SYNTHETIC_TEST_VALUE.fullmatch(value) is not None


def secret_marker(text: str, relative: str | None = None) -> str | None:
    if PRIVATE_KEY.search(text):
        return "private-key"
    if SECRET_PREFIX.search(text):
        return "credential-prefix"
    for match in QUOTED_SECRET_ASSIGNMENT.finditer(text):
        if inside_quoted_literal(text, match.start()):
            continue
        value = match.group(3)
        suffix = match.group(4).lstrip()
        terminal = not suffix or suffix[0] in ",;})]" or suffix.startswith(("#", "//"))
        placeholder = value.casefold() in PLACEHOLDER_VALUES or synthetic_test_placeholder(
            value, relative
        )
        if not placeholder or not terminal:
            return "credential-assignment"
    for match in SECRET_ASSIGNMENT.finditer(text):
        raw_value = match.group(2)
        if environment_reference(text, match, 2) or credential_expression_reference(
            text, match, 2
        ):
            continue
        if raw_value.lower() not in PLACEHOLDER_VALUES:
            return "credential-assignment"
    for match in GENERIC_SECRET_ASSIGNMENT.finditer(text):
        raw_value = match.group(1)
        if environment_reference(text, match, 1) or credential_expression_reference(
            text, match, 1
        ):
            continue
        if raw_value.lower() not in PLACEHOLDER_VALUES:
            return "generic-credential-assignment"
    return None
