"""Path-safety resolution for Hard Eng PLAN files."""

from __future__ import annotations

import os
from pathlib import Path

from safe_plan_io import SafePlanIOError


def safe_plan_path(repo: Path, value: str | Path) -> Path:
    repo_lexical = Path(os.path.abspath(repo))
    repo = repo_lexical.resolve()
    raw = Path(value)
    joined = raw if raw.is_absolute() else repo_lexical / raw
    lexical = Path(os.path.abspath(joined))
    lexical_relative = None
    for root in (repo_lexical, repo):
        try:
            lexical_relative = lexical.relative_to(root)
            break
        except ValueError:
            continue
    if lexical_relative is None:
        resolved_alias = lexical.resolve(strict=False)
        try:
            alias_relative = resolved_alias.relative_to(repo)
        except ValueError as error:
            raise SafePlanIOError("PLAN lexical path must be inside the repository") from error
        alias_root = lexical
        for _ in alias_relative.parts:
            alias_root = alias_root.parent
        if alias_root.resolve(strict=False) != repo or lexical.relative_to(alias_root).parts != alias_relative.parts:
            raise SafePlanIOError("PLAN lexical path must be inside the repository")
        lexical_relative = alias_relative
    current = repo
    for part in lexical_relative.parts:
        current /= part
        if current.is_symlink():
            raise SafePlanIOError(f"PLAN path contains a symlink: {current}")
    resolved = lexical.resolve(strict=False)
    try:
        resolved.relative_to(repo)
    except ValueError as error:
        raise SafePlanIOError("PLAN must be inside the repository") from error
    return resolved
