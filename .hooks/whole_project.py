"""The full check judges every tracked file with the patterns of the changed-file checks, old code included."""

import re
import subprocess
import tomllib
from pathlib import Path, PurePosixPath

from comments import (
    HASH,
    SLASH,
    UNOWNED,
    comment_map,
    pattern_switch_offs,
    security_hits,
    switch_off_refusal,
)
from gate_config import generated_sources
from project_files import GIT_LISTING

LINE_IGNORES = {".gitleaksignore", ".semgrepignore"}
MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
MARKDOWN_NAME = re.compile(r"[\w.+-]+\.md\b")
NEEDS_NO_LINK = {
    "README",
    "AGENTS",
    "AGENTS.override",
    "PRODUCT",
    "DESIGN",
    "SECURITY",
    "CHANGELOG",
    "PLAN",
    "DECISION",
    "SKILL",
}
NEEDS_NO_LINK_FOLDERS = ("docs/adr/", *UNOWNED)


def tracked_files(root: Path) -> list[str]:
    listed = subprocess.check_output(
        [*GIT_LISTING, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
    )
    return sorted(
        {
            name
            for name in listed.split("\0")
            if name and (root / name).is_file() and not (root / name).is_symlink()
        }
    )


def gitleaks_allowlists(name: str, text: str) -> list[str]:
    """Allowlist entries of a Gitleaks config; its detection rules stay."""
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    found = [
        f"{name} holds an allowlist table {key!r}"
        for key in ("allowlist", "allowlists")
        if key in config
    ]
    found += [
        f"{name} holds an allowlist in rule {rule.get('id', '?')!r}"
        for rule in config.get("rules", [])
        if "allowlist" in rule or "allowlists" in rule
    ]
    return found


def switch_offs(root: Path, texts: dict[str, str]) -> list[str]:
    owned = [name for name in texts if not name.startswith(UNOWNED)]
    skipped = generated_sources(root, owned)
    found: list[str] = []
    for name in (name for name in owned if name not in skipped):
        lines = list(enumerate(texts[name].splitlines(), 1))
        base = PurePosixPath(name).name
        found += security_hits(root, name, lines, "holds", base in LINE_IGNORES)
        found += pattern_switch_offs(root, name, lines, "holds")
        if base == ".gitleaks.toml":
            found += gitleaks_allowlists(name, texts[name])
    return found


def source_names(root: Path, texts: dict[str, str]) -> list[str]:
    names = [
        name
        for name in texts
        if Path(name).suffix in HASH | SLASH and not name.startswith(".agents/")
    ]
    skipped = generated_sources(root, names)
    return [name for name in names if name not in skipped]


def excuse_markers(root: Path, texts: dict[str, str], names: list[str]) -> list[str]:
    return [
        f"{name}:{number} holds a {hit[0]} marker"
        for name in names
        for number, comment in comment_map(root / name, texts[name], True).items()
        if (hit := MARKER.search(comment))
    ]


def unnamed_markdown(texts: dict[str, str]) -> list[str]:
    named: dict[str, set[str]] = {}
    for name, text in texts.items():
        for hit in MARKDOWN_NAME.findall(text):
            named.setdefault(hit, set()).add(name)
    return [
        f"{name} is named by no other tracked file"
        for name in texts
        if name.endswith(".md")
        and not name.startswith(NEEDS_NO_LINK_FOLDERS)
        and PurePosixPath(name).stem not in NEEDS_NO_LINK
        and not named.get(PurePosixPath(name).name, set()) - {name}
    ]


def validate_whole_project(root: Path) -> None:
    texts = {
        name: (root / name).read_text(errors="replace") for name in tracked_files(root)
    }
    if found := switch_offs(root, texts):
        raise ValueError(switch_off_refusal(found))
    if found := excuse_markers(root, texts, source_names(root, texts)):
        raise ValueError(
            "HE-COMMENT-LINES: A TODO, FIXME, HACK or XXX marker excuses unfinished work: "
            "fix the cause now and delete the comment; never suppress it. "
            + "; ".join(found)
        )
    if found := unnamed_markdown(texts):
        raise ValueError(
            "HE-NAMED-MARKDOWN: A markdown file that no other tracked file names is dead weight: "
            "name it where a reader opens it, or delete it; never suppress it. "
            + "; ".join(found)
        )
