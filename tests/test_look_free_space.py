"""A gap fact is recorded only between neighbours that nothing separates but the spacing of their own line or stack; free space is no spacing value."""

from pathlib import Path
from types import ModuleType

from test_ui_gap_and_init_script import captured, rows_of

SPACED = (
    "<main style='width:500px'>"
    "<div style='display:flex;gap:12px;font-size:14px'><span>Left one</span><span>Right one</span></div>"
    "<p style='margin:0 0 14px;font-size:14px'>Upper line</p>"
    "<p style='margin:0;font-size:14px'>Lower line</p>"
    "<div style='display:flex;font-size:14px'>"
    "<span style='display:inline-block;background:#ddd'>Chip one</span>"
    "<span style='display:inline-block;background:#ccc'>Chip two</span></div></main>"
)
FREE = (
    "<main style='width:500px'>"
    "<div style='display:flex;justify-content:space-between;font-size:14px'>"
    "<span>Take leave</span><button style='width:44px;height:44px'>X</button></div>"
    "<div style='display:flex;font-size:14px'>"
    "<span>Earned leave</span><button style='margin-left:auto;height:44px'>Remove</button></div>"
    "<div style='display:flex;font-size:14px'>"
    "<span style='flex:1'>Grown label</span><span>Fixed end</span></div></main>"
)


def pairs_of(found: dict[str, object]) -> dict[tuple[object, object], object]:
    return {(gap["at"], gap["to"]): gap["px"] for gap in rows_of(found, "gaps")}


def test_a_gap_is_recorded_where_the_line_or_stack_spacing_makes_it(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "spaced", SPACED)
    pairs = pairs_of(found)
    assert pairs[("Left one", "Right one")] == 12
    assert pairs[("Upper line", "Lower line")] == 14
    assert pairs[("Chip one", "Chip two")] == 0


def test_free_space_between_neighbours_is_no_gap_fact(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "free", FREE)
    pairs = pairs_of(found)
    assert not [pair for pair in pairs if pair[0] == "Take leave"]
    assert not [pair for pair in pairs if pair[0] == "Earned leave"]
    assert not [pair for pair in pairs if pair[0] == "Grown label"]
