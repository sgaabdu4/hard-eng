import fcntl
import json
import os
import tempfile
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .shapes import Obj, obj, parse_time, stamp, text


def utc_now() -> datetime:
    return datetime.now(UTC)


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(handle, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def load_state(directory: Path) -> Obj:
    try:
        return obj(json.loads((directory / "state.json").read_text()))
    except (OSError, ValueError):
        return {}


def save_state(directory: Path, state: Obj) -> None:
    write_atomic(directory / "state.json", json.dumps(state, indent=2))


def posted_ids(directory: Path) -> set[str]:
    try:
        return set((directory / "posted.log").read_text().split())
    except OSError:
        return set()


def log_posted(directory: Path, action_id: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "posted.log").open("a") as log:
        log.write(action_id + "\n")


@contextmanager
def lease_lock(directory: Path) -> Generator[None]:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "lease.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def lease_holder(directory: Path) -> tuple[str, datetime] | None:
    try:
        held = obj(json.loads((directory / "lease").read_text()))
        return text(held["runId"]), parse_time(text(held["startedAt"]))
    except (OSError, ValueError, KeyError):
        return None


def take_lease(directory: Path, every_minutes: float) -> str | None:
    with lease_lock(directory):
        now = utc_now()
        held = lease_holder(directory)
        if held and now - held[1] < timedelta(minutes=2 * every_minutes):
            return None
        run_id = uuid.uuid4().hex
        lease = {"runId": run_id, "startedAt": stamp(now)}
        write_atomic(directory / "lease", json.dumps(lease))
        return run_id


def end_lease(directory: Path, run_id: str) -> bool:
    with lease_lock(directory):
        held = lease_holder(directory)
        if held is None or held[0] != run_id:
            return False
        (directory / "lease").unlink(missing_ok=True)
        return True
