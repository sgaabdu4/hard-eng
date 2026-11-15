import functools
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import zlib
from collections.abc import Callable, Generator
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


@pytest.fixture
def site(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[str]:
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
def browser(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setenv("PATH", os.environ["PATH"])
    import browser as module

    return module


def page(tmp_path: Path, name: str, body: str) -> None:
    (tmp_path / "pages" / name).write_text(f"<!doctype html><body>{body}</body>")


def session() -> str:
    return "test-" + uuid.uuid4().hex[:8]


def open_sessions(tool: str) -> str:
    return subprocess.run(
        [tool, "session", "list"], capture_output=True, text=True, check=False
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


def is_red(rows: list[bytes], step: int, x: int, y: int) -> bool:
    red, green, blue = rows[y][x * step : x * step + 3]
    return red > 200 and green < 60 and blue < 60


def test_installs_like_other_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, browser: ModuleType
) -> None:
    import tool_setup

    tool = tmp_path / "agent-browser"
    log = tmp_path / "log"
    tool.write_text(f'#!/bin/sh\necho "$@" >> {log}\n')
    tool.chmod(0o755)
    calls: list[tuple[list[str], bool | None]] = []
    broken: list[bool] = []

    def provision(
        batch: list[str], timeout: float, offline: bool | None = None
    ) -> None:
        del timeout
        calls.append((batch, offline))
        if broken and not offline:
            raise ValueError("offline")

    monkeypatch.setattr(tool_setup, "provision_batch", provision)
    monkeypatch.setattr(tool_setup, "shared_tool_folder", lambda: tmp_path / "shared")

    def which(name: str) -> str:
        del name
        return str(tool)

    monkeypatch.setattr(browser.shutil, "which", which)
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
        done = subprocess.run(
            [
                sys.executable,
                "-c",
                PLAIN_STEP,
                str(tmp_path),
                "--session",
                name,
                *arguments,
            ],
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONPATH": str(SOURCE / ".hooks")},
        )
        assert done.returncode == 0, done.stderr
        return done.stdout

    try:
        step("open", f"{site}/oops.html")
        step("wait", "--load", "networkidle")
        assert "console-boom" in step("console")
        assert "page-oops" in step("errors")
        step("screenshot", "shot.png")
    finally:
        step("close")
    assert (tmp_path / ".hard-eng/browser/shot.png").is_file()


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
    assert name not in open_sessions(browser.ensure_tool())


def test_capture_draws_boxes_at_both_widths(
    tmp_path: Path, site: str, browser: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    page(
        tmp_path,
        "boxes.html",
        "<style>body{margin:0;height:1600px}div{position:absolute;background:#def}</style>"
        "<div id=a style='left:20px;top:40px;width:100px;height:60px'></div>"
        "<div id=b style='left:30px;top:1100px;width:150px;height:80px'></div>",
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
        str(folder / "boxes-1280.png"),
    ]
    for width in (390, 1280):
        image_width, height, rows, step = decode(folder / f"boxes-{width}.png")
        assert image_width == width
        assert height >= 1600
        for left, top, wide, high in ((20, 40, 100, 60), (30, 1100, 150, 80)):
            assert is_red(rows, step, left + 1, top + high // 2)
            assert is_red(rows, step, left + wide // 2, top + 1)
            assert is_red(rows, step, left + wide - 2, top + high // 2)
            assert not is_red(rows, step, left + wide // 2, top + high // 2)
    assert name not in open_sessions(browser.ensure_tool())


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
        "#side{top:0;bottom:0;right:auto;width:30px;background:#c8c800}</style>"
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
        _, height, rows, step = decode(tmp_path / f".hard-eng/browser/bars-{width}.png")
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
    for name, path in followers.items():
        text = path.read_text()
        assert "e2e/SKILL.md#drive-a-browser" in text, name
        assert not re.search(r"\b(390|1280)\b", text), name
    assert "WIDTHS = (390, 1280)" in command
    assert "3px solid red" in command
