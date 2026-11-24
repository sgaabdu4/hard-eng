"""The tap-size measure sees every control and every standalone link, whatever the reader limits cut."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from ui_capture import WIDTHS, capture


def control(number: int, side: int) -> str:
    return (
        f"<div><button style='width:{side}px;height:{side}px;font-size:16px'>"
        f"{number}</button></div>"
    )


CONTROLS = "".join(control(n, 30 if n == 25 else 44) for n in range(1, 31))
STANDALONE = "<a href='#x' style='font-size:16px'>Sign out</a>"
BIG_LINK = (
    "<a href='#x' style='display:inline-block;min-width:44px;min-height:44px;"
    "font-size:16px;line-height:44px'>Sign out</a>"
)
MID_LINK = (
    "<a href='#x' style='display:inline-block;min-width:60px;min-height:30px;"
    "font-size:16px;line-height:30px'>Sign out</a>"
)
TINY = (
    "<a href='#x' style='display:inline-block;width:10px;height:10px;"
    "font-size:16px;overflow:hidden'>a</a>"
)
CARD = (
    "<div><h3>Plan</h3><p>Two rooms</p>"
    "<a href='#x' style='font-size:16px'>Read more</a></div>"
)
SENTENCE = "<p>Read the <a href='#x'>terms of service</a> before you continue.</p>"
DARK = "".join(
    f"<p style='margin:0;color:#{n:02x}{n:02x}{n:02x}'>Line {n}</p>" for n in range(13)
)
FAINT = "<p style='margin:0;color:#bbb'>Faint line</p>"
CASES: dict[str, tuple[str, dict[int, Counter[str]]]] = {
    "the 25th of 30 controls": (
        CONTROLS,
        {width: Counter({"tap-size": 1}) for width in WIDTHS},
    ),
    "the 14th of 14 text colours": (
        DARK + FAINT,
        {width: Counter({"contrast": 1}) for width in WIDTHS},
    ),
    "a standalone text link": (
        f"<div>{STANDALONE}</div>",
        {width: Counter({"tap-size": 1}) for width in WIDTHS},
    ),
    "two 10 px links with no text around them": (
        "<p style='margin:0'>" + TINY + TINY + "</p>",
        {width: Counter({"link-size": 2, "tap-size": 2}) for width in WIDTHS},
    ),
    "a standalone link under a heading and a paragraph": (
        CARD,
        {width: Counter({"tap-size": 1}) for width in WIDTHS},
    ),
    "a standalone link of 44 px": (f"<div>{BIG_LINK}</div>", {}),
    "a link inside a sentence": (SENTENCE, {}),
    "a link of 30 px, wanted only at 1280 px": (
        f"<div>{MID_LINK}</div>",
        {390: Counter({"tap-size": 1}), 768: Counter({"tap-size": 1})},
    ),
}


@pytest.mark.parametrize(("body", "expected"), CASES.values(), ids=CASES)
def test_the_measure_flags_what_the_limits_and_the_exemption_leave(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    body: str,
    expected: dict[int, Counter[str]],
) -> None:
    (tmp_path / "pages/tap.html").write_text(
        "<!doctype html><html lang=en><title>Tap</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )
    found = capture(browser, tmp_path, site, "tap")
    assert found == {width: expected.get(width, Counter()) for width in WIDTHS}
