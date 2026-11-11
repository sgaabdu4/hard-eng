"""The forms that retry a failed test, judged by the kind of file that holds them."""

import re
from pathlib import PurePosixPath

from comments import JAVASCRIPT
from plans import _is_test

NONZERO = r"(?!\s*(?:0|false|null)\b)\s*\S"
COUNT = r"\s*[1-9]\d*\s*(?:[,})]|$)"
JS_TEST = re.compile(
    r"(jest\.retryTimes\()|\bconfigure\(\s*\{[^}\n]*?(retries:)"
    + COUNT
    + r"|\b(?:test|it|describe|bench|suite)\b[^\n]*\{\s*(retry:)"
    + COUNT
    + r"|[})]\s*,\s*\{\s*(retry:)"
    + COUNT
    + r"|^\s*\{\s*(retry:)"
    + COUNT
)
JS_CONFIG = re.compile(r"(jest\.retryTimes\()|\b(retry:|retries:)" + NONZERO)
PYTHON = re.compile(r"\b(mark\.flaky)\b|(@flaky)\b")
DART_TEST = re.compile(r"(@Retry\()|\b(retry:)" + COUNT)
PYTEST_SETTINGS = re.compile(
    r"(--force-reruns|--reruns)(?![ =]+0\b)|^\s*(reruns)\s*="
    + NONZERO
    + r"|addopts[^\n]*(--retries)\b"
)
KEYS = re.compile(r"^\s*(retry)\s*[=:]" + NONZERO)
COMMANDS = re.compile(
    r'"(--retry|--retries|--reruns)"|(-retry-tests-on-failure)'
    r"|\b(?:vitest|playwright|jest|bun test|pytest)\b[^\n]*?(--retry|--retries|--reruns)\b(?![ =]+0\b)"
    r"|(?i:(retryonfailure))"
)
BY_NAME = {
    "hard-eng.gates.json": COMMANDS,
    "package.json": COMMANDS,
    "bunfig.toml": KEYS,
    "dart_test.yaml": KEYS,
    **dict.fromkeys(
        ("pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg"), PYTEST_SETTINGS
    ),
}
BY_SUFFIX = {".xctestplan": COMMANDS, ".xcscheme": COMMANDS}
IN_TESTS = {".py": PYTHON, ".dart": DART_TEST, **dict.fromkeys(JAVASCRIPT, JS_TEST)}
CONFIG_PREFIXES = (
    "playwright.config.",
    "playwright-ct.config.",
    "vitest.config.",
    "vitest.workspace.",
    "vite.config.",
    "jest.config.",
    "jest.setup.",
)


def retry_pattern(name: str) -> re.Pattern[str] | None:
    path = PurePosixPath(name)
    if pattern := BY_NAME.get(path.name) or BY_SUFFIX.get(path.suffix):
        return pattern
    if path.suffix in JAVASCRIPT and path.name.startswith(CONFIG_PREFIXES):
        return JS_CONFIG
    if path.name == "conftest.py" or _is_test(path):
        return IN_TESTS.get(path.suffix)
    return None


def retry_form(name: str, text: str) -> str | None:
    """The retry form that an added line turns on in this file, or None."""
    pattern = retry_pattern(name)
    hit = pattern.search(text) if pattern else None
    return hit[hit.lastindex or 0] if hit else None
