"""Which generated or vendored marks may hide a file from the switch-off scan: an exact path, a generated-name suffix or a vendor folder, never a catch-all."""

import re
from pathlib import Path, PurePosixPath

from gate_config import GENERATED_KEYS, generated_sources

GLOB = re.compile(r"[*?\[]")
SUFFIX = re.compile(r"[\w*.-]*\.\w+\.\w+")
FOLDER = re.compile(
    r"(?:^|_)(?:shared|vendor|vendored|generated|gen|third_party|node_modules)$"
)


def honoured(pattern: str) -> bool:
    if not GLOB.search(pattern):
        return True
    parts = pattern.strip("/").split("/")
    if SUFFIX.fullmatch(parts[-1]) and not parts[-1].startswith("*.*"):
        return True
    return (
        parts[-1] == "**"
        and len(parts) > 1
        and not GLOB.search(parts[-2])
        and bool(FOLDER.search(parts[-2]))
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


def marks(attribute_file: Path) -> list[str]:
    if not attribute_file.is_file():
        return []
    found = []
    for line in attribute_file.read_text(errors="replace").splitlines():
        words = line.split()
        if len(words) < 2 or words[0].startswith("#"):
            continue
        if any(
            word.split("=")[0] in GENERATED_KEYS and word.split("=")[-1] != "false"
            for word in words[1:]
        ):
            found.append(words[0])
    return found


def hidden_by_exact_marks(root: Path, name: str) -> bool:
    folder = PurePosixPath(name).parent
    for base in (*reversed(folder.parents), folder):
        relative = PurePosixPath(name).relative_to(base)
        for pattern in marks(root / base / ".gitattributes"):
            if honoured(pattern) and regex(pattern).fullmatch(str(relative)):
                return True
    return any(
        honoured(pattern) and regex(pattern).fullmatch(name)
        for pattern in marks(root / ".git" / "info" / "attributes")
    )


def generated_by_exact_marks(root: Path, names: list[str]) -> set[str]:
    return {
        name
        for name in generated_sources(root, names)
        if hidden_by_exact_marks(root, name)
    }
