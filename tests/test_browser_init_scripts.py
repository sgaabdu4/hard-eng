"""A step that started the page again for its init scripts is refused, and a route's init scripts join every step of its session."""

import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from test_browser import fake_tool


def test_a_step_that_started_the_page_again_for_its_init_scripts_is_refused(
    browser: ModuleType,
) -> None:
    warning = (
        "⚠ init-scripts: /a.js,/b.js → /a.js (--init-script), relaunched browser\n"
    )
    done = subprocess.CompletedProcess([], 0, stdout='"x"', stderr=warning)
    with pytest.raises(ValueError, match="started the page again") as error:
        browser.require(done)
    assert "/a.js,/b.js" in str(error.value)
    fine = subprocess.CompletedProcess([], 0, stdout='"x"', stderr="")
    assert browser.require(fine) == '"x"'


def test_the_init_scripts_of_a_route_join_every_step_of_its_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, browser: ModuleType
) -> None:
    monkeypatch.delenv("AGENT_BROWSER_INIT_SCRIPTS", raising=False)
    folder = browser.output_folder(tmp_path)
    own = tmp_path / "own.js"
    own.write_text("window.x = 1;\n")
    steps, files = browser.split_route_scripts(
        [
            "--session",
            "s1",
            "open",
            "--init-script",
            str(own),
            f"--init-script={own}",
            "http://x",
        ]
    )
    assert steps == ["--session", "s1", "open", "http://x"]
    assert files == [str(own), str(own)]
    browser.keep_route_scripts(folder, "s1", files)
    scripts = browser.checkout_space(folder, "s1")["AGENT_BROWSER_INIT_SCRIPTS"].split(
        ","
    )
    assert scripts[0] == str(own.resolve())
    assert len(scripts) == 2
    assert browser.checkout_space(folder, "s2")[
        "AGENT_BROWSER_INIT_SCRIPTS"
    ] != ",".join(scripts)
    with pytest.raises(ValueError, match="gone.js"):
        browser.keep_route_scripts(folder, "s1", [str(tmp_path / "gone.js")])


def test_a_session_that_the_tool_no_longer_lists_loses_its_saved_init_scripts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, browser: ModuleType
) -> None:
    monkeypatch.delenv("AGENT_BROWSER_INIT_SCRIPTS", raising=False)
    folder = browser.output_folder(tmp_path)
    own = tmp_path / "own.js"
    own.write_text("window.x = 1;\n")
    browser.keep_route_scripts(folder, "s1", [str(own)])
    open_one = fake_tool(
        tmp_path, monkeypatch, 'echo \'{"data":{"sessions":["s1"]}}\'\n'
    )
    browser.limit_sessions(str(open_one), folder, "s1")
    assert browser.route_scripts(folder, "s1") == [str(own.resolve())]
    none_open = fake_tool(tmp_path, monkeypatch, 'echo \'{"data":{"sessions":[]}}\'\n')
    browser.limit_sessions(str(none_open), folder, "s1")
    assert browser.route_scripts(folder, "s1") == []


def test_a_session_opened_outside_the_command_still_reaches_the_request_delay_refusal(
    browser: ModuleType,
) -> None:
    outside = "⚠ init-scripts: default → /hold.js (--init-script), relaunched browser\n"
    done = subprocess.CompletedProcess([], 0, stdout='"x"', stderr=outside)
    assert browser.require(done) == '"x"'
