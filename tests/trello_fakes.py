import json
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import SOURCE

SKILL = SOURCE / ".agents/skills/trello-coordinator"
SCRIPTS = SKILL / "scripts"
BOARD = "bd123"
KEY = "fake-key"
TOKEN = "fake-token"
ROLES = ("coordinator", "builder", "planner", "reviewer", "lookup")
CONFIG: dict[str, object] = {
    "board": BOARD,
    "account": "owner",
    "allowed": ["sam"],
    "lists": {"todo": "To do", "doing": "Doing", "testing": "Testing", "done": "Done"},
    "needsLabels": {"sam": "Needs Sam"},
    "roles": {role: {"model": "model-x", "why": "fits the job"} for role in ROLES},
}
type Data = dict[str, object]


def ago(hours: float) -> str:
    moment = datetime.now(UTC) - timedelta(hours=hours)
    return moment.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_card(number: int, name: str, list_id: str, **extra: object) -> Data:
    base: Data = {
        "id": f"card{number}",
        "idList": list_id,
        "name": name,
        "due": None,
        "dueComplete": False,
        "idLabels": [],
        "idMembers": [],
        "shortLink": f"sl{number}",
        "dateLastActivity": ago(1),
    }
    return base | extra


def make_action(
    ident: str, kind: str, card: int, who: str, hours: float, **data: object
) -> Data:
    return {
        "id": ident,
        "type": kind,
        "date": ago(hours),
        "idMemberCreator": who,
        "data": {"card": {"id": f"card{card}", "name": "x"}, **data},
    }


def card_id(action: Data) -> str:
    data = action["data"]
    assert isinstance(data, dict)
    card = data["card"]
    assert isinstance(card, dict)
    return str(card["id"])


def comment(ident: str, card: int, who: str, text: str, hours: float) -> Data:
    return make_action(ident, "commentCard", card, who, hours, text=text)


def move_action(ident: str, card: int, list_id: str, hours: float) -> Data:
    after = {"id": list_id, "name": "Done"}
    return make_action(ident, "updateCard", card, "m-owner", hours, listAfter=after)


@dataclass(frozen=True)
class Call:
    method: str
    path: str
    query: dict[str, str]
    form: dict[str, str]
    auth: str


@dataclass(frozen=True)
class Mods:
    api: ModuleType
    board: ModuleType
    commands: ModuleType
    config: ModuleType
    report: ModuleType
    state: ModuleType


@dataclass
class FakeTrello:
    api: ModuleType
    account: str = "owner"
    ignore_before: bool = False
    cards: list[Data] = field(default_factory=list)
    actions: list[Data] = field(default_factory=list)
    attachments: list[Data] = field(default_factory=list)
    descriptions: dict[str, str] = field(default_factory=dict)
    rejections: list[tuple[int, dict[str, str], str]] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    members: list[Data] = field(
        default_factory=lambda: [
            {"id": "m-owner", "username": "owner"},
            {"id": "m-sam", "username": "sam"},
            {"id": "m-pat", "username": "pat"},
        ]
    )
    lists: list[Data] = field(
        default_factory=lambda: [
            {"id": "l-todo", "name": "To do"},
            {"id": "l-doing", "name": "Doing"},
            {"id": "l-testing", "name": "Testing"},
            {"id": "l-done", "name": "Done"},
        ]
    )
    labels: list[Data] = field(
        default_factory=lambda: [{"id": "lb-sam", "name": "Needs Sam"}]
    )

    @property
    def writes(self) -> list[Call]:
        return [call for call in self.calls if call.method != "GET"]

    def new_id(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]}"

    def __call__(self, request: urllib.request.Request) -> object:
        parts = urlsplit(request.full_url)
        path = parts.path.removeprefix("/1")
        query = {k: v[0] for k, v in parse_qs(parts.query).items()}
        form: dict[str, str] = {}
        if isinstance(request.data, bytes):
            if request.get_header("Content-type", "").startswith("multipart/"):
                form = {"multipart": "yes"}
            else:
                form = {k: v[0] for k, v in parse_qs(request.data.decode()).items()}
        method = request.get_method()
        self.calls.append(
            Call(method, path, query, form, request.get_header("Authorization", ""))
        )
        if self.rejections:
            status, headers, body = self.rejections.pop(0)
            return self.api.Reply(status, headers, body.encode())
        if "/download/" in path:
            return self.api.Reply(200, {}, b"png-bytes")
        reply = json.dumps(self.answer(method, path, query, form)).encode()
        return self.api.Reply(200, {}, reply)

    def answer(
        self, method: str, path: str, query: dict[str, str], form: dict[str, str]
    ) -> object:
        board = f"/boards/{BOARD}"
        lookup: dict[str, object] = {
            "/members/me": {"username": self.account},
            board: {"name": "Fixture board", "shortLink": BOARD},
            f"{board}/members": self.members,
            f"{board}/lists": self.lists,
            f"{board}/labels": self.labels,
            f"{board}/cards/open": self.cards,
            f"{board}/cards/all": self.cards,
            f"{board}/actions": self.page(self.actions, query),
        }
        if path in lookup:
            return lookup[path]
        if method == "POST" and path == "/cards":
            ident = self.new_id("card")
            return {"id": ident, "shortUrl": f"https://trello.com/c/{ident}"}
        if method == "POST" and path.endswith("/attachments"):
            ident = self.new_id("att")
            return {"id": ident, "url": f"https://files.example.test/{ident}.png"}
        if method == "POST" and path.endswith("/actions/comments"):
            return self.reply(path, form["text"])
        if method == "GET" and path.endswith("/attachments"):
            return self.attachments
        return self.card_answer(method, path, query)

    def card_answer(self, method: str, path: str, query: dict[str, str]) -> object:
        detail = re.fullmatch(r"/cards/(card\d+)", path)
        if method == "GET" and detail:
            card = next(c for c in self.cards if c["id"] == detail.group(1))
            return card | {"desc": self.descriptions.get(detail.group(1), "")}
        thread = re.fullmatch(r"/cards/(card\d+)/actions", path)
        if method == "GET" and thread:
            own = [
                a
                for a in self.actions
                if a["type"] == "commentCard" and card_id(a) == thread[1]
            ]
            return self.page(own, query)
        return dict[str, object]()

    def reply(self, path: str, text: str) -> Data:
        ident = self.new_id("act")
        card = int(path.split("/")[2].removeprefix("card"))
        self.actions.append(comment(ident, card, "m-owner", text, -0.03))
        return {"id": ident}

    def page(self, items: list[Data], query: dict[str, str]) -> list[Data]:
        since = query.get("since", "")
        found = [a for a in items if not since or str(a["date"]) > since]
        found.sort(key=lambda a: str(a["date"]), reverse=True)
        if query.get("before") and not self.ignore_before:
            ids = [str(a["id"]) for a in found]
            found = found[ids.index(query["before"]) + 1 :]
        return found[: int(query["limit"])] if "limit" in query else found


@dataclass(frozen=True)
class Result:
    code: int
    payload: dict[str, object]
    text: str


@dataclass
class Project:
    main: Path
    fake: FakeTrello
    mods: Mods
    capsys: pytest.CaptureFixture[str]
    waits: list[float]
    real_transport: Callable[..., object]
    run_id: str = ""

    @property
    def state(self) -> Path:
        return self.main.resolve() / ".git/trello-coordinator"

    def run(self, *argv: str) -> Result:
        code = self.mods.commands.main(list(argv))
        captured = self.capsys.readouterr()
        payload = json.loads(captured.out)
        self.run_id = str(payload.get("runId", self.run_id))
        return Result(code, payload, captured.out + captured.err)

    def finish(self) -> Result:
        return self.run("finish", self.run_id)

    def configure(self, **changes: object) -> None:
        (self.main / "trello.json").write_text(json.dumps(CONFIG | changes))

    def report(self) -> dict[str, list[dict[str, str]]]:
        result = self.run("check")
        assert result.code == 0, result.text
        found: dict[str, list[dict[str, str]]] = {}
        for name, items in result.payload.items():
            if name == "runId":
                continue
            assert isinstance(items, list)
            found[name] = [{k: str(v) for k, v in item.items()} for item in items]
        return found


def refs(items: list[dict[str, str]]) -> set[str]:
    return {item["card"] for item in items}


def write_lease(project: Project, run_id: str, minutes_ago: float) -> None:
    started = project.mods.state.stamp(
        datetime.now(UTC) - timedelta(minutes=minutes_ago)
    )
    lease = {"runId": run_id, "startedAt": started}
    (project.state / "lease").write_text(json.dumps(lease))


def lease_owner(project: Project) -> str:
    return str(json.loads((project.state / "lease").read_text())["runId"])
