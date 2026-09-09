#!/usr/bin/env python3
"""Privacy scan: every tracked text file for home-directory paths, non-allowlisted emails, and a private denylist."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from bounded_run import run_captured
from git_env import git_env, git_output

DENYLIST_ENV = "HARD_ENG_PRIVACY_DENYLIST"
SKIP_NAMES = frozenset({"package-lock.json", ".skill-lock.json"})
HOME_NAME_ALLOW = frozenset({"example", "runner", "user", "<user>", "USER"})
EMAIL_DOMAIN_ALLOW = frozenset(
    {
        "example.com",
        "example.invalid",
        "example.test",
        "example.org",
        "users.noreply.github.com",
        "noreply.github.com",
        "yourdomain.com",
    }
)
UNIX_HOME = re.compile(r"/(?:Users|home)/([^/\s\"'`]+)/")
WINDOWS_HOME = re.compile(r"C:\\Users\\([^\\/:*?\"<>|\r\n]+)\\")
EMAIL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
TEMPLATE_MARKERS = ("secrets.", "vars.")


class PrivacyError(ValueError):
    """The repository or its Git state cannot be scanned for privacy findings."""


def _git(repo: Path, *args: str, timeout: float = 60) -> str:
    return git_output(repo, *args, timeout=timeout, error=PrivacyError)


def git_common_dir(repo: Path) -> Path:
    text = _git(repo, "rev-parse", "--git-common-dir").strip()
    path = Path(text)
    return path if path.is_absolute() else repo / path


def tracked_files(repo: Path) -> list[str]:
    listed = _git(repo, "ls-files", "-z")
    return [item for item in listed.split("\0") if item]


def staged_files(repo: Path) -> set[str]:
    listed = _git(repo, "diff", "--cached", "--name-only", "-z")
    return {item for item in listed.split("\0") if item}


def load_denylist(repo: Path) -> list[str]:
    entries: list[str] = []
    seen: set[str] = set()

    def add(word: str) -> None:
        stripped = word.strip()
        key = stripped.lower()
        if stripped and key not in seen:
            seen.add(key)
            entries.append(stripped)

    deny_path = git_common_dir(repo) / "hard-eng" / "privacy-denylist.txt"
    if deny_path.is_file():
        for line in deny_path.read_text(encoding="utf-8", errors="replace").splitlines():
            add(line.split("#", 1)[0])
    for word in os.environ.get(DENYLIST_ENV, "").split(","):
        add(word)
    return entries


def skip_path(relative: str) -> bool:
    parts = Path(relative).parts
    if not parts:
        return True
    if parts[-1] in SKIP_NAMES:
        return True
    return any(part == "node_modules" or part.startswith(".venv") for part in parts[:-1])


def is_binary(content: bytes) -> bool:
    return b"\0" in content


def read_content(repo: Path, relative: str, staged: set[str], staged_mode: bool) -> bytes | None:
    if staged_mode and relative in staged:
        result = run_captured(["git", "-C", str(repo), "show", f":{relative}"], 60, env=git_env())
        return result.stdout if result.returncode == 0 else None
    try:
        return (repo / relative).read_bytes()
    except OSError:
        return None


def scan_line(relative: str, lineno: int, line: str, denylist_index: dict[str, int]) -> list[str]:
    findings: list[str] = []
    for pattern in (UNIX_HOME, WINDOWS_HOME):
        for match in pattern.finditer(line):
            if match.group(1) not in HOME_NAME_ALLOW:
                findings.append(f"{relative}:{lineno}: home-path")
                break
    for match in EMAIL.finditer(line):
        prefix = line[: match.start()]
        if any(marker in prefix for marker in TEMPLATE_MARKERS):
            continue
        if match.group(1).lower() not in EMAIL_DOMAIN_ALLOW:
            findings.append(f"{relative}:{lineno}: email")
            break
    lowered = line.lower()
    for word, index in denylist_index.items():
        if word.lower() in lowered:
            findings.append(f"{relative}:{lineno}: denylist word #{index}")
    return findings


def scan_repo(repo: Path, staged_mode: bool) -> tuple[list[str], int, int]:
    denylist = load_denylist(repo)
    denylist_index = {word: position + 1 for position, word in enumerate(denylist)}
    staged = staged_files(repo) if staged_mode else set()
    findings: list[str] = []
    scanned = 0
    for relative in tracked_files(repo):
        if skip_path(relative):
            continue
        content = read_content(repo, relative, staged, staged_mode)
        if content is None or is_binary(content):
            continue
        text = content.decode("utf-8", errors="replace")
        scanned += 1
        for lineno, line in enumerate(text.splitlines(), start=1):
            findings.extend(scan_line(relative, lineno, line, denylist_index))
    return findings, scanned, len(denylist)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        findings, scanned, denylist_count = scan_repo(repo, args.staged)
    except PrivacyError as error:
        print(f"privacy: FAIL {error}", file=sys.stderr)
        return 1
    for finding in findings:
        print(finding)
    if findings:
        print(f"privacy: FAIL {len(findings)} finding(s)")
        return 1
    print(f"privacy: PASS files={scanned} denylist={denylist_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
