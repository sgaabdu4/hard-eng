import json
import os
import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

from .api import Secrets, TrelloError
from .secrets import Place, git
from .shapes import Obj, obj, stamp, text
from .state import lease_is_live, lease_lock, utc_now, write_atomic

REF = "refs/trello-coordinator/claim"
MEMORY_SUFFIXES = (".md", ".log", ".json")
MACHINE_FILE = "machine"
RECORD_FILE = "claim-record"
HOLDER_FILE = "holder"
SECONDS = 60
NO_PROMPT = {"GIT_TERMINAL_PROMPT": "0"}
IDENTITY = {
    "GIT_AUTHOR_NAME": "trello-coordinator",
    "GIT_AUTHOR_EMAIL": "trello-coordinator@invalid",
    "GIT_COMMITTER_NAME": "trello-coordinator",
    "GIT_COMMITTER_EMAIL": "trello-coordinator@invalid",
}
GITHUB = re.compile(r"https://github\.com/([^/\s]+/[^/\s]+?)(?:\.git)?/?")
NOT_HELD = (
    "This machine does not hold the coordinator claim; "
    "the user must order takeover here to move it"
)


@dataclass(frozen=True)
class Record:
    sha: str
    since: str


def load_record(state: Path) -> Record | None:
    try:
        saved = obj(json.loads((state / RECORD_FILE).read_text()))
    except (OSError, ValueError):
        return None
    sha = text(saved.get("sha"))
    return Record(sha, text(saved.get("since"))) if sha else None


def write_record(state: Path, record: Record) -> None:
    saved = {"sha": record.sha, "since": record.since}
    write_atomic(state / RECORD_FILE, json.dumps(saved))


def machine_id(state: Path) -> str:
    path = state / MACHINE_FILE
    with lease_lock(state):
        try:
            found = path.read_text().strip()
        except OSError:
            found = ""
        if not found:
            found = uuid.uuid4().hex
            write_atomic(path, found)
        return found


def is_memory_name(name: str) -> bool:
    return name.endswith(MEMORY_SUFFIXES)


def memory_files(state: Path) -> list[Path]:
    if not state.is_dir():
        return []
    return sorted(
        path
        for path in state.iterdir()
        if path.is_file() and not path.is_symlink() and is_memory_name(path.name)
    )


def refuse_keys(files: list[Path], secrets: Secrets) -> None:
    values = [value for value in (secrets.key, secrets.token) if value]
    for path in files:
        content = path.read_text(errors="replace")
        if any(value in content for value in values):
            raise TrelloError(f"{path.name} holds a key or token; no memory was sent")


def network(place: Place, *arguments: str) -> subprocess.CompletedProcess[str]:
    return git(place.main, *arguments, timeout=SECONDS, env=NO_PROMPT)


def plumbing(
    place: Place,
    *arguments: str,
    stdin: str | None = None,
    env: dict[str, str] | None = None,
) -> str:
    done = git(place.main, *arguments, stdin=stdin, env=env)
    if done.returncode:
        raise TrelloError("git could not build or read the claim commit")
    return done.stdout


def is_private(place: Place) -> bool:
    url = git(place.main, "remote", "get-url", "origin").stdout.strip()
    found = GITHUB.fullmatch(url)
    if not found:
        return False
    command = ["gh", "repo", "view", found.group(1), "--json", "visibility"]
    try:
        answer = subprocess.run(
            [*command, "-q", ".visibility"],
            cwd=place.main,
            capture_output=True,
            text=True,
            check=False,
            timeout=SECONDS,
            env={**os.environ, "GH_PROMPT_DISABLED": "1"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return answer.returncode == 0 and answer.stdout.strip() == "PRIVATE"


def remote_sha(place: Place) -> str:
    found = network(place, "ls-remote", "origin", REF)
    if found.returncode:
        raise TrelloError("origin could not be reached")
    words = found.stdout.split()
    return words[0] if words else ""


def fetch_commit(place: Place, sha: str) -> None:
    def present() -> bool:
        return git(place.main, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0

    if present():
        return
    network(place, "fetch", "--no-tags", "origin", REF)
    if not present():
        raise TrelloError("The claim could not be read from origin; run it again")


def holder_of(place: Place, sha: str) -> Obj:
    fetch_commit(place, sha)
    shown = git(place.main, "cat-file", "blob", f"{sha}:{HOLDER_FILE}")
    try:
        return obj(json.loads(shown.stdout))
    except ValueError:
        return {}


def shared_memory(place: Place) -> list[Path]:
    return memory_files(place.state) if is_private(place) else []


def build_tree(
    place: Place, secrets: Secrets, me: str, since: str, memory: list[Path]
) -> str:
    refuse_keys(memory, secrets)
    holder = json.dumps({"machine": me, "since": since})
    rows = [
        (HOLDER_FILE, plumbing(place, "hash-object", "-w", "--stdin", stdin=holder))
    ]
    for path in memory:
        stored = plumbing(place, "hash-object", "-w", "--no-filters", "--", str(path))
        rows.append((path.name, stored))
    listing = "".join(f"100644 blob {sha.strip()}\t{name}\n" for name, sha in rows)
    return plumbing(place, "mktree", stdin=listing).strip()


def push(place: Place, sha: str, expected: str) -> bool:
    lease = f"--force-with-lease={REF}:{expected}"
    done = network(place, "push", "--no-verify", lease, "origin", f"{sha}:{REF}")
    return done.returncode == 0


def publish(place: Place, tree: str, since: str, expected: str) -> bool:
    message = f"Coordinator claim since {since}"
    options = ("-c", "commit.gpgsign=false", "commit-tree", tree, "-m", message)
    sha = plumbing(place, *options, env=IDENTITY).strip()
    if not push(place, sha, expected):
        return False
    write_record(place.state, Record(sha, since))
    return True


def rejected(place: Place, expected: str) -> TrelloError:
    if remote_sha(place) == expected:
        return TrelloError("origin refused the claim push")
    return TrelloError("Another machine holds the coordinator claim now")


def take(place: Place, secrets: Secrets, expected: str) -> bool:
    since = stamp(utc_now())
    memory = shared_memory(place)
    tree = build_tree(place, secrets, machine_id(place.state), since, memory)
    return publish(place, tree, since, expected)


def hold(place: Place, secrets: Secrets) -> Obj | None:
    remote = remote_sha(place)
    record = load_record(place.state)
    if remote and record and record.sha == remote:
        return None
    if not remote:
        if take(place, secrets, ""):
            return None
        remote = remote_sha(place)
        if not remote:
            raise TrelloError("The coordinator claim could not be taken")
    holder = holder_of(place, remote)
    since = text(holder.get("since"))
    if text(holder.get("machine")) == machine_id(place.state):
        write_record(place.state, Record(remote, since))
        return None
    return {"skipped": True, "heldElsewhere": True, "heldSince": since}


def require(place: Place) -> None:
    record = load_record(place.state)
    if record is None or remote_sha(place) != record.sha:
        raise TrelloError(NOT_HELD)


def save(place: Place, secrets: Secrets) -> None:
    record = load_record(place.state)
    memory = shared_memory(place) if record else []
    if record is None or not memory:
        return
    tree = build_tree(place, secrets, machine_id(place.state), record.since, memory)
    saved = git(place.main, "rev-parse", "--verify", "-q", f"{record.sha}^{{tree}}")
    if saved.stdout.strip() == tree:
        return
    if not publish(place, tree, record.since, record.sha):
        raise rejected(place, record.sha)


def restore(place: Place, sha: str) -> bool:
    rows = [
        row.partition("\t") for row in plumbing(place, "ls-tree", "-z", sha).split("\0")
    ]
    kept = {
        name: meta.split()[2]
        for meta, _, name in rows
        if name and meta.split()[1] == "blob" and is_memory_name(name)
    }
    if not kept:
        return False
    for old in memory_files(place.state):
        old.unlink()
    for name, blob in kept.items():
        write_atomic(place.state / name, plumbing(place, "cat-file", "blob", blob))
    return True


def takeover(place: Place, secrets: Secrets, every_minutes: float) -> Obj:
    me = machine_id(place.state)
    with lease_lock(place.state):
        if lease_is_live(place.state, every_minutes):
            raise TrelloError("A run is going on this machine; take over after it ends")
        remote = remote_sha(place)
        previous = saved = ""
        restored = False
        if remote:
            previous = text(holder_of(place, remote).get("since"))
            saved = plumbing(place, "log", "-1", "--format=%cI", remote).strip()
            restored = restore(place, remote)
        since = stamp(utc_now())
        tree = build_tree(place, secrets, me, since, shared_memory(place))
        if not publish(place, tree, since, remote):
            raise rejected(place, remote)
    return {
        "tookOver": True,
        "previousSince": previous,
        "previousSaved": saved,
        "memoryRestored": restored,
    }
