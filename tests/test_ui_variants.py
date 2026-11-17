"""The field, extra-text, accent and alignment measures on the variants real pages use."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from ui_capture import WIDTHS, capture

INPUT = "height:44px;font-size:16px;box-sizing:border-box;width:100%"
META = "color:#55565c;font-size:14px;margin:0"
WRAP = "position:relative;width:320px"
OVERLAY = "position:absolute;right:0;top:0;min-width:44px;height:44px;border:0;background:none"
PLAIN_BUTTON = "min-width:44px;min-height:44px;font-size:16px"
BADGE = (
    "display:inline-block;background:#e6f4ea;color:#0b5d1e;border-radius:12px;"
    "padding:2px 10px;font-size:14px"
)
NODE = (
    "border:1px solid #767676;border-radius:8px;padding:4px 8px;font-size:14px;"
    "color:#55565c"
)
SWATCHES = "".join(
    f"<div style='height:8px;background:{c}'></div>"
    for c in ("#b00", "#060", "#00b", "#b60")
)
LONG_LINE = " ".join(["word"] * 21)
MOCK_LINES = "".join(f"<div style='{META}'>line {n}</div>" for n in range(10))
NODES = "".join(f"<span style='{NODE}'>Step {n}</span>" for n in range(9))
REAL_FAULTS = {
    "div-reveal": (
        f"<form><label for=p>Password</label><div style='display:flex;gap:8px'><input id=p type=password style='{INPUT}'><div style='padding:12px'>Show</div></div></form>",
        "field-control",
    ),
    "css-text-reveal": (
        f"<style>.eye::after{{content:'Show'}}</style><div style='{WRAP}'><input type=password aria-label=Password style='{INPUT}'><button type=button class=eye aria-label='Show password' style='{OVERLAY}'></button></div>",
        "field-control",
    ),
    "clip-path-reveal": (
        f"<div style='display:flex;gap:8px'><input type=password aria-label=Password style='{INPUT}'><button type=button style='clip-path:inset(0);{PLAIN_BUTTON}'>Show</button></div>",
        "field-control",
    ),
    "clip-path-search": (
        f"<input type=search aria-label=Find style='clip-path:inset(0);{INPUT}'>",
        "field-control",
    ),
    "search-placeholder": (
        f"<form><div style='display:flex;gap:8px'><input type=text placeholder=Search aria-label=Search style='{INPUT}'><button type=submit style='{PLAIN_BUTTON}'>Go</button></div></form>",
        "field-control",
    ),
    "bold-div-title": (
        f"<div><div style='font-weight:700'>Offer 7</div><p style='{META}'>Posted yesterday</p><p style='{META}'>Ends in three days</p></div>",
        "extra-text",
    ),
    "twenty-one-words": (
        f"<section><h2>Feature</h2><p style='{META}'>{LONG_LINE}</p></section>",
        "extra-text",
    ),
    "four-accents-one-button": (
        f"<section><h2>Card</h2>{SWATCHES}<button style='{PLAIN_BUTTON}'>Go</button></section>",
        "accent-colours",
    ),
    "centred-line-pushed-button": (
        f"<div style='padding:16px'><p style='text-align:center'>Centred line</p><div style='display:flex;justify-content:flex-end'><button style='{PLAIN_BUTTON}'>Go</button></div></div>",
        "shared-edge",
    ),
}
REAL_PATTERNS = {
    "off-screen-reveal-label": f"<div style='{WRAP}'><input type=password aria-label=Password style='{INPUT}'><button type=button style='{OVERLAY}'><svg aria-hidden=true width=20 height=20><circle cx=10 cy=10 r=5 /></svg><span style='position:absolute;left:-9999px'>Show password</span></button></div>",
    "sr-only-reveal-label": f"<div style='{WRAP}'><input type=password aria-label=Password style='{INPUT}'><button type=button style='{OVERLAY}'><svg aria-hidden=true width=20 height=20><circle cx=10 cy=10 r=5 /></svg><span style='position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)'>Show password</span></button></div>",
    "badge-after-heading": f"<section><h2>Feature</h2><span style='{BADGE}'>New</span><p style='{META}'>One short secondary line</p></section>",
    "value-card": f"<section><h2>Vitals</h2><div style='display:flex;gap:16px'><div><span style='{META}'>Heart rate</span> <strong style='font-size:24px'>72 bpm</strong></div><div><span style='{META}'>Sleep</span> <strong style='font-size:24px'>7 h</strong></div></div></section>",
    "hero-mock-up": f"<section><h1>Hero</h1><p>Lead line.</p><div>{MOCK_LINES}</div></section>",
    "diagram-nodes": f"<section><h2>Flow</h2><div style='display:flex;gap:8px;flex-wrap:wrap'>{NODES}</div></section>",
}


def limit_page(tmp_path: Path, body: str) -> None:
    (tmp_path / "pages/limit.html").write_text(
        "<!doctype html><html lang=en><title>Limit</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )


@pytest.mark.parametrize(("body", "rule"), REAL_FAULTS.values(), ids=REAL_FAULTS)
def test_real_variants_of_each_field_and_text_fault_are_found(
    tmp_path: Path, site: str, browser: ModuleType, body: str, rule: str
) -> None:
    limit_page(tmp_path, body)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({rule: 1}), (width, found[width])


@pytest.mark.parametrize("body", REAL_PATTERNS.values(), ids=REAL_PATTERNS)
def test_real_patterns_that_look_like_faults_are_not_findings(
    tmp_path: Path, site: str, browser: ModuleType, body: str
) -> None:
    limit_page(tmp_path, body)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_a_search_icon_drawn_by_the_wrapper_counts_as_inside_the_field(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    body = (
        "<style>.w{position:relative;width:320px}.w::before{content:'\\\\1F50D';"
        "position:absolute;left:12px;top:10px}</style>"
        f"<div class=w><input type=search aria-label=Find style='{INPUT};padding-left:40px'></div>"
    )
    limit_page(tmp_path, body)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])
