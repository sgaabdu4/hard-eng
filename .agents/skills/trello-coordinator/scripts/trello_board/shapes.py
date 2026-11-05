from datetime import UTC, datetime

type Json = str | int | float | bool | None | list[Json] | dict[str, Json]
type Obj = dict[str, Json]


def obj(value: Json) -> Obj:
    return value if isinstance(value, dict) else {}


def objs(value: Json) -> list[Obj]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def text(value: Json) -> str:
    return value if isinstance(value, str) else ""


def parse_time(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def stamp(moment: datetime) -> str:
    return (
        moment.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    )
