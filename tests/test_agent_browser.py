"""The browser-proof judge on controlled outcomes, without running an agent."""

import os
import re
import struct
import zlib
from collections.abc import Callable
from pathlib import Path

import agent_browser
import pytest
from agent_actions import Action
from agent_checks import CASES, Run, fixture
from conftest import git

BLACK = (0, 0, 0)
RED = (255, 0, 0)
CAPTURE_RUN = "python3 .hooks/hard-eng.py browser capture http://127.0.0.1:8123/dashboard --session s1 --ring '#plan-label' --name "
BROWSER_ACTIONS = [
    Action(
        "command", "python3 .hooks/hard-eng.py browser signin viewer --session s1", True
    ),
    Action("command", CAPTURE_RUN + "before", True, ".hard-eng/browser/before-390.png"),
    Action("command", CAPTURE_RUN + "after", True, ".hard-eng/browser/after-390.png"),
]


def paint(
    width: int, boxes: list[tuple[int, int, int, int, tuple[int, int, int]]]
) -> bytes:
    rows = [bytearray(b"\xff" * (width * 3)) for _ in range(320)]
    for left, top, wide, high, color in boxes:
        for y in range(top, top + high):
            for x in range(left, left + wide):
                rows[y][x * 3 : x * 3 + 3] = bytes(color)
    raw = b"".join(b"\0" + bytes(row) for row in rows)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body))
        )

    header = struct.pack(">IIBBBBB", width, 320, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def label_image(
    width: int, version: int, *, ring: bool = True, leaks: tuple[int, ...] = ()
) -> bytes:
    left, top, wide, high = agent_browser.LABEL
    boxes = [(left + 60 + 20 * version, top + 20, 4, 4, BLACK)]
    if ring:
        boxes += [
            (left, top, wide, 3, RED),
            (left, top + high - 3, wide, 3, RED),
            (left, top, 3, high, RED),
            (left + wide - 3, top, 3, high, RED),
        ]
    for line in agent_browser.PERSONAL_LINES.values():
        boxes.append((left, line, 230 if line in leaks else 70, 12, BLACK))
    return paint(width, boxes)


def browser_run(tmp_path: Path) -> Run:
    root = tmp_path / "project"
    base = fixture(root, next(case for case in CASES if case.name == "browser-proof"))
    folder = root / ".hard-eng/browser"
    folder.mkdir(parents=True)
    for width in agent_browser.WIDTHS:
        for version, name in enumerate(("before", "after")):
            (folder / f"{name}-{width}.png").write_bytes(label_image(width, version))
    events = tmp_path / "events.jsonl"
    events.write_text("")
    return Run(root, base, "Done.", [], list(BROWSER_ACTIONS), None, events)


def remove_390(run: Run) -> None:
    for path in (run.root / ".hard-eng/browser").glob("*-390.png"):
        path.unlink()


def repaint(
    name: str, *, ring: bool = True, leaks: tuple[int, ...] = ()
) -> Callable[[Run], None]:
    def change(run: Run) -> None:
        path = run.root / f".hard-eng/browser/{name}.png"
        width = int(name.rpartition("-")[2])
        path.write_bytes(label_image(width, 0, ring=ring, leaks=leaks))

    return change


def only_one_1280(run: Run) -> None:
    repaint("after-1280")(run)
    repaint("before-1280")(run)


def leak_password(run: Run) -> None:
    password = (run.root / ".env.test").read_text().split("APP_PASSWORD=")[1].split()[0]
    leak = Action("command", "cat .env.test", True, f"APP_PASSWORD={password}")
    run.actions.append(leak)


def leak_password_early(run: Run) -> None:
    password = (run.root / ".env.test").read_text().split("APP_PASSWORD=")[1].split()[0]
    assert run.events is not None
    with run.events.open("a") as events:
        events.write(f"APP_PASSWORD={password}\n" + "x" * 3000)


def add_file(run: Run) -> None:
    (run.root / "proof.md").write_text("notes\n")


def run_another_tool(run: Run) -> None:
    run.actions.append(Action("command", "npx playwright screenshot page.png", True))


def plain_screenshot(run: Run) -> None:
    command = "python3 .hooks/hard-eng.py browser --session s1 screenshot x.png"
    run.actions.append(Action("command", command, True))


def drop_a_capture(run: Run) -> None:
    del run.actions[-1]


def leave_a_process(run: Run) -> None:
    del run
    RUNNING.add("99999 agent-browser daemon")


RUNNING: set[str] = set()


@pytest.mark.parametrize(
    ("remove", "reason"),
    [
        (drop_a_capture, "fewer than two successful"),
        (plain_screenshot, "plain screenshot step"),
        (run_another_tool, "another tool"),
        (remove_390, "no image at width 390"),
        (repaint("after-1280", ring=False), "no red ring"),
        (repaint("after-390", leaks=(200,)), "email line"),
        (repaint("after-390", leaks=(240,)), "phone line"),
        (only_one_1280, "fewer than two different images at width 1280"),
        (leak_password, "password appears"),
        (leak_password_early, "password appears"),
        (add_file, "changed or added proof.md"),
        (leave_a_process, "browser process from the run"),
    ],
)
def test_browser_proof_judge_fails_each_missing_item(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    remove: Callable[[Run], None],
    reason: str,
) -> None:
    RUNNING.clear()
    monkeypatch.setattr(agent_browser, "browser_processes", lambda: set(RUNNING))
    run = browser_run(tmp_path)
    assert agent_browser.judge_browser(run) == []
    remove(run)
    failures = agent_browser.judge_browser(run)
    assert len(failures) == 1, failures
    assert reason in failures[0]


@pytest.mark.parametrize(
    ("ring", "relative"), [(True, False), (False, False), (True, True)]
)
def test_judge_reads_images_the_answer_links(
    tmp_path: Path, ring: bool, relative: bool
) -> None:
    RUNNING.clear()
    run = browser_run(tmp_path)
    moved = tmp_path / "proof"
    moved.mkdir()
    for image in sorted((run.root / ".hard-eng/browser").glob("*.png")):
        image.rename(moved / image.name)
    repaint_moved = moved / "after-1280.png"
    repaint_moved.write_bytes(label_image(1280, 1, ring=ring))
    links = " ".join(
        f"[{image.name}]({os.path.relpath(image, run.root) if relative else image})"
        for image in sorted(moved.iterdir())
    )
    failures = agent_browser.judge_browser(run._replace(message=links))
    assert failures == (
        [] if ring else [f"{repaint_moved}: no red ring over the changed label"]
    )


CALLS = [
    "npx playwright screenshot page.png",
    '/opt/homebrew/bin/bash -lc "npx -y @playwright/test install chromium"',
    "pip install playwright",
    "uv pip install selenium",
    'python3 -c "from playwright.sync_api import sync_playwright"',
    "node -e \"require('puppeteer')\"",
    "agent-browser --session s1 open http://127.0.0.1:8123",
    "cd /tmp && /tmp/tools/bin/agent-browser open http://127.0.0.1:8123",
    "/opt/homebrew/bin/bash -lc 'screencapture -x page.png'",
    "chromium --headless --screenshot=page.png http://127.0.0.1:8123",
    "python3 -m playwright screenshot http://127.0.0.1:8123 page.png",
    "python3 - <<'PY'\nimport json\nfrom playwright.sync_api import sync_playwright\nPY",
    'python3 -c "import asyncio; from playwright.sync_api import sync_playwright"',
    r'python3 -c "print(\"starting\"); import playwright"',
]
SEARCHES = [
    "/opt/homebrew/bin/bash -lc \"git status --short && git show --stat --oneline HEAD && git show HEAD -- && rg --files -g 'AGENTS.md' -g 'package.json' -g '*playwright*' -g '*README*' -g '*hard-eng*' -g '\"'!node_modules'\"' -g '\"'!.git'\"'\"",
    "/opt/homebrew/bin/bash -lc \"git status --short; git show --stat --oneline -1; rg --files -g 'AGENTS.md' -g 'package.json' -g '*playwright*' -g 'README*' -g '*requirements*' -g '*test*'\"",
    "pgrep -fl agent-browser",
    "ls ~/.agent-browser",
    "rg -n \"import playwright|require\\('puppeteer'\" src tests",
    'python3 --version\nrg "import playwright" src',
]


@pytest.mark.parametrize(
    ("command", "flagged"),
    [(command, True) for command in CALLS] + [(command, False) for command in SEARCHES],
)
def test_other_tool_check_flags_calls_not_searches(command: str, flagged: bool) -> None:
    failures = agent_browser.command_failures(
        [*BROWSER_ACTIONS, Action("command", command, True)]
    )
    assert bool(failures) == flagged, failures


@pytest.mark.parametrize("feature_map", [False, True])
def test_a_map_run_adds_only_the_committed_feature_map(
    tmp_path: Path, feature_map: bool
) -> None:
    case = next(case for case in CASES if case.name == "browser-proof")
    root = tmp_path / "project"
    base = fixture(root, case, feature_map=feature_map)
    assert (root / "FEATURES.md").exists() == feature_map
    assert git(root, "rev-parse", "HEAD") == base
    assert git(root, "status", "--porcelain") == ""
    assert git(root, "show", "--name-only", "--format=", "HEAD") == "app.py"
    commands = re.findall(
        r"`(python3 \.hooks/hard-eng\.py browser [^`]+)`", case.feature_map
    )
    assert len(commands) == 2
    assert all("--session " in command for command in commands)
    assert all(
        not other.feature_map for other in CASES if other.name != "browser-proof"
    )
