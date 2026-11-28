import json
from pathlib import Path
from types import ModuleType

import pytest
from test_browser import decode, page, plain_step, session
from test_look import (
    first_prompt,
    good_answer,
    install_agent,
    look_project,
    make_images,
    prompt_text,
    run_look,
)

project = pytest.fixture(look_project)


def test_a_capture_record_holds_the_image_and_screen_height(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        "tall.html",
        "<style>body{margin:0;height:1600px}</style><p>Tall</p>",
    )
    name = session()
    plain_step(tmp_path, name, "set", "viewport", "768", "700")
    plain_step(tmp_path, name, "open", f"{site}/tall.html")
    code = browser.browser_command(
        tmp_path, ["measure", "--session", name, "--name", "tall"]
    )
    plain_step(tmp_path, name, "close")
    assert code == 0
    folder = tmp_path / ".hard-eng/browser"
    record = json.loads((folder / "tall-768.json").read_text())
    assert record["viewport_height"] == 700
    assert record["image_height"] == decode(folder / "tall-768.png")[1] >= 1600


def test_the_prompt_gives_the_reviewer_each_image_and_screen_height(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    images, log, prompt = first_prompt(tmp_path, project)
    assert "Capture notes" not in prompt
    ui_measure.write_record(
        project,
        images[0],
        390,
        [],
        "/kpi",
        image_height=2400,
        viewport_height=900,
    )
    run_look(project, "codex", images)
    prompt = prompt_text(log)
    assert "image-1.png: 2400 px tall, screen 900 px" in prompt
    assert "image-2.png:" not in prompt.partition("Capture notes")[2]


def test_a_capture_record_holds_the_steps_taken_on_the_page(
    tmp_path: Path, site: str, browser: ModuleType
) -> None:
    page(
        tmp_path,
        "menu.html",
        "<button id=open>Open</button><input id=agree type=checkbox>",
    )
    name = session()
    plain_step(tmp_path, name, "open", f"{site}/menu.html")
    plain_step(tmp_path, name, "click", "#open")
    plain_step(tmp_path, name, "check", "#agree")
    code = browser.browser_command(
        tmp_path, ["measure", "--session", name, "--name", "menu"]
    )
    plain_step(tmp_path, name, "close")
    assert code == 0
    folder = tmp_path / ".hard-eng/browser"
    record = json.loads((folder / "menu-1280.json").read_text())
    assert record["steps"] == ["click", "check"]
    assert (
        browser.browser_command(
            tmp_path,
            ["capture", f"{site}/menu.html", "--session", name, "--name", "fresh"],
        )
        == 0
    )
    assert "steps" not in json.loads((folder / "fresh-390.json").read_text())


def test_the_prompt_names_the_steps_that_led_to_a_changed_image(
    tmp_path: Path, project: Path
) -> None:
    import ui_measure

    images = make_images(project, 2)
    ui_measure.write_record(
        project,
        images[0],
        390,
        [],
        "/kpi",
        image_height=900,
        viewport_height=900,
        steps=["click", "check"],
    )
    ui_measure.write_record(
        project, images[1], 390, [], "/kpi", image_height=900, viewport_height=900
    )
    log = install_agent(tmp_path, "claude", 2, good_answer(2))
    run_look(project, "codex", images)
    notes = prompt_text(log).partition("Capture notes")[2]
    assert "image-1.png: 900 px tall, screen 900 px, after click, check" in notes
    assert "image-2.png: 900 px tall, screen 900 px\n" in notes + "\n"
