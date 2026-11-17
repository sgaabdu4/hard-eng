"""Measured screen quality: the red and fixed fixtures, each limit, and the ship checks."""

import json
import shutil
from collections import Counter
from collections.abc import Generator
from pathlib import Path
from types import ModuleType

import pytest
import test_browser
from test_browser import session

FIXTURES = Path(__file__).parent / "fixtures/ui_quality"
WIDTHS = (390, 768, 1280)


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    yield from test_browser.serve_pages(tmp_path, monkeypatch)


@pytest.fixture
def browser(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    return test_browser.load_browser(monkeypatch)


def capture(
    browser: ModuleType, tmp_path: Path, site: str, name: str
) -> dict[int, Counter[str]]:
    """Capture one served page at each width; return the finding rules at each width."""
    code = browser.browser_command(
        tmp_path,
        ["capture", f"{site}/{name}.html", "--session", session(), "--name", name],
    )
    assert code == 0
    folder = tmp_path / ".hard-eng/browser"
    return {
        width: Counter(
            finding["rule"]
            for finding in json.loads((folder / f"{name}-{width}.json").read_text())[
                "findings"
            ]
        )
        for width in WIDTHS
    }


def serve_fixture(tmp_path: Path, name: str) -> None:
    shutil.copy(FIXTURES / f"{name}.html", tmp_path / "pages" / f"{name}.html")


def test_red_fixture_fails_measurement_and_ship(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    serve_fixture(tmp_path, "red")
    found = capture(browser, tmp_path, site, "red")
    for width in WIDTHS:
        assert set(found[width]) >= {
            "contrast",
            "label",
            "text-size",
            "tap-size",
            "competing-buttons",
            "shared-edge",
            "accent-colours",
        }, (width, found[width])


def test_fixed_fixture_passes_measurement_and_ship(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    serve_fixture(tmp_path, "fixed")
    assert capture(browser, tmp_path, site, "fixed") == {
        width: Counter() for width in WIDTHS
    }


def pair(first: str, second: str) -> str:
    return f"<div>{button(first)}{button(second)}</div>"


def button(fill: str) -> str:
    return (
        "<button style='min-height:44px;min-width:44px;font-size:16px;"
        f"color:#fff;background:{fill};border:0'>Go</button>"
    )


LINK = (
    "<a href='#x' style='display:inline-block;width:10px;height:10px;"
    "font-size:16px;overflow:hidden'>a</a>"
)
FAULTS = {
    "text": ("<p style='font-size:12px'>Small words</p>", "text-size", 1),
    "tap": (
        "<button style='width:30px;height:30px;font-size:16px'>Go</button>",
        "tap-size",
        1,
    ),
    "link": (f"<p style='margin:0'>{LINK}{LINK}</p>", "link-size", 2),
    "competing": (f"<div>{pair('#b00', '#00b')}</div>", "competing-buttons", 1),
    "accents": (
        f"<div><p style='color:#b00'>a</p><p style='color:#060'>b</p>{pair('#00b', '#00b')}</div>",
        "accent-colours",
        1,
    ),
}


@pytest.mark.parametrize(("body", "rule", "count"), FAULTS.values(), ids=FAULTS)
def test_each_measured_limit_finds_one_fault(
    tmp_path: Path, site: str, browser: ModuleType, body: str, rule: str, count: int
) -> None:
    (tmp_path / "pages/limit.html").write_text(
        "<!doctype html><html lang=en><title>Limit</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )
    found = capture(browser, tmp_path, site, "limit")
    for width in WIDTHS:
        assert found[width] == Counter({rule: count}), (width, found[width])
