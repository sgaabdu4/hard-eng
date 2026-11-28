from pathlib import Path
from types import ModuleType

from test_browser import decode, page, plain_step, session

HOVER_GREEN = (0, 200, 0)


def test_measure_keeps_no_hover_fill_after_a_click(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        "hover.html",
        "<style>body{margin:0}#row{width:200px;height:44px;background:#fff}"
        "#row:hover{background:#00c800}</style><div id=row>Row</div>",
    )
    name = session()
    plain_step(tmp_path, name, "set", "viewport", "768", "900")
    plain_step(tmp_path, name, "open", f"{site}/hover.html")
    plain_step(tmp_path, name, "click", "#row")
    code = browser.browser_command(
        tmp_path, ["measure", "--session", name, "--name", "hover"]
    )
    plain_step(tmp_path, name, "close")
    assert code == 0
    _, _, rows, step = decode(tmp_path / ".hard-eng/browser/hover-768.png")
    assert tuple(rows[30][150 * step : 150 * step + 3]) != HOVER_GREEN
