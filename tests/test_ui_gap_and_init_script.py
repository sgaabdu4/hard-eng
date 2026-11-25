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
