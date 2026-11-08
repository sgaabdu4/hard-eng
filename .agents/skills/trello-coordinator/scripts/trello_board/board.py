import re
from dataclasses import asdict, dataclass, replace

from .api import Client, TrelloError, redact
from .config import Config
from .shapes import Json, Obj, obj, objs, parse_time, text

CARD_FIELDS = (
    "idList,name,due,dueComplete,idLabels,idMembers,shortLink,dateLastActivity"
)
PAGE = 1000
TAG = re.compile(r"(?<![\w@])@(\w+)")
QUESTION = re.compile(
    r"\?|\b(please|reply|can you|could you|let me know)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Event:
    id: str
    card: str
    kind: str
    date: str
    author: str
    text: str


@dataclass
class Snapshot:
    cards: list[Obj]
    lists: dict[str, str]
    labels: dict[str, str]
    members: dict[str, str]
    threads: dict[str, list[Event]]
    moves: dict[str, str]


def questions_in(
    events: list[Event], members: frozenset[str]
) -> list[tuple[int, Event, str]]:
    found: list[tuple[int, Event, str]] = []
    for index, event in enumerate(events):
        if event.kind != "comment" or not QUESTION.search(event.text):
            continue
        asked = {name.lower() for name in TAG.findall(event.text)} & members
        for person in sorted(asked - {event.author.lower()}):
            replied = any(
                e.kind == "comment" and e.author.lower() == person
                for e in events[index + 1 :]
            )
            if not replied:
                found.append((index, event, person))
    return found


def fetch_cards(client: Client, board: str) -> list[Obj]:
    return objs(
        client.request("GET", f"/boards/{board}/cards/open", {"fields": CARD_FIELDS})
    )


def fetch_names(client: Client, board: str, kind: str, name: str) -> dict[str, str]:
    rows = objs(client.request("GET", f"/boards/{board}/{kind}", {"fields": name}))
    return {text(row.get("id")): text(row.get(name)) for row in rows}


def paged(client: Client, path: str, params: dict[str, str]) -> list[Obj]:
    found: list[Obj] = []
    before = ""
    while True:
        query = {**params, "limit": str(PAGE)}
        if before:
            query["before"] = before
        page = objs(client.request("GET", path, query))
        found += page
        if len(page) < PAGE:
            return found
        last = text(page[-1].get("id"))
        if not last or last == before:
            raise TrelloError("Trello paging did not advance")
        before = last


def board_actions(client: Client, board: str, since: str) -> list[Obj]:
    params = {"filter": "all"}
    if since:
        params["since"] = since
    return paged(client, f"/boards/{board}/actions", params)


def updated(data: Obj) -> tuple[str, str]:
    if "desc" in obj(data.get("old")):
        return "desc", ""
    if "listAfter" in data:
        return "move", text(obj(data["listAfter"]).get("name"))
    return "", ""


def describe(kind: str, data: Obj) -> tuple[str, str]:
    match kind:
        case "commentCard":
            return "comment", text(data.get("text"))
        case "createCard":
            return "created", ""
        case "addAttachmentToCard":
            return "image", text(obj(data.get("attachment")).get("name"))
        case "updateCard":
            return updated(data)
    return "", ""


def to_event(action: Obj, members: dict[str, str]) -> Event | None:
    data = obj(action.get("data"))
    card = text(obj(data.get("card")).get("id"))
    kind, body = describe(text(action.get("type")), data)
    if not card or not kind:
        return None
    creator = text(action.get("idMemberCreator"))
    edited = text(data.get("dateLastEdited")) if kind == "comment" else ""
    return Event(
        text(action.get("id")),
        card,
        kind,
        edited or text(action.get("date")),
        members.get(creator, creator),
        body,
    )


def event_from(row: Obj) -> Event:
    return Event(
        text(row.get("id")),
        text(row.get("card")),
        text(row.get("kind")),
        text(row.get("date")),
        text(row.get("author")),
        text(row.get("text")),
    )


def threads_from(saved: Json) -> dict[str, list[Event]]:
    return {
        card: [event_from(row) for row in objs(rows)]
        for card, rows in obj(saved).items()
    }


def threads_to(threads: dict[str, list[Event]]) -> Obj:
    return {
        card: [dict(asdict(event)) for event in events]
        for card, events in threads.items()
    }


def merge_threads(
    saved: dict[str, list[Event]],
    fresh: list[Event],
    own: str,
    posted: set[str],
    members: frozenset[str],
) -> dict[str, list[Event]]:
    def ours(event: Event) -> bool:
        return (
            event.kind == "comment"
            and event.author.lower() == own.lower()
            and event.id in posted
        )

    def kept(event: Event) -> bool:
        if event.kind == "comment" or event.author.lower() != own.lower():
            return True
        return event.kind in ("move", "created") and event.id not in posted

    by_card: dict[str, dict[str, Event]] = {}
    for event in [e for events in saved.values() for e in events] + fresh:
        if kept(event):
            by_card.setdefault(event.card, {})[event.id] = event
    merged: dict[str, list[Event]] = {}
    for card, found in by_card.items():
        ordered = sorted(found.values(), key=lambda e: parse_time(e.date))
        last = max((i for i, e in enumerate(ordered) if ours(e)), default=0)
        oldest = min((i for i, _, _ in questions_in(ordered, members)), default=last)
        merged[card] = ordered[min(last, oldest) :]
    return merged


def merge_moves(saved: Json, fresh: list[Event]) -> dict[str, str]:
    moves = {card: text(date) for card, date in obj(saved).items()}
    for event in fresh:
        known = moves.get(event.card)
        if event.kind == "move" and (
            known is None or parse_time(event.date) > parse_time(known)
        ):
            moves[event.card] = event.date
    return moves


def fetch(
    client: Client, config: Config, own: str, posted: set[str], saved: Obj
) -> Snapshot:
    board = config.board
    members = fetch_names(client, board, "members", "username")
    cards = fetch_cards(client, board)
    lists = fetch_names(client, board, "lists", "name")
    labels = fetch_names(client, board, "labels", "name")
    since = text(saved.get("checkedAt"))
    fresh = [
        replace(e, text=redact(e.text, client.secrets))
        for a in board_actions(client, board, since)
        if (e := to_event(a, members))
    ]
    open_ids = {text(card.get("id")) for card in cards}
    people = frozenset(name.lower() for name in members.values())
    threads = merge_threads(
        threads_from(saved.get("threads")), fresh, own, posted, people
    )
    return Snapshot(
        cards,
        lists,
        labels,
        members,
        {card: events for card, events in threads.items() if card in open_ids},
        merge_moves(saved.get("moves"), fresh),
    )
