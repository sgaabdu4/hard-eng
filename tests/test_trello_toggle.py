"""The Trello member and label commands add or remove one id on a card and change nothing when it is already so."""

import argparse
import re
import sys
from pathlib import Path

import pytest
from conftest import SOURCE

sys.path.insert(0, str(SOURCE / ".agents/skills/trello-coordinator/scripts"))

from trello_board import board, commands
from trello_board.api import Client, Secrets
from trello_board.config import Config
from trello_board.secrets import Place
from trello_board.shapes import Obj, obj, text


def session() -> commands.Session:
    config = Config(
        board="b1",
        account="me",
        allowed=None,
        lists={},
        needs={},
        every_minutes=1.0,
        chase_hours=1.0,
        promise_hours=1.0,
        done_grace_hours=1.0,
        privacy=(re.compile("x"),),
    )
    place = Place(Path("."), Path("."), Path("."))
    client = Client(Secrets("k", "t"), dry_run=True)
    return commands.Session(client, config, place, "me")


CASES = [
    ("member", "idMembers", "m1", {"username": "@Ann"}),
    ("label", "idLabels", "l1", {"label": "bug"}),
]


@pytest.mark.parametrize(("command", "field", "ident", "extra"), CASES)
@pytest.mark.parametrize(
    ("action", "present", "calls"),
    [
        ("add", False, [("POST", "/cards/c1/{field}")]),
        ("add", True, []),
        ("remove", True, [("DELETE", "/cards/c1/{field}/{ident}")]),
        ("remove", False, []),
    ],
)
def test_a_card_id_toggles_only_when_it_changes(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    field: str,
    ident: str,
    extra: dict[str, str],
    action: str,
    present: bool,
    calls: list[tuple[str, str]],
) -> None:
    card: Obj = {"id": "c1", field: [ident] if present else []}

    def members(_session: commands.Session) -> dict[str, str]:
        return {"ann": "m1"}

    def names(_client: Client, _board: str, _kind: str, _key: str) -> dict[str, str]:
        return {"l1": "bug"}

    def found(_session: commands.Session, _ref: str) -> Obj:
        return card

    monkeypatch.setattr(commands, "member_ids", members)
    monkeypatch.setattr(board, "fetch_names", names)
    monkeypatch.setattr(commands, "resolve_card", found)
    args = argparse.Namespace(card="c1", action=action, **extra)
    current = session()
    result = getattr(commands, command)(current, args)
    sent = [
        (text(obj(item).get("method")), text(obj(item).get("path")))
        for item in current.client.planned
    ]
    assert sent == [
        (method, path.format(field=field, ident=ident)) for method, path in calls
    ]
    assert ("unchanged" in result) is (not calls)
