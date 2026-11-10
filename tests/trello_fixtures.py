import dataclasses
import importlib
import json
from pathlib import Path
from types import ModuleType

import pytest
from conftest import add_origin, commit, git, init
from trello_fakes import CONFIG, KEY, SCRIPTS, TOKEN, FakeTrello, Mods, Project

CLAIM_REF = "refs/trello-coordinator/claim"


def load_claim() -> ModuleType:
    return importlib.import_module("trello_board.claim")


def origin_of(project: Project) -> Path:
    return project.main.parent / "origin.git"


def drop_claim(*projects: Project) -> None:
    git(origin_of(projects[0]), "update-ref", "-d", CLAIM_REF)
    for project in projects:
        (project.state / "claim-record").unlink(missing_ok=True)


def second_machine(project: Project, name: str = "second") -> Project:
    clone = project.main.parent / name
    git(project.main, "clone", "-q", str(origin_of(project)), str(clone))
    git(clone, "config", "user.name", "Repo Owner")
    git(clone, "config", "user.email", "owner@example.invalid")
    (clone / ".env.trello.local").write_text(
        f"TRELLO_KEY={KEY}\nTRELLO_TOKEN={TOKEN}\n"
    )
    return dataclasses.replace(project, main=clone, run_id="")


def enter(monkeypatch: pytest.MonkeyPatch, project: Project) -> Project:
    monkeypatch.chdir(project.main)
    return project


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
    add_origin(main)
    place = importlib.import_module("trello_board.secrets").locate(main)
    assert load_claim().hold(place, mods.api.Secrets(KEY, TOKEN)) is None
    fake = FakeTrello(mods.api)
    waits: list[float] = []
    real = mods.api.transport
    monkeypatch.chdir(main)
    monkeypatch.setattr(mods.api, "transport", fake)
    monkeypatch.setattr(mods.api, "pause", waits.append)
    return Project(main, fake, mods, capsys, waits, real)
