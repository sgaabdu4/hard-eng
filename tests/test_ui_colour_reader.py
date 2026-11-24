"""The page script reads a colour as the one-pixel canvas reader did before the string reader."""

import json
from pathlib import Path
from types import ModuleType

import ui_measure
from test_browser import page, session

OLD_READER = (
    "const old = (() => { const cv = Object.assign(document.createElement('canvas'), { width: 1, height: 1 }).getContext('2d', { willReadFrequently: true }); "
    "return (c) => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = 'rgba(0, 0, 0, 0)'; cv.fillStyle = c; cv.fillRect(0, 0, 1, 1); const d = cv.getImageData(0, 0, 1, 1).data; return [d[0], d[1], d[2], d[3] / 255]; }; })(); "
)
ALPHAS = (0.05, 0.09, 0.1, 0.11, 0.5, 0.7, 0.99)
OPAQUE = (
    "tomato",
    "#a03b26",
    "rgb(160, 59, 38)",
    "color(srgb 0.627451 0.231373 0.14902)",
    "color(srgb 1.2 -0.1 0.5)",
    "oklab(0.5 0.1 0.05)",
    "oklch(0.5 0.15 30)",
    "hsl(10 62% 40%)",
    "color(display-p3 0.6 0.2 0.1)",
    "color-mix(in srgb, rgb(160, 59, 38) 50%, white)",
)
SEE_THROUGH = (
    "rgba(160, 59, 38, {a})",
    "rgb(160 59 38 / {a})",
    "color(srgb 0.627451 0.231373 0.14902 / {a})",
    "color(srgb 1.2 -0.1 0.5 / {a})",
    "oklab(0.5 0.1 0.05 / {a})",
    "oklch(0.5 0.15 30 / {a})",
    "hsl(10 62% 40% / {a})",
    "color(display-p3 0.6 0.2 0.1 / {a})",
    "color-mix(in srgb, rgb(160, 59, 38) {pct}%, transparent)",
)
HEX_BYTES = ("0d", "17", "1a", "1c", "80", "b3", "fc")
READ = (
    "(() => { "
    + OLD_READER
    + ui_measure.COLOUR_JS.replace("const rgb = ", "const now = ", 1)
    + "const computed = (c) => { document.body.style.color = ''; document.body.style.color = c; return getComputedStyle(document.body).color; }; "
    "return JSON.stringify(COLOURS_JSON.map(([c, twin, alpha]) => { const s = computed(c); "
    "return { c, s, alpha, old: old(s), now: now(s), twin: twin ? old(computed(twin)) : null }; })); })()"
)


def colours() -> list[list[str | float | None]]:
    rows: list[list[str | float | None]] = [[c, None, 1.0] for c in OPAQUE]
    for hex_byte in HEX_BYTES:
        rows.append([f"#a03b26{hex_byte}", "#a03b26", int(hex_byte, 16) / 255])
    for form in SEE_THROUGH:
        for alpha in ALPHAS:
            shown = form.format(a=alpha, pct=round(alpha * 100))
            rows.append([shown, form.format(a=1, pct=100), alpha])
    return rows


def readings(tmp_path: Path, site: str, browser: ModuleType) -> list[dict[str, object]]:
    page(tmp_path, "colours.html", "<p>colours</p>")
    tool, name = browser.ensure_tool(), session()
    script = READ.replace("COLOURS_JSON", json.dumps(colours()))
    try:
        browser.require(
            browser.run_tool(tool, tmp_path, name, "open", f"{site}/colours.html")
        )
        reply = browser.require(
            browser.run_tool(tool, tmp_path, name, "eval", "--stdin", text=script)
        )
    finally:
        browser.run_tool(tool, tmp_path, name, "close")
    return json.loads(json.loads(reply))


def byte(alpha: float) -> int:
    return int(alpha * 255 + 0.5)


def test_every_colour_reads_as_the_canvas_reader_read_it_before_the_string_reader(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    problems: dict[str, list[str]] = {"channels": [], "alpha": [], "threshold": []}
    for row in readings(tmp_path, site, browser):
        old, now, twin, alpha = row["old"], row["now"], row["twin"], row["alpha"]
        assert isinstance(old, list) and isinstance(now, list)
        assert isinstance(alpha, int | float)
        shown = f"{row['c']} -> {row['s']}: old {old}, now {now}, twin {twin}"
        if byte(now[3]) != byte(alpha) or abs(byte(old[3]) - byte(alpha)) > 1:
            problems["alpha"].append(shown)
        if (now[3] > 0.1) != (old[3] > 0.1):
            problems["threshold"].append(shown)
        own = twin if twin is not None else old
        assert isinstance(own, list)
        if now[:3] != own[:3]:
            problems["channels"].append(shown)
    assert problems == {"channels": [], "alpha": [], "threshold": []}
