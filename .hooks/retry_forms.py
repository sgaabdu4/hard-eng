"""The forms that retry a failed test, judged by the kind of file that holds them."""

import re
from pathlib import PurePosixPath

from comments import JAVASCRIPT
from plans import _is_test

NONZERO = r"(?!\s*(?:0|false|null)\b)\s*\S"
COUNT = r"\s*[1-9]\d*\s*(?:[,})]|$)"
NAME = r"(?<![\w.$])(?!(?:%s)\b)[\w$]+(?:\.[\w$]+)*"
CLOSED = r"\([^()]*\)"
for _depth in range(3):
    CLOSED = r"\((?:[^()]|" + CLOSED + r")*\)"


def outside_calls(runners: str) -> str:
    """Text where every call of a non-runner name is closed before the end of the text."""
    name = NAME % runners
    return r"(?:" + name + CLOSED + r"|(?!" + name + r"\().)*"


JS_PLAIN = outside_calls("test|it|describe|bench|suite")
JS_LEAD = "^" + JS_PLAIN
DART_LEAD = "^" + outside_calls("test|testWidgets|group")
JS_KEY = r"(retry:|retries:)"
JS_TEST = re.compile(
    r"(jest\.retryTimes\()|\bconfigure\(\s*\{[^}\n]*?(retries:)"
    + NONZERO
    + "|"
    + JS_LEAD
    + r"\b(?:test|it|describe|bench|suite)\b"
    + JS_PLAIN
    + r"\{\s*"
    + JS_KEY
    + COUNT
    + "|"
    + JS_LEAD
    + r"[})]\s*,\s*\{\s*"
    + JS_KEY
    + COUNT
    + r"|^\s*\{\s*"
    + JS_KEY
    + COUNT
)
JS_CONFIG = re.compile(r"(jest\.retryTimes\()|\b(retry:|retries:)" + NONZERO)
PYTHON = re.compile(r"\b(mark\.flaky)\b|(@flaky)\b")
DART_TEST = re.compile(r"(@Retry\()|" + DART_LEAD + r"\b(retry:)" + COUNT)
PYTEST_SETTINGS = re.compile(
    r"(--force-reruns|--reruns)(?![ =]+0\b)|^\s*(reruns)\s*="
    + NONZERO
    + r"|addopts[^\n]*(--retries)\b"
)
KEYS = re.compile(r"^\s*(retry)\s*[=:]" + NONZERO)
COMMANDS = re.compile(
    r'"(--retry|--retries|--reruns)(?:"|=(?!0")[^"]*")|(-retry-tests-on-failure)'
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
CONFIG_STARTS = ("playwright", "vitest", "vite", "jest")
CONFIG_PREFIXES = ("vitest.workspace.", "jest.setup.")


def is_config(name: str) -> bool:
    return name.startswith(CONFIG_PREFIXES) or (
        name.startswith(CONFIG_STARTS) and ".config." in name
    )


def retry_pattern(name: str) -> re.Pattern[str] | None:
    path = PurePosixPath(name)
    if pattern := BY_NAME.get(path.name) or BY_SUFFIX.get(path.suffix):
        return pattern
    if path.suffix in JAVASCRIPT and is_config(path.name):
        return JS_CONFIG
    if path.name == "conftest.py" or _is_test(path):
        return IN_TESTS.get(path.suffix)
    return None


def retry_form(name: str, text: str) -> str | None:
    """The retry form that an added line turns on in this file, or None."""
    pattern = retry_pattern(name)
    hit = pattern.search(text) if pattern else None
    return hit[hit.lastindex or 0] if hit else None
