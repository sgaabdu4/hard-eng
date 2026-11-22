"""Runtime browser audit guards: competing same-colour CTAs, duplicates, hierarchy, clipping, waterfalls, and CLS."""

from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_ui_quality import pair
from ui_capture import WIDTHS, capture

AUDIT_FAULTS = {
    "competing-same-colour": (
        f"<div>{pair('#00b', '#00b')}</div>",
        "competing-buttons",
        1,
    ),
    "duplicate-buttons": (
        (
            "<div><div>"
            "<button style='min-height:44px;min-width:44px;font-size:16px;background:transparent;border:1px solid #333;color:#111'>Mark paid</button>"
            "<button style='min-height:44px;min-width:44px;font-size:16px;background:transparent;border:1px solid #333;color:#111'>Mark paid</button>"
            "</div></div>"
        ),
        "duplicate-buttons",
        1,
    ),
    "heading-hierarchy": (
        (
            "<main><h1 style='font-size:20px;font-weight:400'>Rentals</h1>"
            "<p style='font-size:16px;font-weight:600'>Unit 4B</p></main>"
        ),
        "heading-hierarchy",
        1,
    ),
    "clipped-select": (
        (
            "<label>Status <select aria-label='Status' style='width:52px;height:44px;font-size:16px'>"
            "<option selected>Awaiting Landlord Signature</option></select></label>"
        ),
        "clipped-control",
        1,
    ),
    "clipped-button": (
        "<button style='width:60px;height:44px;font-size:16px;overflow:hidden;white-space:nowrap'>Save Landlord Record</button>",
        "clipped-control",
        1,
    ),
    "clipped-chrome": (
        (
            "<aside style='position:fixed;top:0;left:0;width:200px;height:960px;overflow:visible'>"
            "<div style='height:880px'>Nav</div>"
            "<button style='min-height:44px;min-width:120px;font-size:16px'>Sign out</button></aside>"
        ),
        "clipped-chrome",
        1,
    ),
}


@pytest.mark.parametrize(
    ("body", "rule", "count"), AUDIT_FAULTS.values(), ids=AUDIT_FAULTS
)
def test_each_runtime_audit_guard_finds_one_fault(
    tmp_path: Path, site: str, browser: ModuleType, body: str, rule: str, count: int
) -> None:
    (tmp_path / "pages/audit.html").write_text(
        "<!doctype html><html lang=en><title>Audit</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )
    found = capture(browser, tmp_path, site, "audit")
    for width in WIDTHS:
        assert found[width] == Counter({rule: count}), (width, found[width])


def test_sequential_fetch_waterfall_and_layout_shift_are_measured(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/step.json").write_text('{"ok":true}')
    (tmp_path / "pages/waterfall.html").write_text(
        "<!doctype html><html lang=en><title>Waterfall</title>"
        "<style>body{margin:0;font:16px sans-serif}</style>"
        "<body><main><h1 style='font-size:24px;font-weight:700'>Board</h1><p id='out'>Loading</p></main>"
        "<script>(async () => {"
        "for (let i = 0; i < 4; i++) {"
        "await fetch('/step.json?w=' + i);"
        "await new Promise((r) => setTimeout(r, 25));"
        "}"
        "document.getElementById('out').textContent = 'Ready';"
        "})();</script></body>"
    )
    found_wf = capture(browser, tmp_path, site, "waterfall")
    for width in WIDTHS:
        assert found_wf[width] == Counter({"fetch-waterfall": 1}), (
            width,
            found_wf[width],
        )

    (tmp_path / "pages/cls.html").write_text(
        "<!doctype html><html lang=en><title>Shift</title>"
        "<style>body{margin:0;font:16px sans-serif}</style>"
        "<body><div id='slot'></div>"
        "<main id='content' style='height:500px;background:#fff'>"
        "<h1 style='font-size:24px;font-weight:700;margin:0'>Summary</h1>"
        "<p style='margin:0'>Main body text that shifts downward.</p></main>"
        "<script>setTimeout(() => {"
        "const b = document.createElement('div');"
        "b.style.height = '320px'; b.textContent = 'Late banner';"
        "document.getElementById('slot').appendChild(b);"
        "}, 120);</script></body>"
    )
    found_cls = capture(browser, tmp_path, site, "cls")
    for width in WIDTHS:
        assert found_cls[width] == Counter({"layout-shift": 1}), (
            width,
            found_cls[width],
        )
