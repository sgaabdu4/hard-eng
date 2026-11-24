"""Runtime browser audit guards: competing same-colour CTAs, duplicates, hierarchy, clipping, waterfalls, and CLS."""

import json
import threading
import time
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest
from test_browser import Site, plain_step, session
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
    "clipped-sticky-chrome": (
        (
            "<aside style='position:sticky;top:0;width:200px;height:620px;overflow:hidden'>"
            "<div style='height:610px'>Nav</div>"
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
        "await (await fetch('/step.json?w=' + i)).text();"
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


QUIET_SECONDS = 0.8
LOAD_WAVE = "Promise.all([0,1].map((i) => fetch('/step.json?l=' + i)));"
PRESS = (
    "(async () => { await fetch('/session', { method: 'POST' }); "
    "await fetch('/step.json?p=' + Date.now()); })()"
)
CHAIN = (
    "(async () => { for (let i = 0; i < 4; i++) "
    "await (await fetch('/step.json?w=' + i + Date.now())).text(); "
    "window.done = true; })()"
)
GET = "const get = (url) => fetch(url).then((reply) => reply.text()); "
HELD_CHAIN = (
    f"(async () => {{ {GET}await get('/step.json?a'); await get('/step.json?b'); "
    "await get('/gate'); await get('/step.json?d'); window.done = true; })();"
)
GAP_CHAIN = (
    f"(async () => {{ {GET}await get('/step.json?a'); await get('/step.json?b'); "
    "await new Promise((done) => setTimeout(done, 5000)); "
    "await get('/step.json?c'); await get('/step.json?d'); window.done = true; })();"
)


class Gate:
    def __init__(self) -> None:
        self.arrived = threading.Event()
        self.release = threading.Event()


@pytest.fixture
def gate(monkeypatch: pytest.MonkeyPatch) -> Gate:
    held = Gate()
    original = Site.do_GET

    def do_get(handler: Site) -> None:
        if handler.path.startswith("/gate"):
            held.arrived.set()
            held.release.wait(30)
            handler.reply(200, "{}")
        else:
            original(handler)

    monkeypatch.setattr(Site, "do_GET", do_get)
    return held


def board(tmp_path: Path, name: str, script: str, buttons: str = "") -> None:
    (tmp_path / "pages/step.json").write_text('{"ok":true}')
    (tmp_path / f"pages/{name}.html").write_text(
        "<!doctype html><html lang=en><title>Board</title>"
        "<style>body{margin:0;font:16px sans-serif}</style>"
        "<body><main><h1 style='font-size:24px;font-weight:700'>Board</h1>"
        f"{buttons}<p>Ready</p></main><script>{script}</script></body>"
    )


def press_button(name: str, script: str = PRESS) -> str:
    return (
        f"<button id={name} style='min-height:44px;min-width:120px;font-size:16px' "
        f'onclick="{script}">Press {name}</button>'
    )


def open_board(tmp_path: Path, site: str, name: str, page_name: str) -> None:
    plain_step(tmp_path, name, "set", "viewport", "768", "900")
    plain_step(tmp_path, name, "open", f"{site}/{page_name}.html")


def finished(tmp_path: Path, name: str) -> None:
    for _ in range(120):
        if plain_step(tmp_path, name, "eval", "window.done === true").strip() == "true":
            return
        time.sleep(0.5)
    raise AssertionError("the page chain did not finish")


def measured(
    tmp_path: Path, browser: ModuleType, name: str
) -> list[tuple[object, object]]:
    code = browser.browser_command(
        tmp_path, ["measure", "--session", name, "--name", "state"]
    )
    assert code == 0
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    return [(item["rule"], item.get("at")) for item in record["findings"]]


STAGGERED = (
    "(async () => { await Promise.all([0, 1, 2, 3, 4].map((i) => "
    "new Promise((go) => setTimeout(go, i * 20)).then(() => fetch('/step.json?s=' + i)).then((reply) => reply.text()))); "
    "window.done = true; })()"
)
XHR_CHAIN = (
    "(async () => { const get = (url) => new Promise((done) => { "
    "const request = new XMLHttpRequest(); request.open('GET', url); "
    "request.onload = () => done(request.responseText); request.send(); }); "
    "for (let i = 0; i < 4; i++) await get('/step.json?x=' + i + Date.now()); "
    "window.done = true; })()"
)


def prefetching(headers: str) -> str:
    return (
        "(async () => { const get = (url, headers) => fetch(url, { headers }).then((reply) => reply.text()); "
        "for (let i = 0; i < 3; i++) await get('/step.json?w=' + i + Date.now()); "
        f"for (let i = 0; i < 2; i++) await get('/step.json?x=' + i + Date.now(), {headers}); "
        "window.done = true; })()"
    )


def test_fetches_that_start_a_few_milliseconds_apart_count_as_one_wave(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    board(tmp_path, "staggered", STAGGERED)
    name = session()
    open_board(tmp_path, site, name, "staggered")
    try:
        finished(tmp_path, name)
        assert measured(tmp_path, browser, name) == []
    finally:
        plain_step(tmp_path, name, "close")


def test_a_four_xhr_chain_still_fails_with_the_request_delay(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    board(tmp_path, "xhr", XHR_CHAIN)
    name = session()
    open_board(tmp_path, site, name, "xhr")
    try:
        finished(tmp_path, name)
        assert measured(tmp_path, browser, name) == [("fetch-waterfall", "load")]
    finally:
        plain_step(tmp_path, name, "close")


@pytest.mark.parametrize(
    ("headers", "findings"),
    [
        ("{ 'Next-Router-Prefetch': '1' }", []),
        ("{ Purpose: 'prefetch' }", []),
        ("{ 'Sec-Purpose': 'prefetch;anonymous' }", []),
        ("{ Purpose: 'preview' }", [("fetch-waterfall", "load")]),
        ("{}", [("fetch-waterfall", "load")]),
    ],
)
def test_prefetch_requests_add_no_wave(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    headers: str,
    findings: list[tuple[object, object]],
) -> None:
    board(tmp_path, "prefetch", prefetching(headers))
    name = session()
    open_board(tmp_path, site, name, "prefetch")
    try:
        finished(tmp_path, name)
        assert measured(tmp_path, browser, name) == findings
    finally:
        plain_step(tmp_path, name, "close")


def test_a_session_without_the_request_delay_is_refused(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    board(tmp_path, "plain", "")
    name = session()
    monkeypatch.setattr(browser, "hold_script_file", lambda _folder: None)
    tool, folder = browser.ensure_tool(), browser.output_folder(tmp_path)
    try:
        browser.require(
            browser.run_tool(tool, folder, name, "open", f"{site}/plain.html")
        )
        code = browser.browser_command(
            tmp_path, ["measure", "--session", name, "--name", "state"]
        )
        assert code == 1
        assert "request delay" in capsys.readouterr().err
    finally:
        browser.run_tool(tool, folder, name, "close")


def test_each_press_is_measured_apart_from_the_load(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    buttons = "".join(press_button(name) for name in "abc")
    board(tmp_path, "presses", LOAD_WAVE, buttons)
    name = session()
    open_board(tmp_path, site, name, "presses")
    try:
        for button in "abc":
            time.sleep(QUIET_SECONDS)
            plain_step(tmp_path, name, "click", f"#{button}")
        time.sleep(QUIET_SECONDS)
        assert measured(tmp_path, browser, name) == []
    finally:
        plain_step(tmp_path, name, "close")


def test_a_four_wave_load_still_fails_after_an_older_action_in_the_session(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    board(tmp_path, "waterfall", CHAIN)
    name = session()
    open_board(tmp_path, site, name, "waterfall")
    try:
        finished(tmp_path, name)
        origin = float(plain_step(tmp_path, name, "eval", "performance.timeOrigin"))
        browser.actions_file(browser.output_folder(tmp_path), name).write_text(
            f"{int(origin) - 100} click\n"
        )
        assert measured(tmp_path, browser, name) == [("fetch-waterfall", "load")]
    finally:
        plain_step(tmp_path, name, "close")


def test_a_press_that_starts_a_four_wave_chain_fails_at_that_press(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    board(tmp_path, "chain", LOAD_WAVE, press_button("go", CHAIN))
    name = session()
    open_board(tmp_path, site, name, "chain")
    try:
        time.sleep(QUIET_SECONDS)
        plain_step(tmp_path, name, "click", "body")
        time.sleep(2)
        plain_step(tmp_path, name, "click", "#go")
        finished(tmp_path, name)
        assert measured(tmp_path, browser, name) == [("fetch-waterfall", "click 2")]
    finally:
        plain_step(tmp_path, name, "close")


@pytest.mark.parametrize("verb", ["hover", "click"])
def test_a_step_in_a_quiet_gap_that_starts_no_fetch_does_not_split_a_load_waterfall(
    tmp_path: Path, site: str, browser: ModuleType, verb: str
) -> None:
    board(tmp_path, "gap", GAP_CHAIN)
    name = session()
    open_board(tmp_path, site, name, "gap")
    try:
        time.sleep(QUIET_SECONDS)
        plain_step(tmp_path, name, verb, "body")
        finished(tmp_path, name)
        assert measured(tmp_path, browser, name) == [("fetch-waterfall", "load")]
    finally:
        plain_step(tmp_path, name, "close")


def test_a_click_while_a_fetch_is_in_flight_does_not_split_a_load_waterfall(
    tmp_path: Path, site: str, browser: ModuleType, gate: Gate
) -> None:
    board(tmp_path, "held", HELD_CHAIN)
    name = session()
    open_board(tmp_path, site, name, "held")
    try:
        assert gate.arrived.wait(20)
        plain_step(tmp_path, name, "click", "body")
        gate.release.set()
        finished(tmp_path, name)
        assert measured(tmp_path, browser, name) == [("fetch-waterfall", "load")]
    finally:
        gate.release.set()
        plain_step(tmp_path, name, "close")


def test_an_eval_step_and_the_page_cannot_add_an_action(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    board(tmp_path, "plain", "")
    name = session()
    open_board(tmp_path, site, name, "plain")
    marks = browser.actions_file(browser.output_folder(tmp_path), name)
    try:
        plain_step(
            tmp_path,
            name,
            "eval",
            "document.body.click(); localStorage.setItem('click', '1'); 'click'",
        )
        assert not marks.exists()
        plain_step(tmp_path, name, "click", "body")
        stamp, verb = marks.read_text().strip().split(" ", 1)
        assert stamp.isdigit()
        assert verb == "click"
    finally:
        plain_step(tmp_path, name, "close")


ARGUMENTS = {
    "click": (["click", "#a"], "click"),
    "dblclick": (["dblclick", "#a"], "dblclick"),
    "type": (["type", "#q", "click"], "type"),
    "fill": (["fill", "#q", "press"], "fill"),
    "press": (["press", "Enter"], "press"),
    "tap": (["tap", "#a"], "tap"),
    "key": (["key", "Enter"], "key"),
    "keydown": (["keydown", "Enter"], "keydown"),
    "keyup": (["keyup", "Enter"], "keyup"),
    "keyboard-type": (["keyboard", "type", "hello"], "keyboard type"),
    "keyboard-insert": (["keyboard", "inserttext", "hello"], "keyboard inserttext"),
    "check": (["check", "#c"], "check"),
    "uncheck": (["uncheck", "#c"], "uncheck"),
    "select": (["select", "#s", "one"], "select"),
    "drag": (["drag", "#a", "#b"], "drag"),
    "upload": (["upload", "#f", "a.txt"], "upload"),
    "download": (["download", "#a", "out.pdf"], "download"),
    "mouse-down": (["mouse", "down"], "mouse down"),
    "mouse-up": (["mouse", "up"], "mouse up"),
    "find-role": (["find", "role", "button", "click", "--name", "Go"], "find click"),
    "find-label": (["find", "label", "Email", "fill", "a@b.c"], "find fill"),
    "find-first": (["find", "first", ".row", "click"], "find click"),
    "find-nth": (["find", "nth", "1", "button", "click"], "find click"),
}
NO_MARK = {
    "hover": ["hover", "#a"],
    "focus": ["focus", "#a"],
    "scroll": ["scroll", "down"],
    "eval-click": ["eval", "document.body.click()"],
    "eval-word": ["eval", "click"],
    "wait-text": ["wait", "--text", "click"],
    "open-url": ["open", "http://x/click"],
    "get-text": ["get", "text", "click"],
    "snapshot": ["snapshot", "-i"],
    "find-hover": ["find", "text", "click", "hover"],
    "find-word": ["find", "text", "press", "hover"],
    "find-flag-first": ["find", "role", "button", "--name", "Go", "click"],
    "find-short": ["find", "text", "click"],
    "keyboard-other": ["keyboard", "press", "Enter"],
    "mouse-move": ["mouse", "move", "1", "2"],
    "mouse-wheel": ["mouse", "wheel", "5"],
    "unknown": ["rightclick", "#a"],
    "upper": ["CLICK", "#a"],
    "no-step": [""],
}


@pytest.mark.parametrize(("steps", "label"), ARGUMENTS.values(), ids=ARGUMENTS)
def test_a_step_that_commits_input_is_marked(
    browser: ModuleType, steps: list[str], label: str
) -> None:
    assert browser.action_mark(["--session", "s", *steps]) == ("s", label)
    assert browser.action_mark(["--session=s", *steps]) == ("s", label)


@pytest.mark.parametrize("steps", NO_MARK.values(), ids=NO_MARK)
def test_any_other_step_is_not_marked(browser: ModuleType, steps: list[str]) -> None:
    assert browser.action_mark(["--session", "s", *steps]) is None


@pytest.mark.parametrize(
    "argv",
    [
        ["click", "#a"],
        ["--session"],
        ["--session", "s"],
        ["--json", "--session", "s", "click", "#a"],
        ["--session", "s", "--headed", "click", "#a"],
        ["--session", "bad name!", "click", "#a"],
        ["--session", "../x", "click", "#a"],
    ],
    ids=[
        "no-session",
        "no-name",
        "no-verb",
        "flag-first",
        "flag-after",
        "spaces",
        "path",
    ],
)
def test_a_misread_step_is_not_marked(browser: ModuleType, argv: list[str]) -> None:
    assert browser.action_mark(argv) is None


def test_recording_an_action_never_fails_the_step_or_prints(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    capfd: pytest.CaptureFixture[str],
) -> None:
    folder = browser.output_folder(tmp_path)
    browser.actions_file(folder, "s").mkdir()
    browser.record_action(folder, ["--session", "s", "click", "#a"])
    browser.record_action(folder, ["--session", "t", "click", "#a"])
    seen = capfd.readouterr()
    assert (seen.out, seen.err) == ("", "")
    browser.actions_file(folder, "t").write_text("junk\n12 click\n-3 click\n9 \nx y\n")
    assert browser.session_actions(folder, "t") == [(12, "click")]

    board(tmp_path, "plain", "")
    name = session()
    open_board(tmp_path, site, name, "plain")
    browser.actions_file(folder, name).mkdir()
    try:
        plain_step(tmp_path, name, "click", "body")
    finally:
        plain_step(tmp_path, name, "close")


def test_display_heading_custom_select_sticky_sidebar_and_parallel_fetches_pass(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/step.json").write_text('{"ok":true}')
    (tmp_path / "pages/clean.html").write_text(
        "<!doctype html><html lang=en><title>Clean</title>"
        "<style>body{margin:0;font:500 16px sans-serif}</style>"
        "<body><div style='display:flex;align-items:flex-start'>"
        "<aside style='position:sticky;top:0;width:120px;height:960px;overflow:visible'>"
        "<div style='height:880px'>Nav</div>"
        "<button style='min-height:44px;min-width:100px;font-size:16px'>Sign out</button></aside>"
        "<main style='height:1800px;padding:16px'>"
        "<h1 style='font-size:48px;font-weight:400;margin:0'>Overview</h1>"
        "<p>Body copy at medium weight.</p>"
        "<label>Role <select aria-label='Role' style='appearance:none;-webkit-appearance:none;width:84px;height:44px;padding:0 4px;font-size:16px'>"
        "<option selected>Manager</option></select></label>"
        "</main></div>"
        "<script>Promise.all([0,1,2,3].map((i) => fetch('/step.json?p=' + i)));</script></body>"
    )
    found = capture(browser, tmp_path, site, "clean")
    for width in WIDTHS:
        assert found[width] == Counter(), (width, found[width])


def test_parenthesized_ternaries_generated_siblings_separate_fonts_and_theme_default(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: parenthesized ternaries pass, unrelated generated CSS is ignored, sibling font sheets count, and @theme default yields to explicit tokens."""
    from comments import validate_suppressions
    from conftest import change, commit, init
    from test_ui_rules import refused

    paren = change(
        tmp_path / "paren",
        "src/Status.tsx",
        "export const Status = () => <div />;\n",
        "export const Status = ({ ready, ro }: { ready: boolean; ro: boolean }) => (\n"
        '  <div>{ready && (ro ? <span key="status" /> : <em key="status" />)}</div>\n'
        ");\n"
        'export const list = (ready: boolean, ro: boolean) => [ready && (ro ? <span key="st" /> : <em key="st" />)];\n',
    )
    validate_suppressions(paren, "HEAD")

    sep = tmp_path / "sep"
    init(sep)
    (sep / ".gitattributes").write_text("src/preview.css linguist-generated=true\n")
    (sep / "src").mkdir()
    (sep / "src/fonts.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
    )
    (sep / "src/preview.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 500;\n}\n"
    )
    (sep / "src/brand.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 600;\n}\n"
    )
    (sep / "src/defaults.css").write_text(
        "@theme default {\n  --text-heading--font-weight: 500;\n}\n"
    )
    (sep / "src/app.css").write_text(
        '@import "./brand.css";\n@import "./defaults.css";\n'
    )
    (sep / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 600\n---\n# App\n"
    )
    commit(sep, "base")
    (sep / "src/app.css").write_text(
        '@import "./brand.css";\n@import "./defaults.css";\n/* touch */\n'
    )
    validate_suppressions(sep, "HEAD")
    (sep / "src/app.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    (sep / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 700\n---\n# App\n"
    )
    assert "outside loaded @font-face font-weight ranges" in refused(sep)


def test_bundle_font_isolation_generated_wrapper_and_text_initial_reset(
    tmp_path: Path,
) -> None:
    """HE-UI-SOURCE: bundle font faces stay isolated, generated wrappers still check edited imports, and --text-*: initial clears explicit weights."""
    from comments import validate_suppressions
    from conftest import commit, init
    from test_ui_rules import refused

    bundles = tmp_path / "bundles"
    init(bundles)
    (bundles / "src").mkdir()
    (bundles / "src/storefront.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 600;\n}\n"
    )
    (bundles / "src/admin.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 700;\n}\n'
    )
    (bundles / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontFamily: Inter\n    fontWeight: 700\n---\n# App\n"
    )
    commit(bundles, "base")
    (bundles / "src/storefront.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    assert "outside loaded @font-face font-weight ranges" in refused(bundles)

    wrap = tmp_path / "wrap"
    init(wrap)
    (wrap / ".gitattributes").write_text("src/bundle.css linguist-generated=true\n")
    (wrap / "src").mkdir()
    (wrap / "src/tokens.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    (wrap / "src/bundle.css").write_text('@import "./tokens.css";\n')
    (wrap / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 700\n---\n# App\n"
    )
    commit(wrap, "base")
    (wrap / "src/tokens.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 500;\n}\n"
    )
    assert "--text-heading--font-weight: 500" in refused(wrap)

    reset = tmp_path / "reset"
    init(reset)
    (reset / "src").mkdir()
    (reset / "src/app.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 500;\n}\n"
        "@theme {\n  --text-*: initial;\n}\n"
        "@theme default {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n"
    )
    (reset / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 700\n---\n# App\n"
    )
    commit(reset, "base")
    (reset / "src/app.css").write_text(
        (reset / "src/app.css").read_text() + "/* touch */\n"
    )
    validate_suppressions(reset, "HEAD")

    (reset / "src/app.css").write_text(
        "@theme {\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 500;\n}\n"
        "@theme {\n  --text-heading: initial;\n}\n"
    )
    assert "--text-heading--font-weight: 500" in refused(reset)

    mono_sep = tmp_path / "mono_sep"
    init(mono_sep)
    (mono_sep / "src").mkdir()
    (mono_sep / "src/mono.css").write_text(
        '@font-face {\n  font-family: "JetBrains Mono";\n  font-weight: 400 700;\n}\n'
        '@theme {\n  --font-mono: "JetBrains Mono", monospace;\n}\n'
    )
    (mono_sep / "src/app.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 600;\n}\n'
    )
    (mono_sep / "DESIGN.md").write_text(
        "---\ntypography:\n  heading:\n    fontWeight: 700\n---\n# App\n"
    )
    commit(mono_sep, "base")
    (mono_sep / "src/app.css").write_text(
        '@font-face {\n  font-family: "Inter";\n  font-weight: 400 600;\n}\n'
        '@theme {\n  --font-sans: "Inter", sans-serif;\n  --text-heading: 1.5rem;\n  --text-heading--font-weight: 700;\n}\n'
    )
    assert "outside loaded @font-face font-weight ranges" in refused(mono_sep)
