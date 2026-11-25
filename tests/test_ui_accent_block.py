"""The accent colours of a button group: its block, and the page container that does not count as one."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_ui_quality import button, pair
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


INK = "rgb(43, 27, 23)"
TILE = "rgb(107, 63, 88)"
BAR = "rgb(86, 57, 51)"


def tile(size: int, fill: str) -> str:
    return f"<span style='display:inline-block;width:{size}px;height:{size}px;background:{fill}'></span>"


def badge(fill: str) -> str:
    return f"<span style='background:{fill};color:#fff;padding:4px'>Late</span>"


def outline(text: str, border: str, label: str) -> str:
    return (
        "<button style='min-height:44px;min-width:100px;font-size:16px;"
        f"background:transparent;color:{text};border:1px solid {border}'>{label}</button>"
    )


PAGE_INK = {
    "list-row": screen(
        "<ul style='margin:0;padding:0;list-style:none'><li>"
        f"<p style='margin:0'>Unit 4 status</p>{tile(22, TILE)}"
        f"<div>{outline(BAR, BAR, 'Edit')}{outline(INK, '#ccc', 'Close')}</div></li></ul>"
    ),
    "panel": screen(
        f"<section><h2 style='margin:0;color:{INK}'>Pick one</h2>{tile(36, 'rgb(134, 101, 28)')}"
        f"<div>{outline(INK, '#ccc', 'Yes')}{outline(INK, '#ccc', 'No')}"
        f"{button(BAR, 'Save')}</div></section>"
    ),
}


def page(tmp_path: Path, body: str) -> None:
    (tmp_path / "pages/block.html").write_text(
        "<!doctype html><html lang=en><title>Block</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )


@pytest.mark.parametrize("body", PAGE_INK.values(), ids=PAGE_INK)
def test_the_page_ink_text_is_not_an_accent(
    tmp_path: Path, site: str, browser: ModuleType, body: str
) -> None:
    page(tmp_path, body)
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


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
    "three-accents-and-ink": screen(
        f"<div><p style='margin:0'>Rent due</p>{badge('#b00')}{tile(22, '#060')}"
        f"{pair('#00b', 'transparent')}</div>"
    ),
    "hued-text-not-the-ink": screen(
        f"<div><p style='margin:0;color:#5a3a10'>Rent due</p>{tile(22, TILE)}"
        f"{pair(BAR, 'transparent')}</div>"
    ),
    "ink-as-a-fill": screen(
        f"<div><p style='margin:0'>Rent due</p>{tile(22, INK)}{tile(22, TILE)}"
        f"{pair(BAR, 'transparent')}</div>"
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


def ink_at_two_strengths(ink: str, faded: str) -> str:
    return screen(
        f"<div><p style='margin:0;color:{ink}'>Rent due</p>"
        f"<p style='margin:0;font:700 24px sans-serif;color:{faded}'>Unit 4 status</p>"
        f"{pair('#00b', 'transparent')}</div>"
    )


def test_one_ink_at_two_strengths_counts_as_one_colour(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(tmp_path, ink_at_two_strengths("rgb(160, 59, 38)", "rgba(160, 59, 38, 0.7)"))
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


SAME_INK = {
    "rgb-and-srgb": (
        "rgb(44, 62, 80)",
        "color(srgb 0.172549 0.243137 0.313726 / 0.75)",
    ),
    "srgb-and-oklab": (
        "color(srgb 0.172549 0.243137 0.313726 / 0.75)",
        "oklab(0.356408 -0.0140117 -0.0364867 / 0.75)",
    ),
    "rgb-and-oklab": (
        "rgb(44, 62, 80)",
        "oklab(0.356408 -0.0140117 -0.0364867 / 0.75)",
    ),
    "oklab-alone": ("oklab(0.5 0.1 0.05)", "oklab(0.5 0.1 0.05 / 0.75)"),
    "oklch-alone": ("oklch(0.5 0.15 30)", "oklch(0.5 0.15 30 / 0.75)"),
}


@pytest.mark.parametrize("inks", SAME_INK.values(), ids=SAME_INK)
def test_one_ink_in_two_colour_forms_counts_as_one_colour(
    tmp_path: Path, site: str, browser: ModuleType, inks: tuple[str, str]
) -> None:
    page(tmp_path, ink_at_two_strengths(*inks))
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_two_different_inks_still_count_as_two_colours(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(tmp_path, ink_at_two_strengths("#2b1b17", "#5a3a10"))
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter({"accent-colours": 1}), (width, found[width])


def test_a_different_ink_in_another_colour_form_still_counts_as_a_colour(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        ink_at_two_strengths(
            "color(srgb 0.172549 0.243137 0.313726 / 0.75)",
            "oklab(0.45 0.08 -0.02 / 0.75)",
        ),
    )
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter({"accent-colours": 1}), (width, found[width])


def with_tint(tint: str) -> str:
    return screen(
        "<div><p style='margin:0;color:rgb(160, 59, 38)'>Rent due</p>"
        f"<p style='margin:0;color:rgb(160, 59, 38);background:{tint}'>Unit 4 status</p>"
        f"{pair('#00b', 'transparent')}</div>"
    )


COUNTED = Counter({"accent-colours": 1})
TINTS = {
    "rgba-ten-percent": ("rgba(0, 130, 60, 0.1)", COUNTED),
    "oklab-ten-percent": ("oklab(0.6 -0.15 0.1 / 0.1)", COUNTED),
    "srgb-ten-percent": ("color(srgb 0 0.5 0.25 / 0.1)", COUNTED),
    "rgba-nine-percent": ("rgba(0, 130, 60, 0.09)", Counter()),
    "oklab-nine-percent": ("oklab(0.6 -0.15 0.1 / 0.09)", Counter()),
}


@pytest.mark.parametrize(("tint", "expected"), TINTS.values(), ids=TINTS)
def test_a_tint_of_a_third_hue_counts_from_ten_percent_up(
    tmp_path: Path, site: str, browser: ModuleType, tint: str, expected: Counter[str]
) -> None:
    page(tmp_path, with_tint(tint))
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == expected, (width, found[width])


def test_a_channel_outside_the_colour_range_reads_as_the_nearest_inside_it(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        ink_at_two_strengths("rgb(128, 0, 51)", "color(srgb 0.501961 -0.1 0.2)"),
    )
    found = capture(browser, tmp_path, site, "block")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])
