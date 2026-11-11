"""CI test shards: the field, the split, the shard run and the report merge."""

from pathlib import Path
from typing import cast

import pytest
from conftest import gate
from gate_config import Group, validate_group


def shard_group(path: str, role: str | None, value: object) -> Group:
    options = {"role": role} if role else {}
    return cast(
        Group,
        {"path": path, "checks": [gate("suite", "pass", shards=value, **options)]},
    )


@pytest.mark.parametrize(
    ("path", "role", "value", "accepted"),
    [
        (".", "tests", 6, True),
        ("api", "tests", 2, True),
        (".", "tests", 16, True),
        (".", "tests", "6", False),
        (".", "tests", 1, False),
        (".", "tests", 17, False),
        (".", "tests", True, False),
        ("api", "tests", 0, False),
        (".", "lint", 6, False),
        (".", None, 6, False),
    ],
)
def test_shards_is_a_whole_number_from_2_to_16_on_a_tests_gate(
    tmp_path: Path, path: str, role: str | None, value: object, accepted: bool
) -> None:
    (tmp_path / "api").mkdir()
    group = shard_group(path, role, value)
    if accepted:
        assert validate_group(tmp_path, group, set()) == 1
        return
    with pytest.raises(ValueError, match="shards must be 2 to 16 on a tests gate"):
        validate_group(tmp_path, group, set())
