import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .board import QUESTION, TAG, Event, Snapshot, questions_in
from .config import Config
from .shapes import Obj, parse_time, text

FIELDS = (
    "requests",
    "information",
    "owner",
    "promises",
    "silent",
    "buried",
    "badTags",
    "labels",
    "waitsOnUs",
    "testQueue",
    "unnumbered",
    "overdue",
    "realCases",
)
REAL_CASE = "Waiting for real case"
WORKING = r"\b(?:I am (?:fixing|building|changing)|I will fix|being built|waits for the #\d+ fix)\b"
PROMISE = re.compile(rf"\bI will\b|\bI['’]ll\b|\bNext:|{WORKING}", re.IGNORECASE)
CONDITION = re.compile(
    r"\b(?:when|once|after|until|before|if)\b[^.!?,;\n]*", re.IGNORECASE
)
FINISHED = re.compile(
    r"\b(?:(?:is|are) (?:now |already )?(?:live|done)|went live)\b", re.IGNORECASE
)
WAITS = re.compile(rf"next release|not built yet|{WORKING}", re.IGNORECASE)
LIVE = re.compile(r"\b(?:(?:is|are) (?:now |already )?live|went live)\b", re.IGNORECASE)
NUMBER = re.compile(r"^\s*#(\d+)")
ACK_WORD = r"(?:ok(?:ay)?|thanks?(?: you)?|works?|done)"
ACK = re.compile(rf"{ACK_WORD}(?:[\s,.!]+{ACK_WORD})*[\s,.!]*", re.IGNORECASE)
SPECIAL_TAGS = frozenset({"card", "board"})
EXCERPT = 120

type Item = Obj


@dataclass(frozen=True)
class Context:
    config: Config
    snapshot: Snapshot
    posted: set[str]
    own: str
    now: datetime
    first_check: datetime


@dataclass(frozen=True)
class View:
    card: Obj
    ref: str
    name: str
    list: str
    role: str
    labels: frozenset[str]
    last_ours: Event | None
    after: tuple[Event, ...]
    questions: tuple[tuple[Event, str], ...]


def clean(value: str) -> str:
    return " ".join(value.split())[:EXCERPT]


def says(pattern: re.Pattern[str], body: str) -> bool:
    return pattern.search(CONDITION.sub(" ", body)) is not None


def after_finished(body: str) -> str:
    hidden = CONDITION.sub(lambda found: " " * len(found.group()), body)
    ends = [found.end() for found in FINISHED.finditer(hidden)]
    return body[ends[-1] :] if ends else body


def is_own(ctx: Context, event: Event) -> bool:
    return event.author.lower() == ctx.own.lower()


def hours_since(now: datetime, date: str) -> float:
    return (now - parse_time(date)).total_seconds() / 3600


def event_excerpt(event: Event) -> str:
    match event.kind:
        case "image":
            return clean(f"[image] {event.text}")
        case "desc":
            return "[description edited]"
        case "move":
            return clean(f"[moved to {event.text}]")
        case "created":
            return "[made the card]"
    return clean(event.text)


def item(view: View, at: str, author: str, excerpt: str) -> Item:
    card = text(view.card.get("shortLink"))
    return {
        "card": view.ref,
        "name": view.name,
        "list": view.list,
        "url": f"https://trello.com/c/{card}",
        "at": at,
        "author": author,
        "excerpt": excerpt,
    }


def from_event(view: View, event: Event) -> Item:
    return item(view, event.date, event.author, event_excerpt(event))


def in_scope(ctx: Context, view: View) -> bool:
    if view.role != "done":
        return True
    moved = ctx.snapshot.moves.get(text(view.card.get("id")))
    return (
        moved is not None and hours_since(ctx.now, moved) <= ctx.config.done_grace_hours
    )


def newest(ctx: Context, view: View) -> Event | None:
    return view.after[-1] if view.after and in_scope(ctx, view) else None


def may_request(ctx: Context, event: Event) -> bool:
    allowed = ctx.config.allowed
    if allowed is None:
        allowed = frozenset(name.lower() for name in ctx.snapshot.members.values())
    return event.author.lower() in allowed


def thanks(event: Event) -> bool:
    return ACK.fullmatch(TAG.sub("", event.text).strip()) is not None


def requests(ctx: Context, view: View) -> list[Item]:
    event = newest(ctx, view)
    if (
        event
        and not is_own(ctx, event)
        and may_request(ctx, event)
        and not (view.role == "done" and event.kind == "comment" and thanks(event))
    ):
        return [from_event(view, event)]
    return []


def information(ctx: Context, view: View) -> list[Item]:
    event = newest(ctx, view)
    if event and not is_own(ctx, event) and not may_request(ctx, event):
        return [from_event(view, event)]
    return []


def owner(ctx: Context, view: View) -> list[Item]:
    event = view.after[-1] if view.after else None
    if event and is_own(ctx, event) and parse_time(event.date) > ctx.first_check:
        return [from_event(view, event)]
    return []


def promises(ctx: Context, view: View) -> list[Item]:
    ours = view.last_ours
    if not ours or view.role == "done":
        return []
    if not PROMISE.search(after_finished(ours.text)):
        return []
    if hours_since(ctx.now, ours.date) <= ctx.config.promise_hours:
        return []
    return [from_event(view, ours)]


def label_people(ctx: Context, view: View) -> set[str]:
    return {
        person.lower()
        for person, label in ctx.config.needs.items()
        if label in view.labels
    }


def answered(view: View, person: str) -> bool:
    return any(
        event.kind == "comment" and event.author.lower() == person
        for event in view.after
    )


def our_questions(ctx: Context, view: View) -> list[tuple[Event, str]]:
    found = [(e, person) for e, person in view.questions if e.id in ctx.posted]
    ours = view.last_ours
    if ours and QUESTION.search(ours.text):
        found += [
            (ours, person)
            for person in label_people(ctx, view)
            if not answered(view, person)
        ]
    return found


def silent(ctx: Context, view: View) -> list[Item]:
    if view.role == "done":
        return []
    testers = label_people(ctx, view) if view.role == "testing" else set()
    waiting = [e for e, person in our_questions(ctx, view) if person not in testers]
    if not waiting:
        return []
    oldest = min(waiting, key=lambda e: parse_time(e.date))
    if hours_since(ctx.now, oldest.date) < ctx.config.chase_hours:
        return []
    return [from_event(view, oldest)]


def buried(ctx: Context, view: View) -> list[Item]:
    ours = view.last_ours
    if not ours or view.role == "done":
        return []
    tagged = {name.lower() for name in TAG.findall(ours.text)}
    hidden: dict[str, Event] = {}
    for event, person in our_questions(ctx, view):
        if event.id != ours.id and person not in tagged:
            hidden.setdefault(person, event)
    return [
        item(view, event.date, person, clean(event.text))
        for person, event in hidden.items()
    ]


def bad_tags(ctx: Context, view: View) -> list[Item]:
    ours = view.last_ours
    if not ours:
        return []
    known = {name.lower() for name in ctx.snapshot.members.values()} | SPECIAL_TAGS
    return [
        item(view, ours.date, ours.author, f"@{name}")
        for name in dict.fromkeys(TAG.findall(ours.text))
        if name.lower() not in known
    ]


def label_gap(ctx: Context, view: View, person: str, label: str) -> str:
    has = label in view.labels
    asked = person.lower() in {name for _, name in view.questions}
    if has and not asked:
        return f"{label} is set with no open question to @{person}"
    if asked and not has:
        return f"open question to @{person} without the {label} label"
    return ""


def labels(ctx: Context, view: View) -> list[Item]:
    at = (
        view.last_ours.date
        if view.last_ours
        else text(view.card.get("dateLastActivity"))
    )
    gaps = [
        (person, label_gap(ctx, view, person, label))
        for person, label in ctx.config.needs.items()
    ]
    return [item(view, at, person, gap) for person, gap in gaps if gap]


def waits_on_us(ctx: Context, view: View) -> list[Item]:
    ours = view.last_ours
    if not ours or view.role != "testing":
        return []
    if WAITS.search(ours.text) and not says(LIVE, ours.text):
        return [from_event(view, ours)]
    return []


def duplicate_ids(cards: list[Obj]) -> set[str]:
    by_number: dict[str, list[Obj]] = {}
    for card in cards:
        if found := NUMBER.match(text(card.get("name"))):
            by_number.setdefault(found.group(1), []).append(card)
    ids = (text(card.get("id")) for same in by_number.values() for card in same)
    older = {
        min((text(card.get("id")) for card in same), key=lambda i: (len(i), i))
        for same in by_number.values()
    }
    return set(ids) - older


def test_queue(ctx: Context, view: View) -> list[Item]:
    if view.role != "testing":
        return []
    since = ctx.snapshot.moves.get(text(view.card.get("id")))
    at = since or text(view.card.get("dateLastActivity"))
    return [item(view, at, person, "") for person in sorted(label_people(ctx, view))]


def queues(items: list[Item]) -> list[Item]:
    by_person: dict[str, list[Item]] = {}
    for found in items:
        by_person.setdefault(text(found["author"]), []).append(found)
    result: list[Item] = []
    for rows in by_person.values():
        oldest = min(rows, key=lambda row: parse_time(text(row["at"])))
        summary = f"{len(rows)} cards in testing, oldest is #{oldest['card']}"
        result.append({**oldest, "excerpt": summary})
    return result


def unnumbered(ctx: Context, view: View) -> list[Item]:
    at = text(view.card.get("dateLastActivity"))
    if not NUMBER.match(view.name):
        return [item(view, at, "", "")]
    if text(view.card.get("id")) in duplicate_ids(ctx.snapshot.cards):
        return [item(view, at, "", f"another card also has #{view.ref}")]
    return []


def overdue(ctx: Context, view: View) -> list[Item]:
    due = text(view.card.get("due"))
    if not due or view.role == "done" or view.card.get("dueComplete") is True:
        return []
    return [item(view, due, "", "")] if parse_time(due) < ctx.now else []


def real_cases(ctx: Context, view: View) -> list[Item]:
    if view.role == "done" or REAL_CASE not in view.labels:
        return []
    return [item(view, text(view.card.get("dateLastActivity")), "", "")]


CHECKS: dict[str, Callable[[Context, View], list[Item]]] = {
    "requests": requests,
    "information": information,
    "owner": owner,
    "promises": promises,
    "silent": silent,
    "buried": buried,
    "badTags": bad_tags,
    "labels": labels,
    "waitsOnUs": waits_on_us,
    "testQueue": test_queue,
    "unnumbered": unnumbered,
    "overdue": overdue,
    "realCases": real_cases,
}


def view_of(ctx: Context, card: Obj) -> View:
    snapshot = ctx.snapshot
    list_name = snapshot.lists.get(text(card.get("idList")), "")
    roles = {name: role for role, name in ctx.config.lists.items()}
    events = snapshot.threads.get(text(card.get("id")), [])
    marks = [
        i for i, e in enumerate(events) if e.kind == "comment" and e.id in ctx.posted
    ]
    last = marks[-1] if marks else -1
    name = text(card.get("name"))
    number = NUMBER.match(name)
    label_ids = card.get("idLabels")
    people = frozenset(person.lower() for person in snapshot.members.values())
    names = (
        {snapshot.labels.get(text(i), "") for i in label_ids}
        if isinstance(label_ids, list)
        else set()
    )
    return View(
        card,
        number.group(1) if number else text(card.get("shortLink")),
        name,
        list_name,
        roles.get(list_name, ""),
        frozenset(names),
        events[last] if last >= 0 else None,
        tuple(events[last + 1 :]),
        tuple((e, person) for _, e, person in questions_in(events, people)),
    )


def build(ctx: Context) -> dict[str, list[Item]]:
    views = [view_of(ctx, card) for card in ctx.snapshot.cards]
    found = {
        field: [i for v in views for i in CHECKS[field](ctx, v)] for field in FIELDS
    }
    found["testQueue"] = queues(found["testQueue"])
    return found
