"""The measure orders the neighbours of a gap along their line, and a session keeps its route's init script beside the request hold."""

import json
from pathlib import Path
from types import ModuleType

import pytest
from test_browser import plain_step, session
from test_ui_audit_guards import measured, open_board

COUNTER_PAGE = (
    "<main><div style='display:flex;align-items:baseline;gap:6px;font-size:12px'>"
    "<span>Round</span><span style='font-size:13px;font-weight:700'>5</span>"
    "<span>/36</span></div></main>"
)


def test_the_gap_between_inline_neighbours_follows_their_order_on_the_line(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/counter.html").write_text(
        "<!doctype html><html lang=en><title>Counter</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{COUNTER_PAGE}</body>"
    )
    name = session()
    open_board(tmp_path, site, name, "counter")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    pairs = {(gap["at"], gap["to"]): gap["px"] for gap in record["measured"]["gaps"]}
    assert pairs == {("Round", "5"): 6, ("5", "/36"): 6}


def test_a_capture_keeps_the_route_init_script_beside_the_hold_script(
    tmp_path: Path, site: str, browser: ModuleType, capfd: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pages/counter.html").write_text(
        "<!doctype html><html lang=en><title>Counter</title><body>"
        f"{COUNTER_PAGE}</body>"
    )
    route = tmp_path / "route-init.js"
    route.write_text("window.__route = 'route';\n")
    name = session()
    plain_step(tmp_path, name, "set", "viewport", "768", "900")
    try:
        plain_step(
            tmp_path, name, "open", "--init-script", str(route), f"{site}/counter.html"
        )
        plain_step(tmp_path, name, "set", "viewport", "390", "900")
        seen = plain_step(
            tmp_path,
            name,
            "eval",
            "String(window.__route) + '/' + String(Boolean(window.__heHold))",
        ).strip()
        assert seen == '"route/true"'
    finally:
        plain_step(tmp_path, name, "close")
    assert (
        browser.browser_command(
            tmp_path,
            [
                "--session",
                session(),
                "open",
                "--init-script",
                str(tmp_path / "gone.js"),
                site,
            ],
        )
        == 1
    )
    assert "gone.js" in capfd.readouterr().err


WRAPPED_PAGE = (
    "<main><div style='width:302px;margin:0 auto;font:10px monospace'>"
    + "x" * 50
    + " tail</div></main>"
)


def test_wrapped_left_aligned_text_in_a_centred_box_is_not_centred(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/wrapped.html").write_text(
        "<!doctype html><html lang=en><title>Wrapped</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{WRAPPED_PAGE}</body>"
    )
    name = session()
    open_board(tmp_path, site, name, "wrapped")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    rows = [
        row for row in record["measured"]["texts"] if row["at"].startswith("xxxxxxxx")
    ]
    assert [(row["align"], row["centred"]) for row in rows] == [("start", False)]


INLINE_PAGE = (
    "<main><p style='margin:0 auto;width:fit-content;font:14px sans-serif'>"
    "Already have an account? <a href='/login'>Sign in</a></p></main>"
)


def test_a_centred_line_with_an_inline_link_is_centred(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/inline.html").write_text(
        "<!doctype html><html lang=en><title>Inline</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{INLINE_PAGE}</body>"
    )
    name = session()
    open_board(tmp_path, site, name, "inline")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    rows = [
        row for row in record["measured"]["texts"] if row["at"].startswith("Already")
    ]
    assert [(row["align"], row["centred"]) for row in rows] == [("start", True)]


REPEAT_PAGE = (
    "<main><div style='display:flex;gap:6px;font-size:12px;font-weight:600'>"
    "<span>Round</span><span>5</span><span>/36</span></div>"
    "<div style='display:flex;gap:6px;font-size:12px'>"
    "<span style='font-weight:600'>5</span>"
    "<span style='font-weight:400'>Overdue</span></div></main>"
)


def test_a_label_repeated_in_two_rows_with_one_style_gets_no_weight_verdict(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    import look_facts
    from test_look_facts import tokens_of

    (tmp_path / "pages/repeat.html").write_text(
        "<!doctype html><html lang=en><title>Repeat</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{REPEAT_PAGE}</body>"
    )
    name = session()
    open_board(tmp_path, site, name, "repeat")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    tokens = tokens_of(tmp_path)
    assert look_facts.verdict("weight", "5", record["measured"], tokens) is None
    assert "5" not in look_facts.item_keys(record["measured"], tokens)["weight"]


LABEL_PAGE = (
    "<main><header style='display:flex;gap:12px;font-size:14px'>"
    "<button aria-label='Settings' style='width:20px;height:20px'></button>"
    "<h1 style='font-size:14px;margin:0;font-weight:700'>Dashboard</h1></header>"
    "<nav style='font-size:14px'><a href='/s' style='font-weight:400'>Settings</a></nav></main>"
)


def test_an_icon_button_named_like_a_link_gives_no_weight_verdict(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    import look_facts
    from test_look_facts import tokens_of

    (tmp_path / "pages/label.html").write_text(
        "<!doctype html><html lang=en><title>Label</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{LABEL_PAGE}</body>"
    )
    name = session()
    open_board(tmp_path, site, name, "label")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    tokens = tokens_of(tmp_path)
    for key in ("Dashboard", "Settings"):
        assert look_facts.verdict("weight", key, record["measured"], tokens) is None
