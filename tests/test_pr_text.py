"""The PR text rules have one owner that `ship` and CI both call."""

from pathlib import Path

import pytest
from pr_text import body_problem
from test_shipping import (
    _DIAGRAM,
    FakeGitHub,
    _check,
    _fixture,
    _pull,
    _ready_outcome,
)

_GOOD = "Undo: revert the commits.\n" + _DIAGRAM * 2


@pytest.mark.parametrize(
    ("line", "passes"),
    [
        (None, False),
        ("Not checked:", False),
        ("Not checked: None", False),
        ("Not checked: nothing.", False),
        ("**Not checked:** the Mac canary", False),
        ("Not checked: the Mac canary", True),
        ("  Not checked: the Mac canary", True),
        ("Not checked: None — docs only, CI ran every check", True),
    ],
)
def test_not_checked_needs_what_was_not_checked_or_a_reason_for_none(
    line: str | None, passes: bool
) -> None:
    body = _GOOD if line is None else f"{_GOOD}{line}\n"
    assert (body_problem(body) is None) is passes
    assert (body_problem(body.replace("\n", "\r\n")) is None) is passes


def test_ready_refuses_a_pr_body_without_a_not_checked_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, body=_GOOD), [_check(fixture.head)])
    _ready_outcome(fixture, fake, monkeypatch, "Not checked")
