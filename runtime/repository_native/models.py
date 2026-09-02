"""Small immutable values shared by the launcher modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MarkerPolicy:
    channel: str | None
    minimum_version: str | None
    release_repository: str


@dataclass(frozen=True)
class RepositoryState:
    root: Path
    marked: bool
    marker_digest: str | None
    policy: MarkerPolicy | None


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
    version: str | None
    source_commit: str | None
    channel: str | None
    newest_allowed_version: str | None
    last_check: str
    wiring: str = "verified"

    def json_value(self) -> dict[str, Any]:
        value = asdict(self)
        value["repository"] = str(self.repository)
        value["hard_eng_root"] = str(self.hard_eng_root) if self.hard_eng_root else None
        return value
