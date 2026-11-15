"""The full check judges every tracked file with the patterns of the changed-file checks, old code included."""

import re
import subprocess
import tomllib
from pathlib import Path, PurePosixPath

from comments import (
    COMMENT_HEADER,
    HASH,
    SLASH,
    SWITCH_OFF_HEADER,
    UNOWNED,
    block_hits,
    comment_map,
    pattern_switch_offs,
    security_hits,
)
from gate_config import generated_sources
from project_files import GIT_LISTING

LINE_IGNORES = {".gitleaksignore", ".semgrepignore"}
MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")
ALLOWLIST_LINE = re.compile(r"\s*(\[\[?[\w.-]*allowlists?\]\]?|[\w.-]*allowlists?\s*=)")
DISABLED_LINE = re.compile(r"\s*disabledRules\s*=")
MARKER_HEADER = (
    "HE-COMMENT-LINES: A TODO, FIXME, HACK or XXX marker excuses unfinished work: "
    "fix the cause now and delete the comment; never suppress it."
)
MARKDOWN_HEADER = (
    "HE-NAMED-MARKDOWN: A markdown file that no other tracked file names has no reader: "
    "fix it at the cause, so name it where a reader opens it or delete it; never suppress it."
)
MARKDOWN_NAME = re.compile(r"[\w.+-]+\.md\b")
NEEDS_NO_LINK = {
    "README",
    "AGENTS",
    "AGENTS.OVERRIDE",
    "PRODUCT",
    "DESIGN",
    "SECURITY",
    "CHANGELOG",
    "PLAN",
    "DECISION",
    "SKILL",
    "CONTRIBUTING",
    "CODE_OF_CONDUCT",
    "SUPPORT",
    "GOVERNANCE",
    "MAINTAINERS",
    "CODEOWNERS",
    "LICENSE",
    "NOTICE",
}
NEEDS_NO_LINK_FOLDERS = ("docs/adr/", "docs/requirements.md", ".github/", *UNOWNED)


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


def gitleaks_switch_offs(name: str, text: str) -> list[str]:
    """Allowlist entries and disabled rules of a Gitleaks config; its detection rules stay."""
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    lines = text.splitlines()

    def at(pattern: re.Pattern[str]) -> list[int]:
        return [n for n, line in enumerate(lines, 1) if pattern.match(line)] or [1]

    allowlisted = "allowlist" in config or "allowlists" in config
    allowlisted = allowlisted or any(
        "allowlist" in rule or "allowlists" in rule for rule in config.get("rules", [])
    )
    found = [f"{name}:{n} holds an allowlist" for n in at(ALLOWLIST_LINE)]
    found = found if allowlisted else []
    extend = config.get("extend")
    if isinstance(extend, dict) and (off := extend.get("disabledRules")):
        found += [f"{name}:{n} disables the rules {off!r}" for n in at(DISABLED_LINE)]
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
            found += gitleaks_switch_offs(name, texts[name])
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
        f"{name}:1 is named by no other tracked file"
        for name in texts
        if name.endswith(".md")
        and not name.startswith(NEEDS_NO_LINK_FOLDERS)
        and PurePosixPath(name).stem.upper() not in NEEDS_NO_LINK
        and not named.get(PurePosixPath(name).name, set()) - {name}
    ]


def validate_whole_project(root: Path) -> None:
    texts = {
        name: (root / name).read_text(errors="replace") for name in tracked_files(root)
    }
    sources = source_names(root, texts)
    kinds = [
        (SWITCH_OFF_HEADER, switch_offs(root, texts)),
        (MARKER_HEADER, excuse_markers(root, texts, sources)),
        (
            COMMENT_HEADER,
            [h for n in sources for h in block_hits(n, root / n, texts[n])],
        ),
        (MARKDOWN_HEADER, unnamed_markdown(texts)),
    ]
    blocks = [
        "\n".join([header, *(f"  {hit}" for hit in found)])
        for header, found in kinds
        if found
    ]
    if blocks:
        raise ValueError("\n".join(blocks))
