"""The full-suite gate refuses flags that leave part of the suite out."""

from pathlib import Path
from types import ModuleType

import pytest


@pytest.mark.parametrize(
    ("language", "command"),
    [
        ("python", ["pytest", "--ignore=tests/slow"]),
        ("python", ["pytest", "--ignore-glob", "tests/*_slow.py"]),
        ("javascript", ["vitest", "run", "--shard=1/3"]),
        ("javascript", ["vitest", "run", "--project", "unit"]),
        ("javascript", ["jest", "--selectProjects", "unit"]),
        ("dart", ["flutter", "test", "--total-shards=3", "--shard-index=0"]),
    ],
)
def test_path_and_shard_filters_are_rejected(
    runner: ModuleType, tmp_path: Path, language: str, command: list[str]
) -> None:
    with pytest.raises(ValueError, match="Focused test selection"):
        runner.reject_test_filters(command, tmp_path, language)
