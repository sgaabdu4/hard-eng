"""A repeat of an earlier finished request adds no fetch wave; any other request chain still counts."""

from pathlib import Path
from types import ModuleType

import pytest
from test_browser import plain_step, session
from test_ui_audit_guards import board, finished, measured, open_board

LOOP = (
    "(async () => { const go = (n) => CALL; PREFACE"
    "for (let i = 0; i < COUNT; i++) { await go(i); await new Promise((r) => setTimeout(r, GAP)); } "
    "window.done = true; })();"
)
LOAD = (
    "await fetch('/step.json?a').then((r) => r.text()); "
    "await fetch('/step.json?b').then((r) => r.text()); "
)
FORM = (
    "(() => { const f = new FormData(); f.append('a', '1'); "
    "return fetch('/session', { method: 'POST', body: f }).then((r) => r.text()); })()"
)
POST = "fetch('/session', { method: 'POST', body: BODY }).then((r) => r.text())"
XHR = (
    "new Promise((done) => { const q = new XMLHttpRequest(); q.open('POST', '/session'); "
    "q.onload = () => done(q.responseText); q.send(BODY); })"
)
POLLS = {
    "fetch-get": "fetch('/step.json?poll').then((r) => r.text())",
    "fetch-string-body": POST.replace("BODY", "'poll=1'"),
    "fetch-search-params": POST.replace("BODY", "new URLSearchParams({ poll: 1 })"),
    "xhr-string-body": XHR.replace("BODY", "'poll=1'"),
    "xhr-no-body": XHR.replace("BODY", ""),
}
CHAINS = {
    "fetch-different-string-bodies": POST.replace(
        "BODY", "JSON.stringify({ step: n })"
    ),
    "fetch-form-data": FORM,
    "fetch-blob": POST.replace("BODY", "new Blob(['same'])"),
    "fetch-request-with-body": (
        "fetch(new Request('/session', { method: 'POST', body: 'same' })).then((r) => r.text())"
    ),
    "xhr-different-string-bodies": XHR.replace("BODY", "'step=' + n"),
    "xhr-form-data": XHR.replace(
        "BODY", "(() => { const f = new FormData(); f.append('a', '1'); return f; })()"
    ),
}


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


@pytest.mark.parametrize("call", POLLS.values(), ids=POLLS)
def test_a_poll_that_repeats_after_the_load_adds_no_wave(
    tmp_path: Path, site: str, browser: ModuleType, call: str
) -> None:
    script = (
        LOOP.replace("CALL", call)
        .replace("PREFACE", LOAD)
        .replace("COUNT", "5")
        .replace("GAP", "300")
    )
    assert run(tmp_path, site, browser, script) == []


@pytest.mark.parametrize("call", CHAINS.values(), ids=CHAINS)
def test_a_chain_to_one_address_with_a_new_body_each_time_still_fails(
    tmp_path: Path, site: str, browser: ModuleType, call: str
) -> None:
    script = (
        LOOP.replace("CALL", call)
        .replace("PREFACE", "")
        .replace("COUNT", "4")
        .replace("GAP", "0")
    )
    assert run(tmp_path, site, browser, script) == [("fetch-waterfall", "load")]
