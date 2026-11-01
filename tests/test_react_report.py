"""A failing React Doctor scan names the checks it skipped and why."""

import json
from pathlib import Path

import pytest
import reports
from gate_config import JsonObject
from test_reports import REPORTS

OOM = "oxlint ran out of memory in fixed_size.rs"


def written(tmp_path: Path, **changes: object) -> Path:
    report = json.loads(REPORTS["react-doctor"])
    report["projects"][0].update(changes)
    path = tmp_path / "react.json"
    path.write_text(json.dumps(report))
    return path


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {
                "complete": False,
                "skippedChecks": ["lint"],
                "skippedCheckReasons": {"lint": OOM},
            },
            f"incomplete checks or diagnostics: lint skipped: {OOM}",
        ),
        (
            {"skippedCheckReasons": {"lint:partial": "one worker failed"}},
            "lint:partial skipped: one worker failed",
        ),
        ({"skippedChecks": ["lint"]}, "lint skipped: no reason reported"),
        ({"diagnostics": [{}, {}]}, "2 diagnostics"),
        ({"complete": False}, "the project scan did not complete"),
    ],
    ids=["reason", "partial", "no reason", "diagnostics", "incomplete"],
)
def test_incomplete_react_scan_says_why(
    tmp_path: Path, changes: JsonObject, message: str
) -> None:
    with pytest.raises(ValueError) as caught:
        reports.validate_react_doctor(written(tmp_path, **changes))
    assert message in str(caught.value)


def test_long_reason_is_cut(tmp_path: Path) -> None:
    changes = {"skippedChecks": ["lint"], "skippedCheckReasons": {"lint": "x" * 5000}}
    with pytest.raises(ValueError) as caught:
        reports.validate_react_doctor(written(tmp_path, **changes))
    assert "x" * 2000 in str(caught.value) and "x" * 2001 not in str(caught.value)


def test_complete_react_scan_passes(tmp_path: Path) -> None:
    reports.validate_react_doctor(written(tmp_path))


def test_out_of_memory_reason_says_how_to_fix_it(tmp_path: Path) -> None:
    changes = {"skippedChecks": ["lint"], "skippedCheckReasons": {"lint": OOM}}
    with pytest.raises(ValueError) as caught:
        reports.validate_react_doctor(written(tmp_path, **changes))
    assert (
        "Fix: allow memory overcommit on the runner or give the job more memory"
        in str(caught.value)
    )


def test_other_reasons_get_no_memory_hint(tmp_path: Path) -> None:
    changes = {"skippedChecks": ["lint"], "skippedCheckReasons": {"lint": "timed out"}}
    with pytest.raises(ValueError) as caught:
        reports.validate_react_doctor(written(tmp_path, **changes))
    assert "overcommit" not in str(caught.value)
