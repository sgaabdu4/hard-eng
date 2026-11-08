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


def checklist(*items: tuple[str, str, str]) -> list[Data]:
    rows = [{"id": i, "name": n, "state": st} for i, n, st in items]
    return [{"id": "cl1", "name": "Steps", "checkItems": rows}]


def move_action(
    ident: str,
    card: int,
    list_id: str,
    hours: float,
    who: str = "m-owner",
    name: str = "Done",
) -> Data:
    before = {"id": "l-before", "name": "Before"}
    after = {"id": list_id, "name": name}
    return make_action(
        ident, "updateCard", card, who, hours, listBefore=before, listAfter=after
    )


def create_action(ident: str, card: int, who: str, hours: float) -> Data:
    action = make_action(ident, "createCard", card, who, hours)
    data = action["data"]
    assert isinstance(data, dict)
    data["card"] = {
        "id": f"card{card}",
        "name": "x",
        "idShort": card,
        "shortLink": f"sl{card}",
    }
    data["list"] = {"id": "l-todo", "name": "To do"}
    return action


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
    checklists: dict[str, list[Data]] = field(default_factory=dict)
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
        if method == "POST" and path == f"{board}/labels":
            return {"id": self.new_id("lb-new")}
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
            return self.create(form)
        if method == "POST" and path.endswith("/attachments"):
            ident = self.new_id("att")
            return {"id": ident, "url": f"https://files.example.test/{ident}.png"}
        if method == "POST" and path.endswith("/actions/comments"):
            return self.reply(path, form["text"])
        if method == "GET" and path.endswith("/attachments"):
            return self.attachments
        return self.card_answer(method, path, query, form)

    def card_answer(
        self, method: str, path: str, query: dict[str, str], form: dict[str, str]
    ) -> object:
        detail = re.fullmatch(r"/cards/([\w-]+)", path)
        if method == "GET" and detail:
            card = next(c for c in self.cards if c["id"] == detail.group(1))
            return card | {"desc": self.descriptions.get(detail.group(1), "")}
        if method == "PUT" and detail and "idList" in form:
            self.moved(detail.group(1), form["idList"])
        lists = re.fullmatch(r"/cards/([\w-]+)/checklists", path)
        if method == "GET" and lists:
            return self.checklists.get(lists.group(1), [])
        thread = re.fullmatch(r"/cards/([\w-]+)/actions", path)
        if method == "GET" and thread:
            kinds = query.get("filter", "commentCard").split(",")
            own = [
                a
                for a in self.actions
                if card_id(a) == thread[1]
                and any(str(a["type"]) == k.split(":")[0] for k in kinds)
            ]
            return self.page(own, query)
        return dict[str, object]()

    def create(self, form: dict[str, str]) -> Data:
        ident = self.new_id("card")
        self.cards.append(
            make_card(0, form["name"], form["idList"], id=ident, shortLink=ident)
        )
        number = len(self.cards)
        action = make_action(
            self.new_id("act"), "createCard", 0, "m-owner", -0.03, list=form["idList"]
        )
        data = action["data"]
        assert isinstance(data, dict)
        data["card"] = {"id": ident, "name": form["name"], "idShort": number}
        self.actions.append(action)
        return {"id": ident, "shortUrl": f"https://trello.com/c/{ident}"}

    def moved(self, ident: str, list_id: str) -> None:
        card = next(c for c in self.cards if c["id"] == ident)
        before = {"id": card["idList"], "name": "Before"}
        card["idList"] = list_id
        action = make_action(
            self.new_id("act"),
            "updateCard",
            0,
            "m-owner",
            -0.03,
            listBefore=before,
            listAfter={"id": list_id, "name": "After"},
        )
        data = action["data"]
        assert isinstance(data, dict)
        data["card"] = {"id": ident, "name": str(card["name"])}
        self.actions.append(action)

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
