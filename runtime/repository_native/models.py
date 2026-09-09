"""Small immutable values shared by the launcher modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RepositoryState:
    root: Path
    marked: bool
    marker_digest: str | None
    shared: bool


@dataclass(frozen=True)
class GlobalState:
    mode: str
    root: Path
    identity: str | None
    problems: tuple[str, ...]


@dataclass(frozen=True)
class PreparedState:
    mode: str
    repository: Path
    hard_eng_root: Path | None
    identity: str | None
    wiring: str = "verified"

    def json_value(self) -> dict[str, Any]:
        value = asdict(self)
        value["repository"] = str(self.repository)
        value["hard_eng_root"] = str(self.hard_eng_root) if self.hard_eng_root else None
        return value
