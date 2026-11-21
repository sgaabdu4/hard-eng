"""Every setting a tool prints has a class in a table, so a new setting is refused until someone classes it."""

import json
import re
import subprocess
from pathlib import Path

import pytest
from fallow_table import FALLOW_KEYS, FALLOW_PREFIXES, flatten, judge
from ruff_table import RUFF_KEYS, RUFF_PREFIXES, classify, parse, ruff_hits
from test_fallow_resolved import need_fallow

CLASSES = {
    "free",
    "equal",
    "limit",
    "limits",
    "rules",
    "named",
    "patterns",
    "version",
    "proved",
    "holds",
    "used",
}


def test_every_class_in_the_tables_is_known() -> None:
    for table in (RUFF_KEYS, RUFF_PREFIXES, FALLOW_KEYS, FALLOW_PREFIXES):
        assert set(table.values()) <= CLASSES


def test_every_setting_that_ruff_prints_has_a_class(tmp_path: Path) -> None:
    """The newest Ruff: Hard Eng's own check fails when it prints a key that no table has, so the class is added before a project meets it."""
    (tmp_path / "a.py").write_text("x = 1\n")
    done = subprocess.run(
        ["uvx", "ruff@latest", "check", "--isolated", "--show-settings", "."],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    missing = sorted(key for key in parse(done.stdout) if classify(key) is None)
    assert not missing, f"class these settings: {missing}"


def test_every_setting_that_fallow_prints_has_a_class(tmp_path: Path) -> None:
    need_fallow()
    (tmp_path / ".fallowrc.json").write_text(
        json.dumps(
            {
                "rulePacks": [".fallow-policy.json"],
                "ignoreDependencyOverrides": [
                    {"package": "qs", "source": "package.json"}
                ],
            }
        )
    )
    done = subprocess.run(
        ["bunx", "fallow@latest", "config"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    missing = sorted(
        key
        for key in flatten(json.loads(done.stdout))
        if key not in FALLOW_KEYS
        and not any(key.startswith(prefix) for prefix in FALLOW_PREFIXES)
    )
    assert not missing, f"class these settings: {missing}"


@pytest.mark.parametrize(
    ("text", "key"),
    [
        ("linter.line_length = 88\n", "linter.line_length"),
        ("linter.rules.enabled = [\n\tpyflakes (F401),\n]\n", "linter.rules.enabled"),
        ("linter.per_file_ignores = {}\n", "linter.per_file_ignores"),
    ],
)
def test_the_ruff_parser_reads_each_printed_key(text: str, key: str) -> None:
    assert key in parse(text)
    assert re.fullmatch(r"[a-z_.0-9]+", key)


def test_a_nested_block_is_not_read_as_keys() -> None:
    entry = '\tabsolute_matcher = "/x/a.py"\nbasename_matcher = "a.py"\ndata = [\n\tunused-import (F401),\n]\n\n'
    text = f"linter.per_file_ignores = {{\n{entry}{entry}}}\nlinter.line_length = 88\n"
    assert sorted(parse(text)) == ["linter.line_length", "linter.per_file_ignores"]


def test_a_ruff_setting_that_no_table_classes_is_refused() -> None:
    """HE-NO-SWITCH-OFF: a key that the tables do not class fails, so a new tool setting cannot pass unseen."""
    hits = ruff_hits("linter.made_up_key = 1\n", "", "lint")
    assert any("no table classes" in hit for hit in hits)
    assert not any("ruff_table.py" in hit for hit in hits)


def test_a_fallow_setting_that_no_table_classes_is_refused() -> None:
    hits = judge({"madeUpKey": 1}, {}, lambda patterns: [], lambda glob: "")
    assert any("no table classes" in hit for hit in hits)
    assert not any("fallow_table.py" in hit for hit in hits)


def test_a_new_ruff_setting_at_its_default_passes() -> None:
    """A tool release that adds a setting must not turn a project red: an unclassed key at its default changes no result."""
    assert (
        ruff_hits("linter.made_up_key = 1\n", "linter.made_up_key = 1\n", "lint") == []
    )
    hits = ruff_hits("linter.made_up_key = 2\n", "linter.made_up_key = 1\n", "lint")
    assert any("no table classes" in hit for hit in hits)


def test_a_new_fallow_setting_at_its_default_passes() -> None:
    def drop(patterns: list[str]) -> list[str]:
        return []

    def covered(glob: str) -> str:
        return ""

    nothing = (drop, covered)
    assert judge({"madeUpKey": 1}, {"madeUpKey": 1}, *nothing) == []
    hits = judge({"madeUpKey": 2}, {"madeUpKey": 1}, *nothing)
    assert any("no table classes" in hit and "default" in hit for hit in hits)


SIX_KEYS: dict[str, object] = {
    "duplicates": {"ignoreSymlinks": False},
    "health": {
        "changeCoupling": {
            "maxFilesPerCommit": 30,
            "minRevisions": 5,
            "minSharedRevisions": 5,
            "minDegree": 0.3,
        }
    },
    "showCascade": False,
}


def test_the_six_keys_of_fallow_3_43_have_a_class() -> None:
    missing = [
        key
        for key in flatten(SIX_KEYS)
        if key not in FALLOW_KEYS
        and not any(key.startswith(prefix) for prefix in FALLOW_PREFIXES)
    ]
    assert not missing
