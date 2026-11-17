"""The one owner of which files `linguist-generated` or `linguist-vendored` marks hide: an exact path with a folder, a fixed generator suffix, or a folder that is a byte copy of a judged package; never a catch-all."""

import re
import shlex
import subprocess
import sys
from pathlib import Path, PurePosixPath

from project_files import GIT_LISTING

GENERATED_KEYS = {"linguist-generated", "linguist-vendored"}
PROOFS: dict[tuple[Path, str], str | None] = {}
INDEXES: dict[Path, dict[str, str]] = {}
PUBSPECS: dict[Path, dict[str, bytes]] = {}
MARKED_PACKAGES: dict[Path, set[str]] = {}
LISTED: dict[Path, tuple[frozenset[str], set[str]]] = {}
GLOB = re.compile(r"[*?\[]")
GENERATOR_SUFFIXES = (".g.dart", ".gr.dart", ".freezed.dart")
NAME_PART = re.compile(r"[\w*-]*")


def mark_kind(pattern: str) -> str | None:
    plain = pattern.strip("/")
    if not GLOB.search(plain):
        return "exact" if "/" in plain else None
    last = plain.split("/")[-1]
    if any(
        last.endswith(suffix) and NAME_PART.fullmatch(last.removesuffix(suffix))
        for suffix in GENERATOR_SUFFIXES
    ):
        return "suffix"
    return "folder" if last == "**" and plain != "**" else None


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


def package_name(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("name:"):
            return line.partition(":")[2].strip() or None
    return None


def reset() -> None:
    PROOFS.clear()
    INDEXES.clear()
    PUBSPECS.clear()
    MARKED_PACKAGES.clear()


def tracked_index(top: Path) -> dict[str, str]:
    """Every tracked path with its blob id, read once from the index so that a file deleted from disk and not staged changes nothing."""
    if top not in INDEXES:
        listed = subprocess.run(
            [*GIT_LISTING, "ls-files", "-s", "-z"],
            cwd=top,
            capture_output=True,
            check=False,
        ).stdout.decode(errors="replace")
        INDEXES[top] = {
            path: meta.split()[1]
            for meta, _, path in (entry.partition("\t") for entry in listed.split("\0"))
            if path
        }
    return INDEXES[top]


def folder_prefix(folder: str) -> str:
    return "" if folder in {"", "."} else folder.rstrip("/") + "/"


def tracked_under(top: Path, folder: str) -> list[str]:
    prefix = folder_prefix(folder)
    return [name for name in tracked_index(top) if name.startswith(prefix)]


def pubspec_texts(top: Path) -> dict[str, bytes]:
    """The committed text of every tracked pubspec.yaml, from one `git cat-file --batch`."""
    if top not in PUBSPECS:
        index = tracked_index(top)
        names = [
            name
            for name in index
            if name == "pubspec.yaml" or name.endswith("/pubspec.yaml")
        ]
        batch = subprocess.run(
            [*GIT_LISTING, "cat-file", "--batch"],
            cwd=top,
            input="".join(f"{index[name]}\n" for name in names).encode(),
            capture_output=True,
            check=False,
        ).stdout
        texts: dict[str, bytes] = {}
        at = 0
        for name in names:
            end = batch.index(b"\n", at)
            size = int(batch[at:end].split()[2])
            texts[name] = batch[end + 1 : end + 1 + size]
            at = end + size + 2
        PUBSPECS[top] = texts
    return PUBSPECS[top]


def marked_packages(top: Path) -> set[str]:
    """The folders of tracked packages that hold a file a mark exempts, from one `git check-attr`."""
    if top not in MARKED_PACKAGES:
        packages = {
            PurePosixPath(name).parent.as_posix() for name in pubspec_texts(top)
        }
        files = [
            name
            for name in tracked_index(top)
            if any(
                folder_prefix(package) == "" or name.startswith(folder_prefix(package))
                for package in packages
            )
        ]
        held = set()
        for name in marked_by_git(top, files, GENERATED_KEYS):
            held.update(
                str(parent)
                for parent in PurePosixPath(name).parents
                if str(parent) in packages
            )
        MARKED_PACKAGES[top] = held
    return MARKED_PACKAGES[top]


def runtime_text(relative: str, data: bytes) -> bytes:
    """The bytes of a file as a deployed copy keeps them: a `pubspec.yaml` without its `dev_dependencies`, which tests need and a function does not ship."""
    if relative == "pubspec.yaml":
        return data.split(b"\ndev_dependencies:", 1)[0].rstrip(b"\r\n") + b"\n"
    return data


def derived_copy(top: Path, folder: str) -> str | None:
    """None when the tracked files under the folder are byte copies of a tracked package of the same pubspec name that no mark exempts (a `pubspec.yaml` is compared without its `dev_dependencies`, and a `pubspec.lock` that the copy adds is pub's own output); otherwise what is wrong, naming the first file that differs. It reads the index, never the disk."""
    index = tracked_index(top)
    pubspecs = pubspec_texts(top)
    prefix = folder_prefix(folder)
    own = pubspecs.get(f"{prefix}pubspec.yaml")
    name = package_name(own.decode(errors="replace")) if own is not None else None
    if name is None:
        return "it holds no pubspec.yaml, so no package is its source"
    sources = [
        PurePosixPath(path).parent.as_posix()
        for path, data in pubspecs.items()
        if not path.startswith(prefix)
        and package_name(data.decode(errors="replace")) == name
        and PurePosixPath(path).parent.as_posix() not in marked_packages(top)
    ]
    if not sources:
        return f"no unmarked tracked package is named {name}"
    first = ""
    for source in sources:
        for path in tracked_under(top, folder):
            relative = path[len(prefix) :]
            there = index.get(folder_prefix(source) + relative)
            if relative == "pubspec.lock":
                continue
            if there is None or (
                there != index[path]
                and (
                    relative != "pubspec.yaml"
                    or runtime_text(
                        relative, pubspecs[folder_prefix(source) + relative]
                    )
                    != runtime_text(relative, pubspecs[path])
                )
            ):
                first = first or f"{path} differs from {source}/{relative}"
                break
        else:
            return None
    return first


def proven_copy(top: Path, folder: str) -> str | None:
    if (top, folder) not in PROOFS:
        PROOFS[top, folder] = derived_copy(top, folder)
    return PROOFS[top, folder]


def folder_of(pattern: str, name: str) -> str | None:
    parts = pattern.strip("/").removesuffix("/**")
    pieces = name.split("/")
    for end in range(1, len(pieces)):
        if regex(parts).fullmatch("/".join(pieces[:end])):
            return "/".join(pieces[:end])
    return None


def hidden_by_exact_marks(root: Path, name: str, keys: set[str]) -> bool:
    top = repository_top(root)
    full = PurePosixPath((root.resolve() / name).relative_to(top).as_posix())
    folder = full.parent
    patterns = [
        (pattern, str(full.relative_to(base)))
        for base in (*reversed(folder.parents), folder)
        for pattern in marks(top / base / ".gitattributes", keys)
    ]
    patterns += [
        (pattern, str(full))
        for pattern in marks(top / ".git" / "info" / "attributes", keys)
    ]
    for pattern, relative in patterns:
        kind = mark_kind(pattern)
        if kind is None or not regex(pattern).fullmatch(relative):
            continue
        if kind != "folder":
            return True
        held = folder_of(pattern, relative)
        prefix = str(full)[: len(str(full)) - len(relative)]
        if held is not None and proven_copy(top, prefix + held) is None:
            return True
    return False


def copy_findings(root: Path) -> list[str]:
    """A folder mark that claims a derived copy whose files differ from their source."""
    top = repository_top(root)
    found = []
    for attributes in [top / ".gitattributes"]:
        for pattern in marks(attributes, GENERATED_KEYS):
            if mark_kind(pattern) != "folder" or GLOB.search(pattern.strip("/")[:-3]):
                continue
            folder = pattern.strip("/").removesuffix("/**")
            reason = proven_copy(top, folder)
            if reason and " differs from " in reason:
                found.append(
                    f".gitattributes marks {folder} as a copy: {reason}; a vendored copy must equal its source, so run the project's sync"
                )
    return found


def marked_by_git(root: Path, names: list[str], keys: set[str]) -> set[str]:
    import tempfile

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
