#!/usr/bin/env python3
"""Reject runtime-specific skill invocation syntax in repository-owned content."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env


def content_files() -> tuple[Path, ...]:
    result = subprocess.run(
        (
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.md",
            "*.py",
            "*.js",
            "*.mjs",
            "*.sh",
            "*.ts",
            "*.tsx",
            "*.yaml",
            "*.yml",
            "*.json",
        ),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=git_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "cannot enumerate repository content")
    return tuple(
        path
        for value in sorted(set(result.stdout.splitlines()))
        if value and (path := ROOT / value).is_file()
    )


def managed_skills() -> frozenset[str]:
    payload = json.loads((ROOT / ".skill-lock.json").read_text(encoding="utf-8"))
    return frozenset(payload.get("skills", {}))


def canonical_skill_names() -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                path.parent.name
                for path in (ROOT / "skills").glob("*/SKILL.md")
            ),
            key=lambda value: (-len(value), value),
        )
    )


def skill_reference_matcher(names: tuple[str, ...]) -> re.Pattern[str]:
    ordered = sorted(names, key=lambda value: (-len(value), value))
    return re.compile(
        rf"\$(?P<name>{'|'.join(re.escape(value) for value in ordered)})(?![a-z0-9-])"
    )


def main() -> int:
    names = canonical_skill_names()
    matcher = skill_reference_matcher(names)
    managed = managed_skills()
    findings: list[str] = []
    for path in content_files():
        relative = path.relative_to(ROOT)
        if (
            len(relative.parts) >= 2
            and relative.parts[0] == "skills"
            and relative.parts[1] in managed
        ):
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            for match in matcher.finditer(line):
                findings.append(
                    f"{relative}:{line_number}: use `{match.group('name')}` without a runtime sigil"
                )
    if findings:
        for finding in findings[:20]:
            print(f"agent-agnostic-content: {finding}")
        if len(findings) > 20:
            print(f"agent-agnostic-content: ... {len(findings) - 20} more")
        print(f"agent-agnostic-content: FAIL | findings={len(findings)}")
        return 1
    print(
        "agent-agnostic-content: PASS"
        f" | skills={len(names)} managed_exclusions={len(managed)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
