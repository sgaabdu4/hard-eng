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
GREY_BODY = "color:#6b6b6b;margin:0"
STEPS = "".join(f"<li>Step {n} of the list</li>" for n in range(5))
SMALL = "font-size:9px;color:#55565c;margin:0"
MID = "font-size:12px;color:#55565c;margin:0"
LONG_LINE = " ".join(["word"] * 21)
MOCK_LINES = "".join(
    f"<div style='{META}'>line {'abcdefghij'[n]}</div>" for n in range(10)
)
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
    "label-toggle": (
        f"<div style='display:flex;gap:8px'><input type=password aria-label=Password style='{INPUT}'><input type=checkbox id=c hidden><label for=c style='padding:12px'>Show</label></div>",
        "field-control",
    ),
    "attr-heading": (
        f"<style>.t::before{{content:attr(data-t)}}</style><section><h2 class=t data-t='Offer 7'></h2><p style='{META}'>Posted yesterday</p><p style='{META}'>Ends in three days</p></section>",
        "extra-text",
    ),
    "search-placeholder": (
        f"<form><div style='display:flex;gap:8px'><input type=text placeholder=Search aria-label=Search style='{INPUT}'><button type=submit style='{PLAIN_BUTTON}'>Go</button></div></form>",
        "field-control",
    ),
    "nine-secondary-lines": (
        f"<section><h2>Hero</h2><div>{MOCK_LINES}</div></section>",
        "extra-text",
    ),
    "twenty-one-words": (
        f"<section><h2>Feature</h2><p style='{META}'>{LONG_LINE}</p></section>",
        "extra-text",
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
    "stat-labels": f"<section><h2>Numbers</h2><div style='display:flex;gap:24px'><div><strong style='font-size:24px'>500+</strong><div style='{META}'>Patients served</div></div><div><strong style='font-size:24px'>3,000+</strong><div style='{META}'>Visits a year</div></div></div></section>",
    "footer-copyright": f"<footer><h2>Contact</h2><p>Write to us any time.</p><p style='{META}'>Copyright 2026 Example</p></footer>",
    "icon-list": "<section><h2>Why us</h2><ul style='list-style:none;margin:0;padding:0'><li><svg aria-hidden=true width=16 height=16><circle cx=8 cy=8 r=6 /></svg> <span>Plain words</span></li><li><svg aria-hidden=true width=16 height=16><circle cx=8 cy=8 r=6 /></svg> <span>Fast answers</span></li><li><svg aria-hidden=true width=16 height=16><circle cx=8 cy=8 r=6 /></svg> <span>Fair prices</span></li></ul></section>",
    "diagram-nodes": f"<section><h2>Flow</h2><div style='display:flex;gap:8px;flex-wrap:wrap'>{NODES}</div></section>",
    "grey-body-list": f"<section><h2>Delete</h2><p style='{GREY_BODY}'>Follow these steps.</p><ol style='{GREY_BODY}'>{STEPS}</ol></section>",
    "list-items-in-a-card": f"<section><h2>Open</h2><ul style='{META};padding:0;list-style:none'>{STEPS}</ul></section>",
    "footer-lines": f"<footer><h2>Contact</h2><p style='{META}'>Copyright Example Limited</p><p style='{META}'>All rights reserved</p></footer>",
    "separator-dot": f"<section><h2>Open source</h2><p style='{META}'>A short description</p><span style='{META}'>&middot;</span></section>",
    "pill-toggle": f"<div style='padding:16px'><p style='margin:0'>Show</p><div style='display:inline-flex;padding:6px;background:#eee;border-radius:30px'><button style='{PLAIN_BUTTON}'>Day</button><button style='{PLAIN_BUTTON}'>Week</button></div></div>",
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


def test_a_mock_up_with_text_below_the_floor_reports_only_the_text_size(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    lines = "".join(f"<div style='{SMALL}'>Patient {'abc'[n]}</div>" for n in range(3))
    lines += "".join(f"<div style='{MID}'>Visit {'ab'[n]}</div>" for n in range(2))
    limit_page(tmp_path, f"<section><h2>Dashboard</h2>{lines}</section>")
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert set(found[width]) == {"text-size"}, (width, found[width])


DECOR = (
    "<div {mark} style='{frame}'><h3>Today</h3>"
    f"<p style='{SMALL}'>Patient one</p><p style='{SMALL}'>Patient two</p>"
    "<p style='font-size:14px;color:#cccccc;margin:0'>Faint line</p>"
    "<span style='background:#d33;color:#fff;font-size:14px'>Red</span>"
    "<span style='background:#3a3;color:#fff;font-size:14px'>Green</span>"
    "<span style='background:#33d;color:#fff;font-size:14px'>Blue</span>"
    "</div>"
)
FRAMES = {
    "background": "background:#f2f4f8;padding:12px",
    "shadow": "box-shadow:0 2px 8px rgba(0,0,0,.3);padding:12px",
    "border": "border:1px solid #888;padding:12px",
    "lab": "background:lab(90 0 0);padding:12px",
}
SUB = f"<p style='{META}'>Posted yesterday</p><p style='{META}'>Ends in three days</p>"
HIDDEN = "aria-hidden='true'"
LAYER = "position:absolute;inset:0;background:#f2f4f8"
FAINT = "position:relative;background:#f2f4f9;padding:12px"
LAYERED = (
    f"<div style='position:relative'><div style='{LAYER}'></div>"
    f"<div {HIDDEN} style='{FAINT}'>{SUB}</div></div>"
)
SUB_HIDDEN = SUB.replace("<p ", f"<p {HIDDEN} ")
DODGES = {
    "hidden-div": (f"<h2>Offer</h2><div {HIDDEN}>{SUB}</div>", "extra-text"),
    "hidden-each-p": (f"<h2>Offer</h2>{SUB_HIDDEN}", "extra-text"),
    "hidden-section": (f"<div {HIDDEN}><h2>Offer</h2>{SUB}</div>", "extra-text"),
    "img-div": (f"<h2>Offer</h2><div role=img>{SUB}</div>", "extra-text"),
    "presentation-div": (
        f"<h2>Offer</h2><div role=presentation>{SUB}</div>",
        "extra-text",
    ),
    "faint-frame": (
        f"<h2>Offer</h2><div {HIDDEN} style='background:#fefefe'>{SUB}</div>",
        "extra-text",
    ),
    "faint-lab-frame": (
        f"<h2>Offer</h2><div {HIDDEN} style='background:lab(99.5 0 0)'>{SUB}</div>",
        "extra-text",
    ),
    "faint-over-layer": (f"<h2>Offer</h2>{LAYERED}", "extra-text"),
    "presentation-main": (
        f"<main role=presentation><p style='{SMALL}'>Tiny line</p></main>",
        "text-size",
    ),
}


@pytest.mark.parametrize("frame", FRAMES.values(), ids=FRAMES)
@pytest.mark.parametrize("mark", [HIDDEN, "role=img aria-label='App preview'"])
def test_a_framed_decorative_mock_up_is_not_page_text(
    tmp_path: Path, site: str, browser: ModuleType, mark: str, frame: str
) -> None:
    body = DECOR.format(mark=mark, frame=frame)
    limit_page(tmp_path, f"<section><h2>Preview</h2>{body}</section>")
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


@pytest.mark.parametrize(("body", "rule"), DODGES.values(), ids=DODGES)
def test_a_mark_on_text_with_no_frame_does_not_hide_a_finding(
    tmp_path: Path, site: str, browser: ModuleType, body: str, rule: str
) -> None:
    limit_page(tmp_path, body)
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert rule in found[width], (width, found[width])


def test_the_same_mock_up_without_a_mark_is_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    body = DECOR.format(mark="", frame=FRAMES["background"])
    limit_page(tmp_path, f"<section><h2>Preview</h2>{body}</section>")
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert {"text-size", "contrast"} <= set(found[width]), (width, found[width])


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
