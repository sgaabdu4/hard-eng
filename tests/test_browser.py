import fcntl
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zlib
from collections.abc import Callable, Generator, Mapping
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import override

import pytest

SOURCE = Path(__file__).resolve().parents[1]
SECRET_WORD = "typed-only-on-stdin"
LOGIN = (
    "<form method=post action=/session>"
    "<input name=username type=text><input name=password type=password>"
    "<button type=submit>Sign in</button></form>"
)
PLAIN_STEP = (
    "import sys; from pathlib import Path; from browser import browser_command; "
    "raise SystemExit(browser_command(Path(sys.argv[1]), sys.argv[2:]))"
)


class Site(SimpleHTTPRequestHandler):
    def reply(self, status: int, body: str, *headers: tuple[str, str]) -> None:
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    @override
    def do_GET(self) -> None:
        if self.path == "/login":
            self.reply(200, LOGIN)
        elif self.path == "/home":
            signed = "sid=session-7741" in self.headers.get("Cookie", "")
            self.reply(200, "<p>signed in</p>" if signed else "<p>anonymous</p>")
        else:
            super().do_GET()


def sign_in(handler: Site) -> None:
    handler.rfile.read(int(handler.headers.get("Content-Length", 0)))
    handler.reply(
        303,
        "",
        ("Set-Cookie", "sid=session-7741; Path=/"),
        ("Location", "/home"),
    )


def stay_quiet(handler: Site, format: str, *arguments: object) -> None:
    del handler, format, arguments


def serve_pages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    monkeypatch.setattr(Site, "do_POST", sign_in, raising=False)
    monkeypatch.setattr(Site, "log_message", stay_quiet)
    pages = tmp_path / "pages"
    pages.mkdir()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Site, directory=str(pages))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
    yield from serve_pages(tmp_path, monkeypatch)


def load_browser(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("PATH", os.environ["PATH"])
    import browser as module

    keep_hosted_sandbox(
        os.environ,
        lambda: module.sandbox_refusal([]) is not None,
        run_as_shell,
        Path(tempfile.gettempdir()) / "hard-eng-browser-profile.lock",
    )
    return module


@pytest.fixture
def browser(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    return load_browser(monkeypatch)


def no_provision(monkeypatch: pytest.MonkeyPatch, shared: Path) -> None:
    import tool_setup

    def provision(
        batch: list[str], timeout: float, offline: bool | None = None
    ) -> None:
        del batch, timeout, offline

    monkeypatch.setattr(tool_setup, "provision_batch", provision)
    monkeypatch.setattr(tool_setup, "shared_tool_folder", lambda: shared)


def keep_hosted_sandbox(
    environ: Mapping[str, str],
    needed: Callable[[], bool],
    run: Callable[[str], object],
    lock: Path,
) -> bool:
    """GitHub's Ubuntu runners limit user namespaces; their passwordless sudo adds the profile."""
    if environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        return False
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if not needed():
            return False
        import browser

        run(browser.root_step())
    return True


def run_as_shell(step: str) -> None:
    subprocess.run(["sh", "-c", step], check=True)


def page(tmp_path: Path, name: str, body: str) -> None:
    (tmp_path / "pages" / name).write_text(
        f"<!doctype html><html lang=en><title>Page</title><body>{body}</body>"
    )


def session() -> str:
    return "test-" + uuid.uuid4().hex[:8]


def open_sessions(browser: ModuleType, root: Path) -> str:
    return subprocess.run(
        [browser.ensure_tool(), "session", "list"],
        capture_output=True,
        text=True,
        check=False,
        env=browser.checkout_space(browser.output_folder(root)),
    ).stdout


def paeth(left: int, above: int, corner: int) -> int:
    guess = left + above - corner
    nearest = min(abs(guess - value) for value in (left, above, corner))
    for value in (left, above, corner):
        if abs(guess - value) == nearest:
            return value
    raise AssertionError


def decode(path: Path) -> tuple[int, int, list[bytes], int]:
    data = path.read_bytes()
    chunks: dict[bytes, bytes] = {}
    position = 8
    while position < len(data):
        size = int.from_bytes(data[position : position + 4], "big")
        kind = data[position + 4 : position + 8]
        chunks.setdefault(kind, b"")
        chunks[kind] += data[position + 8 : position + 8 + size]
        position += size + 12
    width, height = (
        int.from_bytes(chunks[b"IHDR"][:4], "big"),
        int.from_bytes(chunks[b"IHDR"][4:8], "big"),
    )
    step = {2: 3, 6: 4}[chunks[b"IHDR"][9]]
    raw = zlib.decompress(chunks[b"IDAT"])
    rows: list[bytes] = []
    for y in range(height):
        start = y * (width * step + 1)
        kind, line = raw[start], bytearray(raw[start + 1 : start + 1 + width * step])
        above = rows[-1] if rows else bytes(width * step)
        for x in range(len(line)):
            left = line[x - step] if x >= step else 0
            corner = above[x - step] if x >= step else 0
            line[x] = (
                line[x]
                + [
                    0,
                    left,
                    above[x],
                    (left + above[x]) // 2,
                    paeth(left, above[x], corner),
                ][kind]
            ) % 256
        rows.append(bytes(line))
    return width, height, rows, step


def plain_step(root: Path, name: str, *arguments: str) -> str:
    done = subprocess.run(
        [sys.executable, "-c", PLAIN_STEP, str(root), "--session", name, *arguments],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(SOURCE / ".hooks")},
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


def is_red(rows: list[bytes], step: int, x: int, y: int) -> bool:
    red, green, blue = rows[y][x * step : x * step + 3]
    return red > 200 and green < 60 and blue < 60


def found_at(tool: Path, name: str) -> str:
    del name
    return str(tool)


def fake_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    tool = tmp_path / "agent-browser"
    tool.write_text("#!/bin/sh\n" + body)
    tool.chmod(0o755)
    monkeypatch.setattr(shutil, "which", functools.partial(found_at, tool))
    return tool


def test_installs_like_other_tools(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser: ModuleType,
    capfd: pytest.CaptureFixture[str],
) -> None:
    import tool_setup

    log = tmp_path / "log"
    tool = fake_tool(
        tmp_path, monkeypatch, f'echo "$@" >> {log}\necho "Installing Chrome..."\n'
    )
    calls: list[tuple[list[str], bool | None]] = []
    broken: list[bool] = []

    def provision(
        batch: list[str], timeout: float, offline: bool | None = None
    ) -> None:
        del timeout
        print("Prepare latest native tools: " + ", ".join(batch))
        calls.append((batch, offline))
        if broken and not offline:
            raise ValueError("offline")

    monkeypatch.setattr(tool_setup, "provision_batch", provision)
    monkeypatch.setattr(tool_setup, "shared_tool_folder", lambda: tmp_path / "shared")
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("x")
    before = sorted(path.name for path in project.iterdir())

    for _ in range(2):
        assert browser.ensure_tool() == str(tool)
    stamp = tmp_path / "shared/browser-refreshed"
    os.utime(stamp, (time.time() - 3 * 86400,) * 2)
    broken.append(True)
    browser.ensure_tool()

    assert calls == [
        (["npm:agent-browser@latest"], False),
        (["npm:agent-browser@latest"], True),
        (["npm:agent-browser@latest"], False),
        (["npm:agent-browser@latest"], True),
    ]
    assert log.read_text().splitlines() == ["install"]
    assert sorted(path.name for path in project.iterdir()) == before

    assert capfd.readouterr().out == ""


def test_each_tool_path_installs_chrome_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, browser: ModuleType
) -> None:

    log = tmp_path / "log"
    tools = []
    for checkout in ("first", "second"):
        (tmp_path / checkout).mkdir()
        tools.append(
            fake_tool(tmp_path / checkout, monkeypatch, f"echo {checkout} >> {log}\n")
        )

    no_provision(monkeypatch, tmp_path / "shared")
    for tool in [*tools, *tools, *tools]:
        monkeypatch.setattr(shutil, "which", functools.partial(found_at, tool))
        assert browser.ensure_tool() == str(tool)
    clock = tmp_path / "shared/browser-refreshed"
    started = clock.stat().st_mtime
    os.utime(clock, (started - 3600,) * 2)
    browser.ensure_tool()
    assert log.read_text().splitlines() == ["first", "second"]
    assert clock.stat().st_mtime == started - 3600


def test_parallel_first_runs_install_chrome_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, browser: ModuleType
) -> None:

    log, busy = tmp_path / "log", tmp_path / "busy"
    fake_tool(
        tmp_path,
        monkeypatch,
        f"mkdir {busy} || exit 3\nsleep 0.3\necho install >> {log}\nrmdir {busy}\n",
    )

    no_provision(monkeypatch, tmp_path / "shared")
    failures: list[BaseException] = []

    def run() -> None:
        try:
            browser.ensure_tool()
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            failures.append(error)

    workers = [threading.Thread(target=run) for _ in range(4)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert failures == []
    assert log.read_text().splitlines() == ["install"]


def test_refuses_switching_off_the_sandbox(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser: ModuleType,
    capsys: pytest.CaptureFixture[str],
) -> None:
    switch = ["--session", "a", "--args", "--disable-gpu,--no-sandbox", "open", "x"]
    assert browser.browser_command(tmp_path, switch) == 2
    assert "--no-sandbox" in capsys.readouterr().err
    monkeypatch.setenv("AGENT_BROWSER_ARGS", "--no-sandbox")
    assert browser.browser_command(tmp_path, ["--session", "a", "open", "x"]) == 2
    assert "--no-sandbox" in capsys.readouterr().err
    monkeypatch.delenv("AGENT_BROWSER_ARGS")

    limit, profile = tmp_path / "limit", tmp_path / "apparmor/agent-browser-chrome"
    limit.write_text("1\n")
    monkeypatch.setattr(browser, "USERNS_LIMIT", limit)
    monkeypatch.setattr(browser, "CHROME_PROFILE", profile)
    assert browser.browser_command(tmp_path, ["--session", "a", "open", "x"]) == 2
    message = capsys.readouterr().err
    assert f"sudo apparmor_parser -r {profile}" in message
    step = message[message.index("printf") :].split(" | ")[0]
    text = subprocess.run(
        ["sh", "-c", step], capture_output=True, text=True, check=True
    ).stdout
    assert "@{HOME}/.agent-browser/browsers/chrome-*/chrome" in text
    assert "  userns,\n" in text
    profile.parent.mkdir()
    profile.write_text(text)
    assert browser.sandbox_refusal(["--session", "a", "open", "x"]) is None


def test_runs_from_output_folder(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        "oops.html",
        "<script>console.error('console-boom');"
        "setTimeout(() => { throw new Error('page-oops'); });</script>",
    )
    name = session()

    def step(*arguments: str) -> str:
        return plain_step(tmp_path, name, *arguments)

    try:
        step("open", f"{site}/oops.html")
        step("wait", "--load", "networkidle")
        assert "console-boom" in step("console")
        assert "page-oops" in step("errors")
        step("screenshot", "shot.png")
    finally:
        step("close")
    assert (tmp_path / ".hard-eng/browser/shot.png").is_file()


def test_same_session_name_in_two_checkouts_stays_apart(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(tmp_path, "one.html", "<p>one</p>")
    page(tmp_path, "two.html", "<p>two</p>")
    first, second, name = tmp_path / "first", tmp_path / "second", session()
    try:
        plain_step(first, name, "open", f"{site}/one.html")
        plain_step(second, name, "open", f"{site}/two.html")
        assert "one.html" in plain_step(first, name, "eval", "location.pathname")
    finally:
        plain_step(first, name, "close")
        plain_step(second, name, "close")
    for root in (first, second):
        assert name not in open_sessions(browser, root)


def test_refuses_shared_sessions(
    tmp_path: Path, site: str, browser: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    assert browser.browser_command(tmp_path, ["open", "http://x"]) == 2
    assert "--session" in capsys.readouterr().err
    assert browser.browser_command(tmp_path, ["--session", "a", "close", "--all"]) == 2
    assert "close --all" in capsys.readouterr().err

    page(tmp_path, "one.html", "<p id=one>one</p>")
    name = session()
    code = browser.browser_command(
        tmp_path,
        ["capture", f"{site}/one.html", "--session", name, "--ring", "#none"],
    )
    assert code == 1
    assert "matched no visible element" in capsys.readouterr().err
    assert name not in open_sessions(browser, tmp_path)


def test_capture_draws_boxes_at_each_width(
    tmp_path: Path, site: str, browser: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    page(
        tmp_path,
        "boxes.html",
        "<style>body{margin:0;height:1600px}div{position:absolute;background:#def}</style>"
        "<div id=a style='left:20px;top:40px;width:100px;height:60px'></div>"
        "<div id=b style='left:30px;top:1100px;width:150px;height:80px'></div>",
    )
    page(
        tmp_path,
        "wide.html",
        "<style>body{margin:0}div{width:900px;height:5px;background:#def}</style><div></div>",
    )
    name = session()
    code = browser.browser_command(
        tmp_path,
        [
            "capture",
            f"{site}/boxes.html",
            "--session",
            name,
            "--ring",
            "#a",
            "--ring",
            "#b",
            "--name",
            "boxes",
        ],
    )
    assert code == 0
    folder = tmp_path / ".hard-eng/browser"
    assert capsys.readouterr().out.split() == [
        str(folder / "boxes-390.png"),
        str(folder / "boxes-768.png"),
        str(folder / "boxes-1280.png"),
    ]
    assert (
        browser.browser_command(
            tmp_path,
            ["capture", f"{site}/wide.html", "--session", name, "--name", "wide"],
        )
        == 0
    )
    overflow = {
        width: [
            finding["rule"]
            for finding in json.loads((folder / f"wide-{width}.json").read_text())[
                "findings"
            ]
        ]
        for width in (390, 768, 1280)
    }
    assert overflow == {390: ["overflow"], 768: ["overflow"], 1280: []}
    for width in (390, 768, 1280):
        image_width, height, rows, step = decode(folder / f"boxes-{width}.png")
        assert image_width == width
        assert height >= 1600
        for left, top, wide, high in ((20, 40, 100, 60), (30, 1100, 150, 80)):
            assert is_red(rows, step, left + 1, top + high // 2)
            assert is_red(rows, step, left + wide // 2, top + 1)
            assert is_red(rows, step, left + wide - 2, top + high // 2)
            assert not is_red(rows, step, left + wide // 2, top + high // 2)
    assert name not in open_sessions(browser, tmp_path)


def test_measure_records_an_open_session_state(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        "state.html",
        "<button id=show style='width:60px;height:44px;font-size:16px' "
        "onclick=\"document.body.insertAdjacentHTML('beforeend',"
        "'<p id=late style=font-size:10px>Opened</p>')\">Show</button>",
    )
    name = session()
    plain_step(tmp_path, name, "set", "viewport", "768", "900")
    plain_step(tmp_path, name, "open", f"{site}/state.html")
    plain_step(tmp_path, name, "click", "#show")
    plain_step(tmp_path, name, "wait", "#late")
    code = browser.browser_command(
        tmp_path,
        ["measure", "--session", name, "--name", "state", "--ring", "#late"],
    )
    assert code == 0
    folder = tmp_path / ".hard-eng/browser"
    record = json.loads((folder / "state-768.json").read_text())
    assert [item["rule"] for item in record["findings"]] == ["text-size"]
    assert record["width"] == 768
    image = folder / "state-768.png"
    assert record["sha256"] == hashlib.sha256(image.read_bytes()).hexdigest()
    _, _, rows, step = decode(image)
    rect = json.loads(
        json.loads(
            plain_step(
                tmp_path,
                name,
                "eval",
                "JSON.stringify(document.querySelector('#late').getBoundingClientRect())",
            )
        )
    )
    assert is_red(
        rows, step, int(rect["x"]) + 1, int(rect["y"]) + int(rect["height"]) // 2
    )
    assert name in open_sessions(browser, tmp_path)
    plain_step(tmp_path, name, "close")


def test_capture_places_fixed_bars_once_at_their_edge(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        "bars.html",
        "<style>body{margin:0;height:2400px}div{position:fixed;left:0;right:0}"
        "#top{top:0;height:40px;background:#00c800}"
        "#bottom{bottom:0;height:60px;background:#0000c8}"
        "#label{position:absolute;left:20px;top:1200px;width:100px;height:30px}"
        "#side{top:0;bottom:0;right:auto;width:30px;background:#c8c800}"
        ".blob{width:300px;height:300px;border-radius:50%;background:#c800c8}"
        "#high{top:-100px;left:auto;right:-150px}"
        "#low{bottom:-100px;left:-150px;right:auto}</style>"
        "<div class=blob id=high></div><div class=blob id=low></div>"
        "<div id=top></div><div id=bottom></div><div id=side></div>"
        "<p id=label>middle</p>",
    )
    code = browser.browser_command(
        tmp_path,
        [
            "capture",
            f"{site}/bars.html",
            "--session",
            session(),
            "--ring",
            "#bottom",
            "--ring",
            "#label",
            "--name",
            "bars",
        ],
    )
    assert code == 0
    for width in (390, 1280):
        wide, height, rows, step = decode(
            tmp_path / f".hard-eng/browser/bars-{width}.png"
        )
        assert (wide, height) == (width, 2400)
        inside_ring = range(height - 57, height - 3)
        for colour, wanted in ((1, range(40)), (2, inside_ring)):
            seen = {
                y
                for y in range(height)
                if rows[y][width // 2 * step + colour] > 190
                and sum(rows[y][width // 2 * step : width // 2 * step + 3]) < 260
            }
            assert seen == set(wanted), (width, colour, min(seen), max(seen))
        side = {
            y
            for y in range(height)
            if rows[y][15 * step] > 190
            and rows[y][15 * step + 1] > 190
            and rows[y][15 * step + 2] < 60
        }
        assert side == set(range(900)), (width, min(side, default=-1), len(side))
        assert is_red(rows, step, 21, 1231)
        assert is_red(rows, step, width // 2, height - 59)
        assert is_red(rows, step, width // 2, height - 1)


def test_capture_hides_emails_and_phones(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        "private.html",
        "<p id=t>Mail bob@example.com or call +44 7700 900123 and 555-123-4567."
        " Text 07700 900456 or 98765 43210. Paid $1,234.56 on 2026-11-14.</p>"
        "<p id=late>later</p>"
        "<input id=e value=carol@example.org><textarea id=n>0207 123 4567</textarea>",
    )
    tool, folder, name = browser.ensure_tool(), tmp_path, session()
    script = browser.PAGE_SCRIPT.replace("RINGS", "[]")

    def step(*arguments: str, text: str | None = None) -> str:
        return browser.require(
            browser.run_tool(tool, folder, name, *arguments, text=text)
        )

    try:
        step("open", f"{site}/private.html")
        step("wait", "--load", "networkidle")
        step("eval", "--stdin", text=script)
        shown = json.loads(
            step(
                "eval",
                "--stdin",
                text="(async () => {"
                "document.querySelector('#late').firstChild.nodeValue = 'dan@example.net';"
                "document.body.append(Object.assign(document.createElement('p'),"
                "{textContent: 'call 07700 900789'}));"
                "await Promise.resolve();"
                "return JSON.stringify([document.body.innerText,"
                "document.querySelector('#e').value,"
                "document.querySelector('#n').value]);})()",
            )
        )
    finally:
        step("close")
    text, email, number = json.loads(shown)
    assert not re.search(r"@|\d{3}[ -]\d{3}|\+44", text + email + number)
    assert text.count("[hidden]") == 7
    assert email == "[hidden]"
    assert number == "[hidden]"
    assert "$1,234.56 on 2026-11-14" in text


FRAME_CHANGES = (
    "(async () => {"
    "const shadow = document.querySelector('#host').shadowRoot;"
    "shadow.append(Object.assign(document.createElement('p'),"
    "{textContent: 'late zed@example.com'}));"
    "const same = document.querySelector('#same');"
    "const sameText = same.contentDocument.body.textContent;"
    "same.src = OTHER + '/inner.html';"
    "document.body.append(Object.assign(document.createElement('iframe'),"
    "{id: 'late', src: OTHER + '/inner.html'}));"
    "const spot = document.querySelector('#spot').attachShadow({mode: 'closed'});"
    "spot.innerHTML = '<iframe id=later src=' + OTHER + '/inner.html></iframe>';"
    "await Promise.resolve();"
    "const kind = (root, id) => { const found = root.querySelector('#' + id);"
    "return found ? found.tagName + ('hardEngFrame' in found.dataset ? ':held' : '') : 'gone'; };"
    "const forced = document.querySelector('#forced').getBoundingClientRect();"
    "return JSON.stringify([shadow.textContent, sameText,"
    "['same', 'hidden', 'forced', 'thing', 'late'].map((id) => kind(document, id))"
    ".concat(kind(shadow, 'deep'), kind(spot, 'later')), [forced.width, forced.height]]);})()"
)


def test_capture_replaces_frames_it_cannot_read(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    other = site.replace("127.0.0.1", "localhost")
    page(tmp_path, "inner.html", "<p>other frame bob@example.com</p>")
    page(tmp_path, "same.html", "<p>frame 07700 900111</p>")
    page(
        tmp_path,
        "nested.html",
        "<div id=host></div><div id=spot></div><iframe id=same src='/same.html'></iframe>"
        f"<iframe id=hidden style='display:none' src='{other}/inner.html'></iframe>"
        "<iframe id=forced style='visibility:visible !important;width:200px;"
        f"height:100px' src='{other}/inner.html'></iframe>"
        f"<object id=thing data='{other}/inner.html' style='width:50px;height:50px'>"
        "</object><script>document.querySelector('#host').attachShadow({mode: 'open'})"
        ".innerHTML = '<p>shadow eve@example.com</p>"
        f'<iframe id=deep src="{other}/inner.html"></iframe>\';</script>',
    )
    tool, name = browser.ensure_tool(), session()

    def step(*arguments: str, text: str | None = None) -> str:
        return browser.require(
            browser.run_tool(tool, tmp_path, name, *arguments, text=text)
        )

    try:
        step("open", f"{site}/nested.html")
        step("wait", "--load", "networkidle")
        step("eval", "--stdin", text=browser.PAGE_SCRIPT.replace("RINGS", "[]"))
        changes = FRAME_CHANGES.replace("OTHER", json.dumps(other))
        shown = step("eval", "--stdin", text=changes)
        unread = step("eval", browser.FRAME_CHECK)
    finally:
        step("close")
    shadow, same, kinds, forced = json.loads(json.loads(shown))
    assert shadow.count("[hidden]") == 2
    assert "@" not in shadow
    assert "frame [hidden]" in same
    assert kinds == ["DIV:held"] * 7
    assert forced == [204, 104]
    assert json.loads(unread) == 0


def test_capture_fails_with_no_image_when_a_frame_slips_past(
    tmp_path: Path, site: str, browser: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    other = site.replace("127.0.0.1", "localhost")
    page(tmp_path, "inner.html", "<p>other frame bob@example.com</p>")
    page(
        tmp_path,
        "slip.html",
        "<p id=a>a</p><div id=spot style='width:10px;height:10px'></div><script>"
        "const attach = Element.prototype.attachShadow;"
        "let done = false; new MutationObserver(() => { if (done) return; done = true;"
        "attach.call(document.querySelector('#spot'), {mode: 'open'}).innerHTML ="
        f" \"<iframe src='{other}/inner.html'></iframe>\"; }})"
        ".observe(document.documentElement, {childList: true});</script>",
    )
    code = browser.browser_command(
        tmp_path,
        ["capture", f"{site}/slip.html", "--session", session(), "--ring", "#a"],
    )
    assert code == 1
    assert "no image was kept" in capsys.readouterr().err
    assert not list((tmp_path / ".hard-eng/browser").glob("*.png"))


@pytest.mark.parametrize("start_fails", [False, True])
def test_capture_keeps_no_image_when_the_frame_check_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    browser: ModuleType,
    capsys: pytest.CaptureFixture[str],
    start_fails: bool,
) -> None:
    checks: list[tuple[str, ...]] = []

    def tool(
        name: str, folder: Path, session: str, *arguments: str, text: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        del name, session, text
        if arguments[:1] == ("screenshot",):
            (folder / arguments[-1]).write_bytes(b"image")
        if arguments[:2] == ("eval", browser.FRAME_CHECK):
            checks.append(arguments)
            if len(checks) == 2 and start_fails:
                raise OSError("session closed")
            if len(checks) == 2:
                return subprocess.CompletedProcess(arguments, 1, "", "session closed")
            return subprocess.CompletedProcess(arguments, 0, "0", "")
        reply = json.dumps("[]") if arguments[:1] == ("eval",) else ""
        if arguments[:1] == ("a11y",):
            reply = '{"data": {"violations": []}}'
        return subprocess.CompletedProcess(arguments, 0, reply, "")

    monkeypatch.setattr(browser, "ensure_tool", lambda: "agent-browser")
    monkeypatch.setattr(browser, "run_tool", tool)
    code = browser.browser_command(
        tmp_path, ["capture", "http://x", "--session", session()]
    )
    assert code == 1
    assert "session closed" in capsys.readouterr().err
    assert len(checks) == 2
    assert not list((tmp_path / ".hard-eng/browser").glob("*.png"))


def test_signin_keeps_password_off_command_line(
    tmp_path: Path,
    site: str,
    browser: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = {
        "packages": list[str](),
        "shared": list[str](),
        "browser": {
            "roles": {
                "admin": {
                    "url": f"{site}/login",
                    "username_env": "HE_TEST_USER",
                    "password_env": "HE_TEST_PASSWORD",
                    "env_file": ".env.test",
                }
            }
        },
    }
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    (tmp_path / ".env.test").write_text(f"export HE_TEST_PASSWORD='{SECRET_WORD}'\n")
    monkeypatch.setenv("HE_TEST_USER", "admin@example.com")
    monkeypatch.delenv("HE_TEST_PASSWORD", raising=False)
    arguments: list[list[str]] = []
    run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run

    def spy(command: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        arguments.append(list(command))
        return run(command, **options)

    monkeypatch.setattr(browser.subprocess, "run", spy)
    name = session()
    assert (
        browser.browser_command(tmp_path, ["signin", "admin", "--session", name]) == 0
    )

    state = tmp_path / ".hard-eng/browser/state/admin.json"
    output = capsys.readouterr()
    assert output.out.strip() == str(state)
    assert SECRET_WORD not in output.out + output.err
    assert arguments
    assert not any(SECRET_WORD in part for command in arguments for part in command)
    assert "--password-stdin" in next(
        command for command in arguments if "save" in command
    )
    assert "session-7741" in state.read_text()
    assert SECRET_WORD not in state.read_text()


def test_skills_point_to_the_command() -> None:
    skills = SOURCE / ".agents/skills"
    command = (SOURCE / ".hooks/browser.py").read_text()
    e2e = (skills / "e2e/SKILL.md").read_text()
    followers = {
        "he-ship/references/checks.md": (skills / "he-ship/references/checks.md"),
        "trello-coordinator/references/mockups.md": (
            skills / "trello-coordinator/references/mockups.md"
        ),
    }
    assert "hard-eng.py browser" in e2e
    assert "(references/browser.md)" in e2e
    for name, path in followers.items():
        text = path.read_text()
        assert "e2e/references/browser.md#capture" in text, name
        assert not re.search(r"\b(390|1280)\b", text), name
    assert "WIDTHS = (390, 768, 1280)" in command
    assert "3px solid red" in command


@pytest.mark.parametrize(
    ("runner", "needed", "runs"),
    [
        ("github-hosted", True, 1),
        ("github-hosted", False, 0),
        ("self-hosted", True, 0),
        (None, True, 0),
    ],
)
def test_only_a_hosted_runner_adds_the_sandbox_profile(
    tmp_path: Path, browser: ModuleType, runner: str | None, needed: bool, runs: int
) -> None:
    steps: list[str] = []
    environ = {} if runner is None else {"RUNNER_ENVIRONMENT": runner}
    added = keep_hosted_sandbox(
        environ, lambda: needed, steps.append, tmp_path / "lock"
    )
    assert steps == [browser.root_step()] * runs
    assert added == bool(runs)


def test_a_failed_profile_step_stops_the_tests(tmp_path: Path) -> None:
    def fail(step: str) -> None:
        raise subprocess.CalledProcessError(1, step)

    with pytest.raises(subprocess.CalledProcessError):
        keep_hosted_sandbox(
            {"RUNNER_ENVIRONMENT": "github-hosted"},
            lambda: True,
            fail,
            tmp_path / "lock",
        )
