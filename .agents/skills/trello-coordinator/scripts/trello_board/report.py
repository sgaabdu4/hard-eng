import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .board import Event, Snapshot
from .config import Config
from .shapes import Obj, parse_time, text

FIELDS = (
    "requests",
    "information",
    "owner",
    "promises",
    "silent",
    "badTags",
    "labels",
    "waitsOnUs",
    "unnumbered",
    "overdue",
)
PROMISE = re.compile(r"\bI will\b|\bI['’]ll\b|\bNext:", re.IGNORECASE)
CONDITION = re.compile(
    r"\b(?:when|once|after|until|before|if)\b[^.!?,;\n]*", re.IGNORECASE
)
FINISHED = re.compile(r"\bis (?:now |already )?(?:live|done)\b", re.IGNORECASE)
WAITS = re.compile(r"next release|not built yet|I am fixing", re.IGNORECASE)
LIVE = re.compile(r"\bis (?:now |already )?live\b", re.IGNORECASE)
TAG = re.compile(r"(?<![\w@])@(\w+)")
QUESTION = re.compile(
    r"\?|\b(please|reply|can you|could you|let me know)\b", re.IGNORECASE
)
NUMBER = re.compile(r"^\s*#(\d+)")
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


def clean(value: str) -> str:
    return " ".join(value.split())[:EXCERPT]


def says(pattern: re.Pattern[str], body: str) -> bool:
    return pattern.search(CONDITION.sub(" ", body)) is not None


def is_own(ctx: Context, event: Event) -> bool:
    return event.author.lower() == ctx.own.lower()


def hours_since(now: datetime, date: str) -> float:
    return (now - parse_time(date)).total_seconds() / 3600


def event_excerpt(event: Event) -> str:
    if event.kind == "image":
        return clean(f"[image] {event.text}")
    return "[description edited]" if event.kind == "desc" else clean(event.text)


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


def requests(ctx: Context, view: View) -> list[Item]:
    event = newest(ctx, view)
    if event and not is_own(ctx, event) and event.author.lower() in ctx.config.allowed:
        return [from_event(view, event)]
    return []


def information(ctx: Context, view: View) -> list[Item]:
    event = newest(ctx, view)
    if (
        event
        and not is_own(ctx, event)
        and event.author.lower() not in ctx.config.allowed
    ):
        return [from_event(view, event)]
    return []


def owner(ctx: Context, view: View) -> list[Item]:
    event = view.after[-1] if view.after else None
    if (
        event
        and event.kind == "comment"
        and is_own(ctx, event)
        and parse_time(event.date) > ctx.first_check
    ):
        return [from_event(view, event)]
    return []


def promises(ctx: Context, view: View) -> list[Item]:
    ours = view.last_ours
    if not ours or view.role == "done" or not PROMISE.search(ours.text):
        return []
    if (
        says(FINISHED, ours.text)
        or hours_since(ctx.now, ours.date) <= ctx.config.promise_hours
    ):
        return []
    return [from_event(view, ours)]


def tags(ctx: Context, view: View) -> set[str]:
    if not view.last_ours or not QUESTION.search(view.last_ours.text):
        return set()
    found = {name.lower() for name in TAG.findall(view.last_ours.text)}
    return found & {name.lower() for name in ctx.snapshot.members.values()}


def label_people(ctx: Context, view: View) -> set[str]:
    return {
        person.lower()
        for person, label in ctx.config.needs.items()
        if label in view.labels
    }


def answered(view: View, person: str) -> bool:
    return any(event.author.lower() == person for event in view.after)


def silent(ctx: Context, view: View) -> list[Item]:
    ours = view.last_ours
    targets = tags(ctx, view) | label_people(ctx, view)
    if not ours or view.role == "done" or not targets or not QUESTION.search(ours.text):
        return []
    if hours_since(ctx.now, ours.date) < ctx.config.chase_hours:
        return []
    if any(answered(view, person) for person in targets):
        return []
    return [from_event(view, ours)]


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
    asked = person.lower() in tags(ctx, view) and not answered(view, person.lower())
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


def unnumbered(ctx: Context, view: View) -> list[Item]:
    if NUMBER.match(view.name):
        return []
    return [item(view, text(view.card.get("dateLastActivity")), "", "")]


def overdue(ctx: Context, view: View) -> list[Item]:
    due = text(view.card.get("due"))
    if not due or view.role == "done" or view.card.get("dueComplete") is True:
        return []
    return [item(view, due, "", "")] if parse_time(due) < ctx.now else []


CHECKS: dict[str, Callable[[Context, View], list[Item]]] = {
    "requests": requests,
    "information": information,
    "owner": owner,
    "promises": promises,
    "silent": silent,
    "badTags": bad_tags,
    "labels": labels,
    "waitsOnUs": waits_on_us,
    "unnumbered": unnumbered,
    "overdue": overdue,
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
    )


def build(ctx: Context) -> dict[str, list[Item]]:
    views = [view_of(ctx, card) for card in ctx.snapshot.cards]
    return {
        field: [i for v in views for i in CHECKS[field](ctx, v)] for field in FIELDS
    }
