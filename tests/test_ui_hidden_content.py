"""Content the browser hides, or that sits behind an open modal, is not part of the measured screen."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_ui_variants import LONG_BUTTON, META, limit_page
from ui_capture import WIDTHS, capture

SHORT_BUTTON = (
    "<button style='height:30px;min-width:120px;font-size:16px'>Close</button>"
)
GOOD_BUTTON = (
    "<button style='height:44px;min-width:120px;font-size:16px'>Close</button>"
)
SHEET_STYLE = "position:fixed;bottom:0;left:0;right:0;background:#fff;padding:8px"
BEHIND = (
    "<main><section><h2>Card</h2>"
    f"<p style='{META}'>Posted yesterday</p><p style='{META}'>Ends in three days</p>"
    "</section></main>"
)
SHEET = f"<div role=dialog aria-modal=true style='{SHEET_STYLE}'>{{inner}}</div>"
MODAL = "<dialog id=d>{inner}</dialog><script>document.getElementById('d').showModal()</script>"
BOXLESS = (
    "<div role=dialog aria-modal=true style='position:relative'>"
    f"<div style='{SHEET_STYLE}'>{{inner}}</div></div>"
)
SCREEN_READER_FIELD = "<input type=checkbox style='position:absolute;width:1px;height:1px;clip:rect(0,0,0,0)'>"
NOT_OPEN = [
    "<dialog open>{inner}</dialog>",
    "<div aria-modal=true style='display:none'>{inner}</div>",
    "<div role=dialog aria-modal=true style='max-height:0;overflow:hidden'>{inner}</div>",
    "<div role=dialog aria-modal=true style='clip-path:inset(100%)'>{inner}</div>",
    "<div role=dialog aria-modal=true style='position:relative'><div style='position:fixed;inset:0;opacity:0'><div style='background:#fff'>{inner}</div></div></div>",
    "<div style='position:fixed;inset:0;opacity:0;pointer-events:none'><div role=dialog aria-modal=true style='background:#fff'>{inner}</div></div>",
]


def test_an_open_details_and_a_control_only_screen_readers_reach_are_still_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    limit_page(
        tmp_path,
        f"<details open style='width:60px'><summary>More actions</summary>{LONG_BUTTON}</details>{SCREEN_READER_FIELD}",
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width]["wrapped-label"] == 1, (width, found[width])
        assert found[width]["tap-size"] >= 1, (width, found[width])
        assert found[width]["label"] == 1, (width, found[width])


@pytest.mark.parametrize(
    "modal", [MODAL, SHEET, BOXLESS], ids=["dialog-show-modal", "aria-modal", "boxless"]
)
def test_only_the_open_modal_is_measured(
    tmp_path: Path, site: str, browser: ModuleType, modal: str
) -> None:
    limit_page(tmp_path, BEHIND + modal.format(inner=SHORT_BUTTON))
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({"tap-size": 1}), (width, found[width])


def test_with_two_modals_only_the_last_one_in_the_page_is_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    limit_page(
        tmp_path,
        BEHIND + SHEET.format(inner=SHORT_BUTTON) + SHEET.format(inner=GOOD_BUTTON),
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_faint_text_and_an_unlabelled_field_behind_a_modal_give_no_finding(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    faint = "<p style='color:#ccc;font-size:16px'>Faint line behind the sheet</p>"
    field = "<input style='height:44px;width:200px;font-size:16px'>"
    limit_page(
        tmp_path,
        f"<main><h1>Page</h1>{faint}{field}</main>" + SHEET.format(inner=GOOD_BUTTON),
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_elements_that_are_not_an_open_modal_leave_the_page_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    closed = "".join(item.format(inner=GOOD_BUTTON) for item in NOT_OPEN)
    limit_page(tmp_path, BEHIND + closed + SHORT_BUTTON)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width]["extra-text"] == 1, (width, found[width])
        assert found[width]["tap-size"] == 1, (width, found[width])
