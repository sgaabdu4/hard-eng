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


VALUES_PAGE = (
    "<main><h1 style='font-size:24px;font-weight:700;margin:0 0 14px'>Board</h1>"
    "<p style='margin:0 0 14px;color:#767676;font-size:16px'>Grey on white</p>"
    "<p style='margin:0;color:#000;font-size:16px'>Black on white</p>"
    "<div style='margin-top:14px'><button style='min-height:44px;min-width:120px;font-size:16px'>Go</button></div>"
    "<p style='margin:14px 0 0;color:rgba(0,0,0,0.5);font-size:16px'>Half ink</p>"
    "<p style='margin:14px 0 0'><span style='display:inline-block;padding:2px 8px;background:#e6efe9;color:#2d6a4f;font-size:10.5px;font-weight:600'>Paid</span></p></main>"
)


def test_the_record_holds_each_element_with_its_facts(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/values.html").write_text(
        "<!doctype html><html lang=en><title>Values</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{VALUES_PAGE}</body>"
    )
    name = session()
    open_board(tmp_path, site, name, "values")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    values = record["measured"]
    texts = {item["at"]: item for item in values["texts"]}
    grey = texts["Grey on white"]
    assert (grey["fg"], grey["bg"], grey["px"], grey["ratio"]) == (
        "#767676",
        "#ffffff",
        16,
        4.54,
    )
    assert (grey["weight"], grey["colour"], grey["fill"], grey["under"]) == (
        400,
        "767676ff",
        "",
        False,
    )
    assert texts["Board"]["weight"] == 700
    assert texts["Half ink"]["colour"] == "00000080"
    paid = texts["Paid"]
    assert (
        paid["px"],
        paid["weight"],
        paid["colour"],
        paid["fill"],
        paid["under"],
    ) == (
        10.5,
        600,
        "2d6a4fff",
        "e6efe9ff",
        True,
    )
    assert {"at": "Board", "to": "Grey on white", "px": 14, "axis": "y"} in values[
        "gaps"
    ]
    go = next(item for item in values["sizes"]["controls"] if item["at"] == "Go")
    assert (go["w"], go["h"], go["floor"], go["under"], go["exempt"]) == (
        120,
        44,
        44,
        False,
        False,
    )
    assert "contrast" not in values
    assert "text_px" not in values["sizes"]


def test_the_record_holds_the_corner_radius_of_every_rounded_element(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    (tmp_path / "pages/radii.html").write_text(
        "<!doctype html><html lang=en><title>Radii</title>"
        "<style>body{margin:0;font:16px sans-serif}</style><body><main>"
        "<h1 style='font-size:24px;margin:0 0 14px'>Radii</h1>"
        "<button style='min-height:44px;min-width:120px;font-size:16px;border-radius:6px'>Go</button>"
        "<p style='margin:14px 0'><span style='display:inline-block;padding:2px 8px;background:#dde;border-radius:4px;font-size:14px'>New</span></p>"
        "<div style='height:30px;border-radius:12px;background:#eee'></div>"
        "<div style='width:40px;height:40px;border-radius:8px;overflow:hidden'></div>"
        "<p style='margin:14px 0'><span style='display:inline-block;padding:2px 12px;background:#cde;border-radius:9999px;font-size:14px'>Pill</span></p></main></body>"
    )
    name = session()
    open_board(tmp_path, site, name, "radii")
    try:
        measured(tmp_path, browser, name)
    finally:
        plain_step(tmp_path, name, "close")
    record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
    radii = {(item["at"], item["px"]) for item in record["measured"]["radii"]}
    assert {("Go", 6), ("New", 4)} <= radii
    assert {6, 4, 12, 8} <= {px for _, px in radii}
    assert max(px for _, px in radii) < 100


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


KIND_TOKENS = (
    "---\ncolors:\n  ink: '#1a1a1a'\n  mint: '#e6efe9'\nspacing:\n  sm: 8px\n  md: 14px\n"
    "rounded:\n  sm: 4px\n  md: 6px\n---\n# Design\n\n## Overview\nPlain.\n"
)
KIND_PAGE = (
    "<main><h1 style='font-size:24px;margin:0 0 14px'>Kinds</h1>"
    "<p style='margin:0 0 14px;font-size:10px'>Fine print</p>"
    "<p style='margin:0 0 14px;font-size:14px'>Body copy</p>"
    "<p style='margin:0 0 14px;font-size:14px;color:#767676'>Off token</p>"
    "<div style='margin:0 0 14px;font-size:14px;background:#e6efe9;color:#1a1a1a;display:inline-block'>On token</div>"
    "<section><div>Alpha block</div><div style='margin-top:11px'>Beta block</div></section>"
    "<section style='margin-top:14px'><div>Gamma block</div><div style='margin-top:14px'>Delta block</div></section>"
    "<div style='margin:14px 0;border-radius:7px;background:#ddd;display:inline-block;padding:8px'>Round seven</div>"
    "<div style='margin:14px 0;border-radius:6px;background:#ddd;display:inline-block;padding:8px'>Round six</div>"
    "<div><button style='width:30px;height:30px;font-size:12px'>Tiny one</button>"
    "<button style='min-height:44px;min-width:120px;font-size:16px'>Big one</button></div>"
    "<div style='margin:14px 0 0;text-align:center;font-size:14px'>Centred note</div>"
    "<div style='margin:14px 0 0;font-size:14px'>Left note</div>"
    "<div style='display:flex;gap:14px;margin:14px 0 0;font-size:14px'><span>Even one</span><span>Even two</span></div>"
    "<div style='display:flex;gap:14px;margin:14px 0 0;font-size:14px'><span>Light one</span><b>Bold two</b></div></main>"
)
KIND_CASES = {
    ("size", "Fine print"): False,
    ("size", "Body copy"): True,
    ("colour", "Off token"): None,
    ("colour", "On token"): None,
    ("gap", "Alpha block to Beta block"): None,
    ("gap", "Gamma block to Delta block"): None,
    ("radius", "Round seven"): None,
    ("radius", "Round six"): None,
    ("tap", "Tiny one"): False,
    ("tap", "Big one"): True,
    ("align", "Centred note"): True,
    ("align", "Left note"): False,
    ("weight", "Even one"): True,
    ("weight", "Bold two"): False,
}


def test_code_decides_each_kind_the_same_way_in_five_real_captures(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    import look_facts

    (tmp_path / "DESIGN.md").write_text(KIND_TOKENS)
    tokens = look_facts.design_tokens(tmp_path)
    (tmp_path / "pages/kinds.html").write_text(
        "<!doctype html><html lang=en><title>Kinds</title>"
        f"<style>body{{margin:0;font:16px sans-serif}}</style><body>{KIND_PAGE}</body>"
    )
    runs = []
    for _ in range(5):
        name = session()
        open_board(tmp_path, site, name, "kinds")
        try:
            measured(tmp_path, browser, name)
        finally:
            plain_step(tmp_path, name, "close")
        record = json.loads((tmp_path / ".hard-eng/browser/state-768.json").read_text())
        runs.append(
            {
                case: look_facts.verdict(case[0], case[1], record["measured"], tokens)
                for case in KIND_CASES
            }
        )
    assert all(run == runs[0] for run in runs)
    assert {
        case: found[0] if found else None for case, found in runs[0].items()
    } == KIND_CASES
