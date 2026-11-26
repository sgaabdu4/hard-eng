"""The measure records every corner of a control or a chip, also at 0, and code decides a square claim from the corners of that element only."""

import json
from pathlib import Path
from types import ModuleType

from look_facts import SQUARE_LAST, radius_facts, tokens_from_text, verdict
from test_browser import plain_step, session
from test_ui_audit_guards import measured, open_board

DESIGN = "---\nrounded:\n  sm: 6px\n  md: 8px\n---\n# Design\n"
CHIP = "display:inline-block;padding:2px 10px;background:#dde;font-size:14px;"


def chip(name: str, radius: str) -> str:
    return f"<span style='{CHIP}border-radius:{radius}'>{name}</span>"


def test_square_chips_are_recorded_and_decided_from_their_own_corners(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/corners.html").write_text(
        "<!doctype html><html lang=en><title>Corners</title>"
        "<style>body{margin:0;font:16px sans-serif}</style><body><main>"
        "<h1 style='font-size:24px;margin:0 0 14px'>Corners</h1>"
        f"<p style='margin:14px 0'>{chip('Square one', '0')}{chip('Square two', '0')}</p>"
        f"<p style='margin:14px 0'>{chip('Round one', '6px')}{chip('Round end', '6px 0 0 6px')}</p>"
        "<button style='min-height:44px;min-width:120px;font-size:16px;border-radius:0'>Go</button>"
        "<p style='margin:14px 0'><a href='#' style='display:inline-block;min-height:44px;min-width:44px;border-radius:0'>Plain link</a></p>"
        "<input style='width:120px;height:44px;border-radius:0'>"
        "<table><tr><td style='background:#eef;padding:4px;border-radius:0'>Cell</td></tr></table>"
        "<div style='height:30px;background:#eee;border-radius:0'></div>"
        "</main></body>"
    )
    name = session()
    open_board(tmp_path, site, name, "corners")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    values = record["measured"]
    rows = {item["at"]: item for item in values["radii"]}
    for square in ("Square one", "Square two", "Go"):
        assert rows[square]["corners"] == [0, 0, 0, 0], square
        assert rows[square]["px"] == 0, square
    assert rows["Round one"]["corners"] == [6, 6, 6, 6]
    assert rows["Round end"]["corners"] == [6, 0, 0, 6]
    assert rows["Round end"]["px"] == 6
    assert len(values["radii"]) == len(rows)
    assert all(item["at"] for item in values["radii"])
    assert rows["Plain link"]["corners"] == [0, 0, 0, 0]
    assert rows["Cell"]["corners"] == [0, 0, 0, 0]
    tokens = tokens_from_text(DESIGN)
    squares = [
        fact for fact in radius_facts(values, tokens) if fact.margin == SQUARE_LAST
    ]
    assert {fact.key for fact in squares} == {
        "Square one",
        "Square two",
        "Go",
        "Plain link",
        "Cell",
    }
    assert all(fact.ok is True for fact in squares)
    failing = verdict("radius", "Square one", values, tokens, "square")
    assert failing is not None
    assert failing[0] is False
    assert "0 is in no rounded token" in failing[1]
    for passing in ("Round one", "Round end"):
        found = verdict("radius", passing, values, tokens, "square")
        assert found is not None
        assert found[0] is True
        assert "not square" in found[1]
