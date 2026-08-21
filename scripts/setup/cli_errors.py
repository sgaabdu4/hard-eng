"""Stable setup CLI error boundary."""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable


def _message(error: Exception) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(error)).strip()
    return text[:500] or "operation failed"


def run_cli(owner: str, action: Callable[[], int]) -> int:
    try:
        return action()
    except Exception as error:
        if os.environ.get("HARD_ENG_DEBUG") == "1":
            raise
        print(f"{owner}: FAIL: {type(error).__name__}: {_message(error)}", file=sys.stderr)
        return 1
