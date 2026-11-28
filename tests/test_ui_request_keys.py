"""A repeat of an earlier finished request adds no fetch wave; any other request chain still counts."""

import json
from pathlib import Path
from types import ModuleType

import pytest
from test_browser import plain_step, session
from test_ui_audit_guards import (
    LOAD_WAVE,
    board,
    finished,
    measured,
    open_board,
    press_button,
    press_clicks,
)
from ui_measure import LIMITS

POLLING = (
    "(async () => { const go = () => Promise.all([CALLS]); "
    "const polls = [0, 1, 2, 3, 4].map((i) => new Promise((r) => setTimeout(r, i * 300)).then(go)); "
    "for (const w of 'abc') await fetch('/step.json?' + w).then((r) => r.text()); "
    "await Promise.all(polls); window.done = true; })();"
)
CHAIN = (
    "(async () => { for (const call of [CALLS]) await call(); window.done = true; })();"
)
POST = "() => fetch('/session', { method: 'POST', body: BODY }).then((r) => r.text())"
XHR = (
    "() => new Promise((done) => { const q = new XMLHttpRequest(); q.open('POST', '/session'); "
    "q.onload = () => done(q.responseText); q.send(BODY); })"
)
FORM = "(() => { const f = new FormData(); f.append('a', '1'); return f; })()"
POLLS = [
    "() => fetch('/step.json?poll').then((r) => r.text())",
    POST.replace("BODY", "'poll=1'"),
    POST.replace("BODY", "new URLSearchParams({ q: 2 })"),
    XHR.replace("BODY", "'poll=3'"),
    XHR.replace("BODY", ""),
]
FETCH_CHAIN = [
    POST.replace("BODY", "'step=a'"),
    POST.replace("BODY", "'step=b'"),
    *[POST.replace("BODY", FORM)] * 2,
    *[POST.replace("BODY", "new Blob(['same'])")] * 2,
    *[
        "() => fetch(new Request('/session', { method: 'POST', body: 'same' })).then((r) => r.text())"
    ]
    * 2,
]
XHR_CHAIN_CALLS = [
    XHR.replace("BODY", "'step=a'"),
    XHR.replace("BODY", "'step=b'"),
    *[XHR.replace("BODY", FORM)] * 2,
]


def run(
    tmp_path: Path, site: str, browser: ModuleType, script: str
) -> list[tuple[object, object]]:
    board(tmp_path, "keys", script)
    name = session()
    open_board(tmp_path, site, name, "keys")
    try:
        finished(tmp_path, name)
        return measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")


def waves(tmp_path: Path) -> object:
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    return next(
        item["waves"]
        for item in record["findings"]
        if item["rule"] == "fetch-waterfall"
    )


def test_polls_that_repeat_after_the_load_add_no_wave(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    script = POLLING.replace("CALLS", ", ".join(f"({call})()" for call in POLLS))
    assert run(tmp_path, site, browser, script) == []


@pytest.mark.parametrize(
    ("calls", "count"), [(FETCH_CHAIN, 8), (XHR_CHAIN_CALLS, 4)], ids=["fetch", "xhr"]
)
def test_a_chain_to_one_address_with_a_new_body_each_time_still_counts_every_wave(
    tmp_path: Path, site: str, browser: ModuleType, calls: list[str], count: int
) -> None:
    script = CHAIN.replace("CALLS", ", ".join(calls))
    assert run(tmp_path, site, browser, script) == [("fetch-waterfall", "load")]
    assert waves(tmp_path) == count


BACKGROUND_POLL = (
    "window.polls = new Set(); window.tickStart = 0; window.tickDone = 0; "
    "setInterval(() => { window.tickStart += 1; window.polls.add(window.__heRequests.length); "
    "fetch('/step.json?poll').then((r) => r.text()).then(() => { window.tickDone += 1; }); }, 300);"
)


def until(tmp_path: Path, name: str, condition: str) -> None:
    """Wait on the page itself until `condition` holds, so the order of page events decides, not the clock; a polling page is never quiet, so the fetch log cannot settle."""
    script = (
        "(async () => { while (!(CONDITION)) "
        "await new Promise((go) => setTimeout(go, 25)); return true; })()"
    ).replace("CONDITION", condition)
    plain_step(tmp_path, name, "eval", script)


def pressed(tmp_path: Path, name: str, count: int) -> None:
    until(tmp_path, name, f"(window.pressed || 0) >= {count}")


def quiet_apart_from_the_poll(tmp_path: Path, name: str) -> None:
    quiet = LIMITS["action_quiet_ms"] + 100
    until(
        tmp_path,
        name,
        "(() => { const log = window.__heRequests.filter((e, i) => !window.polls.has(i)); "
        f"return log.length > 0 && log.every((e) => e.end > 0 && performance.now() - e.end >= {quiet}); }})()",
    )


def test_a_polling_page_still_measures_each_press_apart_from_the_load(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    buttons = "".join(press_button(name) for name in "abc")
    board(tmp_path, "background", LOAD_WAVE + BACKGROUND_POLL, buttons)
    name = session()
    open_board(tmp_path, site, name, "background")
    try:
        for count, button in enumerate("abc", 1):
            quiet_apart_from_the_poll(tmp_path, name)
            plain_step(tmp_path, name, "click", f"#{button}")
            pressed(tmp_path, name, count)
        assert measured(tmp_path, browser, name) == []
    finally:
        plain_step(tmp_path, name, "close")


TAB_LOAD = (
    "(async () => { for (const u of ['t1a', 't1b']) "
    "await fetch('/step.json?' + u).then((r) => r.text()); })();"
)


def tab_button(name: str, tab: str) -> str:
    script = (
        f"(async () => {{ for (const u of ['{tab}a', '{tab}b']) "
        "await fetch('/step.json?' + u).then((r) => r.text()); "
        "window.pressed = (window.pressed || 0) + 1; })()"
    )
    return press_button(name, script)


def test_a_tab_opened_again_after_another_tab_is_measured_as_its_own_step(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    buttons = tab_button("a", "t2") + tab_button("b", "t1")
    board(tmp_path, "tabs", TAB_LOAD, buttons)
    name = session()
    open_board(tmp_path, site, name, "tabs")
    try:
        press_clicks(tmp_path, name, "ab")
        assert measured(tmp_path, browser, name) == []
    finally:
        plain_step(tmp_path, name, "close")


CARRY_PRESS = (
    "(async () => { const from = window.tickStart; "
    "while (window.tickStart < from + 2) await new Promise((go) => setTimeout(go, 25)); "
    "while (window.tickDone < window.tickStart) await new Promise((go) => setTimeout(go, 25)); "
    "for (const u of ['c1', 'c2', 'c3']) await fetch('/step.json?' + u + Date.now()).then((r) => r.text()); "
    "window.pressed = (window.pressed || 0) + 1; })()"
)


def test_a_poll_that_carries_on_into_a_press_adds_no_wave_to_it(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    board(
        tmp_path,
        "carry",
        LOAD_WAVE + BACKGROUND_POLL,
        press_button("a", CARRY_PRESS),
    )
    name = session()
    open_board(tmp_path, site, name, "carry")
    try:
        quiet_apart_from_the_poll(tmp_path, name)
        plain_step(tmp_path, name, "click", "#a")
        pressed(tmp_path, name, 1)
        assert measured(tmp_path, browser, name) == []
    finally:
        plain_step(tmp_path, name, "close")


TWICE_AT_LOAD = (
    "Promise.all([0, 1].map(() => fetch('/step.json?dup').then((r) => r.text())));"
)
DUP_CHAIN = (
    "(async () => { for (const u of ['dup', 'x1', 'x2', 'x3']) "
    "await fetch('/step.json?' + u + Date.now()).then((r) => r.text()); "
    "window.pressed = (window.pressed || 0) + 1; })()"
)


def test_two_requests_at_once_for_one_address_are_no_poll(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    chain = DUP_CHAIN.replace(
        "'/step.json?' + u + Date.now()",
        "'/step.json?' + u + (u === 'dup' ? '' : Date.now())",
    )
    board(tmp_path, "dup", TWICE_AT_LOAD, press_button("a", chain))
    name = session()
    open_board(tmp_path, site, name, "dup")
    try:
        press_clicks(tmp_path, name, "a")
        assert measured(tmp_path, browser, name) == [("fetch-waterfall", "click 1")]
    finally:
        plain_step(tmp_path, name, "close")


SLOW_POLL = (
    "window.polls = new Set(); window.started = 0; window.ticks = 0; "
    "setInterval(() => { window.started += 1; window.polls.add(window.__heRequests.length); "
    "fetch('/step.json?poll').then((r) => r.text()).then(() => { window.ticks += 1; }); }, 1000);"
)


def test_a_slow_poll_does_not_keep_the_page_from_going_quiet(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    script = TAB_LOAD + SLOW_POLL
    board(tmp_path, "slow", script, press_button("a"))
    name = session()
    open_board(tmp_path, site, name, "slow")
    try:
        quiet_apart_from_the_poll(tmp_path, name)
        until(tmp_path, name, "window.started >= 1")
        plain_step(tmp_path, name, "click", "#a")
        pressed(tmp_path, name, 1)
        until(tmp_path, name, "window.ticks >= 3")
        assert measured(tmp_path, browser, name) == []
    finally:
        plain_step(tmp_path, name, "close")


THREE_WAVES = (
    "(async () => { for (const u of ['t1', 't2', 't3']) "
    "await fetch('/step.json?' + u).then((r) => r.text()); })();"
)
OPEN_LIVE = (
    "(async () => { await fetch('/step.json?live').then((r) => r.text()); "
    "setInterval(() => fetch('/step.json?live').then((r) => r.text()).then(() => { window.live = (window.live || 0) + 1; }), 1000); "
    "window.pressed = (window.pressed || 0) + 1; })()"
)


def test_a_click_that_opens_a_polling_view_is_measured_as_its_own_step(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    board(tmp_path, "live", THREE_WAVES, press_button("a", OPEN_LIVE))
    name = session()
    open_board(tmp_path, site, name, "live")
    try:
        press_clicks(tmp_path, name, "a")
        until(tmp_path, name, "(window.live || 0) >= 2")
        assert measured(tmp_path, browser, name) == []
    finally:
        plain_step(tmp_path, name, "close")
