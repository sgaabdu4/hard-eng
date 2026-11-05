import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .api import TrelloError
from .shapes import Json, Obj, obj

FIELDS = (
    "board",
    "account",
    "allowed",
    "lists",
    "needsLabels",
    "timing",
    "roles",
    "privacy",
)
REQUIRED_LISTS = ("todo", "doing", "testing", "done")
OPTIONAL_LISTS = ("urgent", "discuss")
REQUIRED_ROLES = ("coordinator", "builder", "planner", "reviewer", "lookup")
OPTIONAL_ROLES = ("computerUse",)
ROLE_FIELDS = ("model", "why", "provider")
TIMING_HOURS = {
    "everyMinutes": 15,
    "chaseHours": 24,
    "promiseHours": 6,
    "doneGraceHours": 72,
}
TIMING_FIELDS = (*TIMING_HOURS, "quietHours", "timeZone")
QUIET = re.compile(r"^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$")
SECRET = re.compile(r"\b(?:[0-9a-f]{32,}|ATTA[0-9A-Za-z]{20,})\b", re.IGNORECASE)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE = re.compile(r"(?<![\w#])\+?\d(?:[\s().-]?\d){8,}(?![\d:])")


@dataclass(frozen=True)
class Config:
    board: str
    account: str
    allowed: frozenset[str]
    lists: dict[str, str]
    needs: dict[str, str]
    every_minutes: float
    chase_hours: float
    promise_hours: float
    done_grace_hours: float
    privacy: tuple[re.Pattern[str], ...]

    def refuse_private(self, body: str) -> None:
        if EMAIL.search(body):
            raise TrelloError("The comment holds an email address")
        if PHONE.search(body):
            raise TrelloError("The comment holds a phone number")
        if any(pattern.search(body) for pattern in self.privacy):
            raise TrelloError("The comment matches a privacy pattern in trello.json")


def strings_in(value: Json) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from strings_in(item)


def name_field(data: Obj, name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise TrelloError(f"trello.json: {name} must be a nonempty string")
    return value


def string_map(value: Json, name: str, keys: tuple[str, ...] = ()) -> dict[str, str]:
    if not isinstance(value, dict) or not all(
        isinstance(v, str) and v for v in value.values()
    ):
        raise TrelloError(f"trello.json: {name} must map names to nonempty strings")
    unknown: list[str] = sorted(set(value) - set(keys)) if keys else []
    if unknown:
        raise TrelloError(f"trello.json: unknown {name} entry: {', '.join(unknown)}")
    return {k: v for k, v in value.items() if isinstance(v, str)}


def check_lists(lists: dict[str, str]) -> None:
    missing = [role for role in REQUIRED_LISTS if role not in lists]
    if missing:
        raise TrelloError(f"trello.json: lists is missing {', '.join(missing)}")


def check_roles(value: Json) -> None:
    roles = obj(value)
    missing = [role for role in REQUIRED_ROLES if role not in roles]
    unknown = sorted(set(roles) - {*REQUIRED_ROLES, *OPTIONAL_ROLES})
    if not isinstance(value, dict) or missing or unknown:
        raise TrelloError(f"trello.json: roles needs {', '.join(REQUIRED_ROLES)}")
    for role, entry in roles.items():
        fields = obj(entry)
        bad = [
            k
            for k in ("model", "why")
            if not isinstance(fields.get(k), str) or not fields[k]
        ]
        if (
            bad
            or set(fields) - set(ROLE_FIELDS)
            or not isinstance(fields.get("provider", ""), str)
        ):
            raise TrelloError(
                f"trello.json: roles.{role} needs model and why, optional provider"
            )


def timing_value(timing: Obj, name: str) -> float:
    value = timing.get(name, TIMING_HOURS[name])
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise TrelloError(f"trello.json: timing.{name} must be a positive number")
    return float(value)


def check_timing(value: Json) -> dict[str, float]:
    timing = obj(value)
    unknown = sorted(set(timing) - set(TIMING_FIELDS))
    if not isinstance(value, (dict, type(None))) or unknown:
        raise TrelloError(f"trello.json: timing takes only {', '.join(TIMING_FIELDS)}")
    quiet = timing.get("quietHours")
    if quiet is not None and not (isinstance(quiet, str) and QUIET.match(quiet)):
        raise TrelloError('trello.json: timing.quietHours must look like "22:00-07:00"')
    try:
        ZoneInfo(str(timing.get("timeZone", "UTC")))
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise TrelloError("trello.json: timing.timeZone is not an IANA name") from error
    return {name: timing_value(timing, name) for name in TIMING_HOURS}


def compile_privacy(value: Json) -> tuple[re.Pattern[str], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TrelloError("trello.json: privacy must be a list of regex strings")
    try:
        return tuple(re.compile(item) for item in value if isinstance(item, str))
    except re.error as error:
        raise TrelloError(f"trello.json: privacy holds a bad regex: {error}") from error


def read_json(path: Path) -> Obj:
    if not path.is_file():
        raise TrelloError("trello.json is missing at the repository root")
    try:
        data = json.loads(path.read_text())
    except ValueError as error:
        raise TrelloError("trello.json is not valid JSON") from error
    if not isinstance(data, dict):
        raise TrelloError("trello.json must hold an object")
    return data


def load_config(root: Path) -> Config:
    data = read_json(root / "trello.json")
    if any(SECRET.search(item) for item in strings_in(data)):
        raise TrelloError("trello.json holds a value that looks like a key or token")
    unknown = sorted(set(data) - set(FIELDS))
    if unknown:
        raise TrelloError(f"trello.json: unknown field: {', '.join(unknown)}")
    lists = string_map(data.get("lists"), "lists", (*REQUIRED_LISTS, *OPTIONAL_LISTS))
    check_lists(lists)
    check_roles(data.get("roles"))
    hours = check_timing(data.get("timing"))
    allowed = data.get("allowed")
    if not isinstance(allowed, list) or not all(isinstance(n, str) for n in allowed):
        raise TrelloError("trello.json: allowed must be a list of usernames")
    return Config(
        board=name_field(data, "board"),
        account=name_field(data, "account"),
        allowed=frozenset(n.lower() for n in allowed if isinstance(n, str)),
        lists=lists,
        needs=string_map(data.get("needsLabels", {}), "needsLabels"),
        every_minutes=hours["everyMinutes"],
        chase_hours=hours["chaseHours"],
        promise_hours=hours["promiseHours"],
        done_grace_hours=hours["doneGraceHours"],
        privacy=compile_privacy(data.get("privacy")),
    )
