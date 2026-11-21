"""Helpers that capture a served page at each width, for the screen quality tests."""

import json
from collections import Counter
from pathlib import Path
from types import ModuleType

from test_browser import session

WIDTHS = (390, 768, 1280)


def capture(
    browser: ModuleType,
    tmp_path: Path,
    site: str,
    name: str,
    skip: tuple[str, ...] = (),
) -> dict[int, Counter[str]]:
    """Capture one served page at each width; return the finding rules at each width."""
    code = browser.browser_command(
        tmp_path,
        ["capture", f"{site}/{name}.html", "--session", session(), "--name", name],
    )
    assert code == 0
    folder = tmp_path / ".hard-eng/browser"
    return {
        width: Counter(
            finding["rule"]
            for finding in json.loads((folder / f"{name}-{width}.json").read_text())[
                "findings"
            ]
            if finding.get("selector") not in skip
        )
        for width in WIDTHS
    }
