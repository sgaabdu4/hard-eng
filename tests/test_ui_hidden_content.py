"""Content the browser hides, or that sits behind an open modal, is not part of the measured screen."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_ui_variants import META, limit_page
from ui_capture import WIDTHS, capture

LONG_BUTTON = (
    "<button style='width:40px;font-size:16px'>Archive this conversation</button>"
)
SHORT_BUTTON = (
    "<button style='height:30px;min-width:120px;font-size:16px'>Close</button>"
)
HIDDEN = {
    "closed-details": f"<details style='width:60px'><summary>More actions</summary>{LONG_BUTTON}</details>",
    "hidden-until-found": f"<div hidden=until-found>{LONG_BUTTON}</div>",
    "ancestor-content-visibility": f"<div style='content-visibility:hidden'><div>{LONG_BUTTON}</div></div>",
    "closed-dialog": f"<dialog>{LONG_BUTTON}</dialog>",
    "inert": f"<div inert>{LONG_BUTTON}</div>",
}
BEHIND = (
    "<main><section><h2>Card</h2>"
    f"<p style='{META}'>Posted yesterday</p><p style='{META}'>Ends in three days</p>"
    "</section></main>"
)
SHEET = (
    "<div role=dialog aria-modal=true style='position:fixed;bottom:0;left:0;right:0;background:#fff;padding:8px'>"
    f"{SHORT_BUTTON}</div>"
)
MODAL = f"<dialog id=d>{SHORT_BUTTON}</dialog><script>document.getElementById('d').showModal()</script>"
PLAIN_DIALOG = f"<dialog open>{SHORT_BUTTON}</dialog>"


@pytest.mark.parametrize("body", HIDDEN.values(), ids=HIDDEN)
def test_a_control_the_browser_hides_is_not_measured(
    tmp_path: Path, site: str, browser: ModuleType, body: str
) -> None:
    limit_page(tmp_path, body)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_the_same_control_in_an_open_details_is_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    limit_page(
        tmp_path,
        f"<details open style='width:60px'><summary>More actions</summary>{LONG_BUTTON}</details>",
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width]["wrapped-label"] == 1, (width, found[width])
        assert found[width]["tap-size"] == 1, (width, found[width])


@pytest.mark.parametrize(
    "modal", [MODAL, SHEET], ids=["dialog-show-modal", "aria-modal"]
)
def test_only_the_open_modal_is_measured(
    tmp_path: Path, site: str, browser: ModuleType, modal: str
) -> None:
    limit_page(tmp_path, BEHIND + modal)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({"tap-size": 1}), (width, found[width])


def test_the_page_behind_a_dialog_that_is_not_modal_is_still_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    limit_page(tmp_path, BEHIND + PLAIN_DIALOG)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width]["extra-text"] == 1, (width, found[width])
        assert found[width]["tap-size"] == 1, (width, found[width])


def test_a_page_with_no_modal_is_measured_as_before(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    limit_page(tmp_path, BEHIND + SHORT_BUTTON)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({"extra-text": 1, "tap-size": 1}), (
            width,
            found[width],
        )


GOOD_BUTTON = (
    "<button style='height:44px;min-width:120px;font-size:16px'>Close</button>"
)
SHEET_STYLE = "position:fixed;bottom:0;left:0;right:0;background:#fff;padding:8px"


def test_with_two_modals_only_the_last_one_in_the_page_is_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    first = (
        f"<div role=dialog aria-modal=true style='{SHEET_STYLE}'>{SHORT_BUTTON}</div>"
    )
    last = f"<div role=dialog aria-modal=true style='{SHEET_STYLE}'>{GOOD_BUTTON}</div>"
    limit_page(tmp_path, BEHIND + first + last)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_a_hidden_element_marked_modal_does_not_blank_the_page(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    hidden = f"<div aria-modal=true style='display:none'>{GOOD_BUTTON}</div>"
    limit_page(tmp_path, BEHIND + hidden + SHORT_BUTTON)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({"extra-text": 1, "tap-size": 1}), (
            width,
            found[width],
        )


def test_a_low_contrast_line_behind_a_modal_gives_no_finding(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    faint = "<p style='color:#ccc;font-size:16px'>Faint line behind the sheet</p>"
    limit_page(
        tmp_path,
        f"<main><h1>Page</h1>{faint}</main>"
        f"<div role=dialog aria-modal=true style='{SHEET_STYLE}'>{GOOD_BUTTON}</div>",
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_an_unlabelled_field_behind_a_modal_gives_no_finding(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    field = "<input style='height:44px;width:200px;font-size:16px'>"
    limit_page(
        tmp_path,
        f"<main><h1>Page</h1>{field}</main>"
        f"<div role=dialog aria-modal=true style='{SHEET_STYLE}'>{GOOD_BUTTON}</div>",
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_a_modal_wrapper_with_no_box_of_its_own_still_covers_the_page(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    wrapper = (
        "<div role=dialog aria-modal=true style='position:relative'>"
        f"<div style='{SHEET_STYLE}'>{SHORT_BUTTON}</div></div>"
    )
    limit_page(tmp_path, BEHIND + wrapper)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({"tap-size": 1}), (width, found[width])


def test_an_unlabelled_field_that_only_screen_readers_reach_is_still_reported(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    field = "<input type=checkbox style='position:absolute;width:1px;height:1px;clip:rect(0,0,0,0)'>"
    limit_page(tmp_path, f"<main><h1>Page</h1>{field}</main>")
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width]["label"] == 1, (width, found[width])


CLOSED_MODALS = {
    "collapsed": "<div role=dialog aria-modal=true style='max-height:0;overflow:hidden'>{inner}</div>",
    "clipped": "<div role=dialog aria-modal=true style='clip-path:inset(100%)'>{inner}</div>",
    "faded-wrapper": "<div style='position:fixed;inset:0;opacity:0;pointer-events:none'><div role=dialog aria-modal=true style='background:#fff'>{inner}</div></div>",
}


@pytest.mark.parametrize("closed", CLOSED_MODALS.values(), ids=CLOSED_MODALS)
def test_a_closed_modal_that_is_collapsed_or_faded_does_not_blank_the_page(
    tmp_path: Path, site: str, browser: ModuleType, closed: str
) -> None:
    limit_page(tmp_path, BEHIND + closed.format(inner=GOOD_BUTTON) + SHORT_BUTTON)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width]["extra-text"] == 1, (width, found[width])
        assert found[width]["tap-size"] == 1, (width, found[width])
