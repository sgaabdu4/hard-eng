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
