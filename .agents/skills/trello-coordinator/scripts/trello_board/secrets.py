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


def git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=False
        )
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


def load_secrets(main: Path) -> Secrets:
    if git(main, "check-ignore", "-q", "--", ENV_NAME).returncode != 0:
        raise TrelloError(
            f"Git does not ignore {ENV_NAME} in the main checkout; add it to .gitignore"
        )
    path = main / ENV_NAME
    if not path.is_file():
        raise TrelloError(f"{ENV_NAME} is missing in the main checkout")
    values = parse_env(path.read_text())
    missing = [name for name in NAMES if not values.get(name)]
    if missing:
        raise TrelloError(f"{ENV_NAME} does not set {', '.join(missing)}")
    return Secrets(values["TRELLO_KEY"], values["TRELLO_TOKEN"])
