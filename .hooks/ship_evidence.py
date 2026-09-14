"""Select PR attachments from declared, inspected visual comparison evidence."""

import fnmatch
import re

_BEFORE = re.compile(
    r"^\s*Before:\s*!\[[^\]\r\n]*\]\((https://github\.com/user-attachments/assets/[^)\s?#]+)\)\s*$",
    re.MULTILINE,
)
_AFTER = re.compile(
    r"^\s*After:\s*!\[[^\]\r\n]*\]\((https://github\.com/user-attachments/assets/[^)\s?#]+)\)\s*$",
    re.MULTILINE,
)


def attachment_urls(body: str, paths: list[str], patterns: list[str]) -> list[str]:
    if not any(
        fnmatch.fnmatchcase(path, pattern) for path in paths for pattern in patterns
    ):
        return []
    unchanged = re.findall(
        r"^UI appearance: unchanged(?:[ \t]*—[ \t]*(.*))?$", body, re.MULTILINE
    )
    if unchanged:
        if (
            len(unchanged) != 1
            or not unchanged[0].strip()
            or re.search(r"(?m)^\s*(?:Before|After):", body)
        ):
            raise ValueError(
                "Unchanged UI requires one comparison note and no Before/After attachments"
            )
        return []
    before = _BEFORE.findall(body)
    after = _AFTER.findall(body)
    if len(before) != 1 or len(after) != 1 or before[0] == after[0]:
        raise ValueError(
            "UI changes require distinct Before and After attachments or an explained unchanged appearance"
        )
    return [before[0], after[0]]
