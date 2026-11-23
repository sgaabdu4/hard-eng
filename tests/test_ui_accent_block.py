"""The accent colours of a button group: its block, and the page container that does not count as one."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_ui_quality import pair
from ui_capture import WIDTHS, capture


def tab(colour: str, label: str) -> str:
    return (
        "<button style='min-height:44px;min-width:100px;font-size:16px;"
        f"background:transparent;color:{colour};border:1px solid {colour}'>{label}</button>"
    )


def screen(content: str) -> str:
    return (
        "<main style='padding:16px;color:#2b1b17'>"
        f"<h1 style='font-size:24px;font-weight:700;margin:0 0 8px'>Rentals</h1>{content}</main>"
    )


def status_list(*colours: str) -> str:
    items = "".join(
        f"<li style='color:{colour}'>Unit {n} status</li>"
        for n, colour in enumerate(colours, 1)
    )
    return f"<ul>{items}</ul>"


def words(*colours: str) -> str:
    return "".join(
        f"<p style='margin:0;color:{colour}'>Note {n}</p>"
        for n, colour in enumerate(colours, 1)
    )


def page(tmp_path: Path, body: str) -> None:
    (tmp_path / "pages/block.html").write_text(
        "<!doctype html><html lang=en><title>Block</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )


def test_a_tab_bar_in_the_page_container_does_not_count_the_whole_page(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    tabs = f"<div>{tab('#563933', 'Open')}{tab('#2b1b17', 'Closed')}</div>"
    page(tmp_path, screen(tabs + status_list("#a03b26", "#8a5a00")))
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


STILL_COUNTED = {
    "card-pair": screen(
        f"<div><p style='color:#b00'>a</p><p style='color:#060'>b</p>{pair('#00b', 'transparent')}</div>"
    ),
    "tab-bar-own-colours": screen(
        f"<div>{tab('#b00', 'One')}{tab('#060', 'Two')}{tab('#00b', 'Three')}</div>"
    ),
    "wrapper-in-card": screen(
        f"<div><section><div>{words('#b00', '#060', '#00b')}</div></section>"
        f"{pair('#2b1b17', 'transparent')}</div>"
    ),
    "wrapper-in-tab-bar": screen(
        f"<div>{tab('#563933', 'Open')}{tab('#2b1b17', 'Closed')}"
        f"<section>{words('#b00', '#060', '#00b')}</section></div>"
    ),
}


@pytest.mark.parametrize("body", STILL_COUNTED.values(), ids=STILL_COUNTED)
def test_accent_colours_around_a_button_group_still_count(
    tmp_path: Path, site: str, browser: ModuleType, body: str
) -> None:
    page(tmp_path, body)
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter({"accent-colours": 1}), (width, found[width])
