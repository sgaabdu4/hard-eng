import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .board import QUESTION, TAG, Event, Snapshot, questions_in
from .config import Config
from .shapes import Obj, parse_time, stamp, text

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
    "idle",
)
REAL_CASE = "Waiting for real case"
OPEN_WORK = frozenset({"todo", "doing", "urgent"})
TRELLO_ID = re.compile(r"[0-9a-f]{24}")
TOUCHES = frozenset({"comment", "move", "created"})
WORKING = r"\b(?:I am (?:fixing|building|changing)|I will fix|being built|waits for the #\d+ fix)\b"
INTENT = (
    r"\bI(?: am|['’]m) (?:fixing|building|changing|adding|checking|making|watching|writing|looking"
    r"|testing|updating|sending|posting|going to)\b"
    r"|\bI (?:check|post|make|fix|send|add|update|tell|share|reply|look|watch|test)\b"
    r"|\bbeing (?:built|fixed)\b"
)
PROMISE = re.compile(
    rf"\bI will\b|\bI['’]ll\b|\bNext:|{WORKING}|{INTENT}", re.IGNORECASE
)
CONDITION = re.compile(
    r"\b(?:when|once|after|until|before|if)\b[^.!?\n]*|[^.!?\n,;]*\?",
    re.IGNORECASE,
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
    owed: frozenset[str]


def clean(value: str) -> str:
    return " ".join(value.split())[:EXCERPT]


def plain(body: str) -> str:
    return CONDITION.sub(lambda found: " " * len(found.group()), body)


def says(pattern: re.Pattern[str], body: str) -> bool:
    return pattern.search(plain(body)) is not None


def after_finished(body: str) -> str:
    hidden = plain(body)
    ends = [found.end() for found in FINISHED.finditer(hidden)]
    return hidden[ends[-1] :] if ends else hidden


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


def promise_due(ctx: Context, view: View) -> datetime | None:
    ours = view.last_ours
    if not ours or view.role == "done" or not PROMISE.search(after_finished(ours.text)):
        return None
    return parse_time(ours.date) + timedelta(hours=ctx.config.promise_hours)


def promises(ctx: Context, view: View) -> list[Item]:
    due = promise_due(ctx, view)
    if due is None or view.last_ours is None or ctx.now <= due:
        return []
    return [from_event(view, view.last_ours)]


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


def oldest_unanswered(ctx: Context, view: View) -> Event | None:
    if view.role == "done":
        return None
    testers = label_people(ctx, view) if view.role == "testing" else set()
    newest: dict[str, Event] = {}
    for event, person in our_questions(ctx, view):
        known = newest.get(person)
        if person not in testers and (
            known is None or parse_time(event.date) > parse_time(known.date)
        ):
            newest[person] = event
    return min(newest.values(), key=lambda e: parse_time(e.date)) if newest else None


def silent(ctx: Context, view: View) -> list[Item]:
    oldest = oldest_unanswered(ctx, view)
    if oldest is None or hours_since(ctx.now, oldest.date) < ctx.config.chase_hours:
        return []
    return [from_event(view, oldest)]


def buried(ctx: Context, view: View) -> list[Item]:
    ours = view.last_ours
    if not ours or view.role == "done":
        return []
    tagged = {name.lower() for name in TAG.findall(ours.text)}
    testers = label_people(ctx, view) if view.role == "testing" else set()
    hidden: dict[str, Event] = {}
    for event, person in our_questions(ctx, view):
        if event.id != ours.id and person not in tagged | testers:
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
    asked = asked or (view.role == "testing" and person.lower() in view.owed)
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
    if says(WAITS, ours.text) and not says(LIVE, ours.text):
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


def card_due(view: View) -> str:
    due = text(view.card.get("due"))
    if not due or view.role == "done" or view.card.get("dueComplete") is True:
        return ""
    return due


def overdue(ctx: Context, view: View) -> list[Item]:
    due = card_due(view)
    return [item(view, due, "", "")] if due and parse_time(due) < ctx.now else []


def real_cases(ctx: Context, view: View) -> list[Item]:
    if view.role == "done" or REAL_CASE not in view.labels:
        return []
    return [item(view, text(view.card.get("dateLastActivity")), "", "")]


def last_touch(ctx: Context, view: View) -> str:
    card = text(view.card.get("id"))
    events = ctx.snapshot.threads.get(card, [])
    dates = [e.date for e in events if e.kind in TOUCHES]
    if moved := ctx.snapshot.moves.get(card):
        dates.append(moved)
    if TRELLO_ID.fullmatch(card):
        dates.append(stamp(datetime.fromtimestamp(int(card[:8], 16), UTC)))
    if not dates:
        return text(view.card.get("dateLastActivity"))
    return max(dates, key=parse_time)


def idle(ctx: Context, view: View) -> list[Item]:
    if view.role not in OPEN_WORK:
        return []
    at = last_touch(ctx, view)
    hours = hours_since(ctx.now, at)
    if hours <= ctx.config.chase_hours:
        return []
    excerpt = f"{hours:.0f} hours in {view.list} with no comment or move"
    return [item(view, at, "", excerpt)]


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
    "idle": idle,
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
    found = questions_in(events, people, ctx.posted)
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
        tuple((e, p) for _, e, p in found if QUESTION.search(e.text)),
        frozenset(p for _, e, p in found if e.id in ctx.posted),
    )


def build(ctx: Context) -> dict[str, list[Item]]:
    views = [view_of(ctx, card) for card in ctx.snapshot.cards]
    found = {
        field: [i for v in views for i in CHECKS[field](ctx, v)] for field in FIELDS
    }
    found["testQueue"] = queues(found["testQueue"])
    return found
