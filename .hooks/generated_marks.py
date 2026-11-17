"""The one owner of which files `linguist-generated` or `linguist-vendored` marks hide: an exact path with a folder, or a fixed generator suffix, never a catch-all."""

import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from project_files import GIT_LISTING

GENERATED_KEYS = {"linguist-generated", "linguist-vendored"}
LISTED: dict[Path, tuple[frozenset[str], set[str]]] = {}
GLOB = re.compile(r"[*?\[]")
GENERATOR_SUFFIXES = (".g.dart", ".gr.dart", ".freezed.dart")
NAME_PART = re.compile(r"[\w*-]*")


def honoured(pattern: str) -> bool:
    plain = pattern.strip("/")
    if not GLOB.search(plain):
        return "/" in plain
    last = plain.split("/")[-1]
    return any(
        last.endswith(suffix) and NAME_PART.fullmatch(last.removesuffix(suffix))
        for suffix in GENERATOR_SUFFIXES
    )


def regex(pattern: str) -> re.Pattern[str]:
    anchored = "/" in pattern.strip("/")
    text = ""
    parts = pattern.strip("/").split("/")
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        if part == "**":
            text += ".*" if last else "(?:.*/)?"
            continue
        text += re.escape(part).replace(r"\*", "[^/]*").replace(r"\?", "[^/]") + (
            "" if last else "/"
        )
    return re.compile(text if anchored else f"(?:.*/)?{text}")


def marks(attribute_file: Path, keys: set[str]) -> list[str]:
    if not attribute_file.is_file():
        return []
    found = []
    for line in attribute_file.read_text(errors="replace").splitlines():
        try:
            words = shlex.split(line, comments=True)
        except ValueError:
            words = line.split()
        if len(words) < 2:
            continue
        if any(
            word.split("=")[0] in keys and word.split("=")[-1] != "false"
            for word in words[1:]
        ):
            found.append(words[0])
    return found


def repository_top(root: Path) -> Path:
    folder = root.resolve()
    return next(
        (parent for parent in (folder, *folder.parents) if (parent / ".git").exists()),
        folder,
    )


def hidden_by_exact_marks(root: Path, name: str, keys: set[str]) -> bool:
    top = repository_top(root)
    full = PurePosixPath((root.resolve() / name).relative_to(top).as_posix())
    folder = full.parent
    for base in (*reversed(folder.parents), folder):
        relative = full.relative_to(base)
        for pattern in marks(top / base / ".gitattributes", keys):
            if honoured(pattern) and regex(pattern).fullmatch(str(relative)):
                return True
    return any(
        honoured(pattern) and regex(pattern).fullmatch(str(full))
        for pattern in marks(top / ".git" / "info" / "attributes", keys)
    )


def marked_by_git(root: Path, names: list[str], keys: set[str]) -> set[str]:
    # A live stdin pipe deadlocked against git's per-path output on macOS (issue 375).
    with tempfile.TemporaryFile() as paths:
        paths.write(("\0".join(names) + "\0").encode())
        paths.seek(0)
        listed = subprocess.run(
            [*GIT_LISTING, "check-attr", "-z", "--all", "--stdin"],
            cwd=root,
            capture_output=True,
            text=True,
            stdin=paths,
            check=False,
        )
    if listed.returncode:
        repository = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if repository.returncode:
            return set()  # Standalone source directories have no Git attributes.
        sys.stderr.write(listed.stderr)
        listed.check_returncode()
    attributes = listed.stdout.split("\0")
    return {
        name
        for name, key, value in zip(attributes[::3], attributes[1::3], attributes[2::3])
        if key in keys and value in {"set", "true"}
    }


def generated_sources(
    root: Path, names: list[str], generated_only: bool = False
) -> set[str]:
    if not names:
        return set()
    listed, generated = LISTED.get(root, (frozenset(), set()))
    if listed.issuperset(names) and not generated_only:
        return generated.intersection(names)
    keys = {"linguist-generated"} if generated_only else GENERATED_KEYS
    return {
        name
        for name in marked_by_git(root, names, keys)
        if hidden_by_exact_marks(root, name, keys)
    }
