import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .api import Secrets, TrelloError

ENV_NAME = ".env.trello.local"
STATE_FOLDER = "trello-coordinator"
NAMES = ("TRELLO_KEY", "TRELLO_TOKEN")


@dataclass(frozen=True)
class Place:
    root: Path
    main: Path
    state: Path


def git(
    cwd: Path,
    *arguments: str,
    timeout: float | None = None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env={**os.environ, **env} if env else None,
            input=stdin,
        )
    except subprocess.TimeoutExpired as error:
        raise TrelloError("git did not answer in time") from error
    except OSError as error:
        raise TrelloError("git could not run") from error


def locate(cwd: Path) -> Place:
    root = git(cwd, "rev-parse", "--show-toplevel")
    common = git(cwd, "rev-parse", "--git-common-dir")
    if root.returncode or common.returncode:
        raise TrelloError("The current folder is not inside a git repository")
    shared = (cwd / common.stdout.strip()).resolve()
    return Place(Path(root.stdout.strip()), shared.parent, shared / STATE_FOLDER)


def parse_env(content: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.splitlines():
        line = line.strip().removeprefix("export ")
        name, separator, value = line.partition("=")
        if separator and not line.startswith("#"):
            values[name.strip()] = value.strip().strip("'\"")
    return values


def require_ignored(main: Path) -> None:
    if git(main, "check-ignore", "-q", "--", ENV_NAME).returncode != 0:
        raise TrelloError(
            f"Git does not ignore {ENV_NAME} in the main checkout; add it to .gitignore"
        )


def ignore_locally(place: Place) -> None:
    if git(place.main, "check-ignore", "-q", "--", ENV_NAME).returncode == 0:
        return
    if git(place.main, "ls-files", "--error-unmatch", "--", ENV_NAME).returncode == 0:
        raise TrelloError(f"Git tracks {ENV_NAME}; remove it from git first")
    exclude = place.state.parent / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    before = exclude.read_text() if exclude.is_file() else ""
    joined = before if not before or before.endswith("\n") else before + "\n"
    exclude.write_text(f"{joined}{ENV_NAME}\n")


def save_secret(place: Place, name: str, source: Path) -> str:
    ignore_locally(place)
    require_ignored(place.main)
    try:
        value = source.read_text().strip()
    except OSError as error:
        raise TrelloError(
            f"The file with the pasted {name} could not be read"
        ) from error
    if not value or any(character.isspace() for character in value):
        raise TrelloError(f"The pasted {name} is empty or has spaces in it")
    path = place.main / ENV_NAME
    lines = path.read_text().splitlines() if path.is_file() else []
    kept = [line for line in lines if name not in parse_env(line)]
    place.state.mkdir(parents=True, exist_ok=True)
    temporary = place.state / f"{ENV_NAME}.new"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("\n".join([*kept, f"{name}={value}"]) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return name


def load_secrets(main: Path) -> Secrets:
    require_ignored(main)
    path = main / ENV_NAME
    if not path.is_file():
        raise TrelloError(f"{ENV_NAME} is missing in the main checkout")
    values = parse_env(path.read_text())
    missing = [name for name in NAMES if not values.get(name)]
    if missing:
        raise TrelloError(f"{ENV_NAME} does not set {', '.join(missing)}")
    return Secrets(values["TRELLO_KEY"], values["TRELLO_TOKEN"])
