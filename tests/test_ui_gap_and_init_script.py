"""The measure orders the neighbours of a gap along their line and reads text alignment and weight facts."""

import json
from pathlib import Path
from types import ModuleType

from test_browser import plain_step, session
from test_ui_audit_guards import measured, open_board


def captured(
    tmp_path: Path, site: str, browser: ModuleType, page: str, body: str
) -> dict[str, object]:
    (tmp_path / f"pages/{page}.html").write_text(
        f"<!doctype html><html lang=en><title>{page}</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{body}</body>"
    )
    name = session()
    open_board(tmp_path, site, name, page)
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    return record["measured"]


def rows_of(found: dict[str, object], key: str) -> list[dict[str, str | int | bool]]:
    value = found[key]
    assert isinstance(value, list)
    return value


def assert_no_weight_verdict(
    tmp_path: Path, found: dict[str, object], *keys: str
) -> None:
    import look_facts
    from test_look_facts import tokens_of

    tokens = tokens_of(tmp_path)
    for key in keys:
        assert look_facts.verdict("weight", key, found, tokens) is None
        assert key not in look_facts.item_keys(found, tokens)["weight"]


COUNTER_PAGE = (
    "<main><div style='display:flex;align-items:baseline;gap:6px;font-size:12px'>"
    "<span>Round</span><span style='font-size:13px;font-weight:700'>5</span>"
    "<span>/36</span></div></main>"
)


def test_the_gap_between_inline_neighbours_follows_their_order_on_the_line(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "counter", COUNTER_PAGE)
    pairs = {(gap["at"], gap["to"]): gap["px"] for gap in rows_of(found, "gaps")}
    assert pairs == {("Round", "5"): 6, ("5", "/36"): 6}


WRAPPED_PAGE = (
    "<main><div style='width:302px;margin:0 auto;font:10px monospace'>"
    + "x" * 50
    + " tail</div></main>"
)


def test_wrapped_left_aligned_text_in_a_centred_box_is_not_centred(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "wrapped", WRAPPED_PAGE)
    rows = [
        row for row in rows_of(found, "texts") if str(row["at"]).startswith("xxxxxxxx")
    ]
    assert [(row["align"], row["centred"]) for row in rows] == [("start", False)]


INLINE_PAGE = (
    "<main><p style='margin:0 auto;width:fit-content;font:14px sans-serif'>"
    "Already have an account? <a href='/login'>Sign in</a></p></main>"
)


def test_a_centred_line_with_an_inline_link_is_centred(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "inline", INLINE_PAGE)
    rows = [
        row for row in rows_of(found, "texts") if str(row["at"]).startswith("Already")
    ]
    assert [(row["align"], row["centred"]) for row in rows] == [("start", True)]


REPEAT_PAGE = (
    "<main><div style='display:flex;gap:6px;font-size:12px;font-weight:600'>"
    "<span>Round</span><span>5</span><span>/36</span></div>"
    "<div style='display:flex;gap:6px;font-size:12px'>"
    "<span style='font-weight:600'>5</span>"
    "<span style='font-weight:400'>Overdue</span></div></main>"
)


def test_a_label_repeated_in_two_rows_with_one_style_gets_no_weight_verdict(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "repeat", REPEAT_PAGE)
    assert_no_weight_verdict(tmp_path, found, "5")


LABEL_PAGE = (
    "<main><header style='display:flex;gap:12px;font-size:14px'>"
    "<button aria-label='Settings' style='width:20px;height:20px'></button>"
    "<h1 style='font-size:14px;margin:0;font-weight:700'>Dashboard</h1></header>"
    "<nav style='font-size:14px'><a href='/s' style='font-weight:400'>Settings</a></nav></main>"
)


def test_an_icon_button_named_like_a_link_gives_no_weight_verdict(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "label", LABEL_PAGE)
    assert_no_weight_verdict(tmp_path, found, "Dashboard", "Settings")


WRAPPER_PAGE = (
    "<main><div style='display:flex;gap:12px;font-size:14px'>"
    "<div style='display:flex;gap:4px'><span>Round</span><span>5</span></div>"
    "<span>Active</span></div>"
    "<h2 style='font-size:14px;margin:0;font-weight:700'>Round 5</h2></main>"
)


def test_a_wrapper_named_like_a_heading_gives_no_weight_verdict(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    found = captured(tmp_path, site, browser, "wrapper", WRAPPER_PAGE)
    assert_no_weight_verdict(tmp_path, found, "Active", "Round 5")
