"""HE-NO-TEXT-WALLS: run the reader of a screen language; the reader returns the text parts and never counts."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict

from text_reader_programs import JS_READER

HOOKS = Path(__file__).resolve().parent
LIMIT = 120
NEEDS_BUN = (
    "HE-NO-TEXT-WALLS: reading the changed TSX or JSX screens needs Bun. Install Bun, "
    "or in CI add an oven-sh/setup-bun step before the check"
)
INSTALL_FAILED = (
    "HE-NO-TEXT-WALLS: installing the TSX and JSX reader failed: {error}. "
    "Run the check once with network access"
)
READ_FAILED = "HE-NO-TEXT-WALLS: the {kind} reader failed: {error}"


class Block(TypedDict):
    line: int
    lines: list[int]
    kind: str
    name: str
    parts: list[object]
    clamp: int | None
    tap: bool
    user: bool


class FileBlocks(TypedDict):
    path: str
    error: str | None
    blocks: list[Block]


def tool_folder() -> Path:
    from tool_setup import shared_tool_folder

    return shared_tool_folder()


def install_js(staging: Path, environment: dict[str, str]) -> None:
    (staging / "package.json").write_bytes(
        (HOOKS / "text_walls.package.json").read_bytes()
    )
    (staging / "bun.lock").write_bytes((HOOKS / "text_walls.bun.lock").read_bytes())
    (staging / "reader.mjs").write_text(JS_READER)
    done = subprocess.run(
        ["bun", "install", "--frozen-lockfile", "--ignore-scripts"],
        cwd=staging,
        env=environment,
        capture_output=True,
        text=True,
        timeout=LIMIT,
        check=False,
    )
    if done.returncode:
        raise ValueError(INSTALL_FAILED.format(error=done.stderr.strip()))


def js_folder() -> Path:
    """The folder with the installed JavaScript reader, built once for each pin and program."""
    digest = hashlib.sha256()
    for part in (
        (HOOKS / "text_walls.package.json").read_bytes(),
        (HOOKS / "text_walls.bun.lock").read_bytes(),
        JS_READER.encode(),
    ):
        digest.update(hashlib.sha256(part).digest())
    tools = tool_folder()
    root = tools / "text-readers"
    folder = root / f"js-{digest.hexdigest()[:12]}"
    if folder.is_dir():
        return folder
    root.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.setdefault("BUN_INSTALL_CACHE_DIR", str(tools / "bun" / "cache"))
    with (root / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not folder.is_dir():
            staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=root))
            try:
                install_js(staging, environment)
                staging.rename(folder)
            except BaseException:
                shutil.rmtree(staging, ignore_errors=True)
                raise
            for older in root.glob("js-*"):
                if older != folder:
                    shutil.rmtree(older, ignore_errors=True)
    return folder


def read(kind: str, request: dict[str, object]) -> list[FileBlocks]:
    """One reader process reads every file of the request."""
    if kind != "js":
        raise ValueError(READ_FAILED.format(kind=kind, error="no such reader"))
    if shutil.which("bun") is None:
        raise ValueError(NEEDS_BUN)
    folder = js_folder()
    try:
        done = subprocess.run(
            ["bun", str(folder / "reader.mjs")],
            cwd=folder,
            input=json.dumps(request),
            capture_output=True,
            text=True,
            timeout=LIMIT,
            check=True,
        )
        files: list[FileBlocks] = json.loads(done.stdout)["files"]
    except subprocess.CalledProcessError as error:
        raise ValueError(
            READ_FAILED.format(kind="TSX and JSX", error=error.stderr.strip())
        ) from error
    except (subprocess.SubprocessError, OSError, ValueError, KeyError) as error:
        raise ValueError(READ_FAILED.format(kind="TSX and JSX", error=error)) from error
    return files
