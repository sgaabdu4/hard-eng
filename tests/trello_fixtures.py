import importlib
import json
from pathlib import Path

import pytest
from conftest import commit, init
from trello_fakes import CONFIG, KEY, SCRIPTS, TOKEN, FakeTrello, Mods, Project


def load_mods(monkeypatch: pytest.MonkeyPatch) -> Mods:
    monkeypatch.syspath_prepend(str(SCRIPTS))
    load = importlib.import_module
    return Mods(
        load("trello_board.api"),
        load("trello_board.board"),
        load("trello_board.commands"),
        load("trello_board.config"),
        load("trello_board.report"),
        load("trello_board.state"),
    )


def make_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mods: Mods,
) -> Project:
    main = tmp_path / "main"
    init(main)
    (main / ".gitignore").write_text(".env.trello.local\n")
    (main / "trello.json").write_text(json.dumps(CONFIG))
    (main / ".env.trello.local").write_text(f"TRELLO_KEY={KEY}\nTRELLO_TOKEN={TOKEN}\n")
    commit(main, "fixture")
    fake = FakeTrello(mods.api)
    waits: list[float] = []
    real = mods.api.transport
    monkeypatch.chdir(main)
    monkeypatch.setattr(mods.api, "transport", fake)
    monkeypatch.setattr(mods.api, "pause", waits.append)
    return Project(main, fake, mods, capsys, waits, real)
