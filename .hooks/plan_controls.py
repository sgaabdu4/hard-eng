"""The `Controls:` line of a visible-change plan: each control names the shared part it reuses, or a new part with a mockup that `look` has opened."""

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

REUSE = re.compile(r".+ — reuses `([^`\s]+)`")
NEW = re.compile(r".+ — new `[^`\s]+`( — mockup !\[[^\]\n]*\]\(([^)\s]+)\))?")
NONE = re.compile(r"None — \S.*")


def plan_root(plan: Path) -> Path | None:
    for folder in plan.resolve().parents:
        if (folder / ".git").exists():
            return folder
    return None


def looked_hashes(root: Path) -> set[str]:
    """The hashes of the images that a `look` record of this checkout says were opened."""
    done = subprocess.run(
        ["git", "rev-parse", "--git-path", "hard-eng/look"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    found: set[str] = set()
    for record in (root / done.stdout.strip()).glob("*.json") if done.stdout else []:
        try:
            images = json.loads(record.read_text())["images"]
            found.update(i["sha256"] for i in images if i["read"] is True)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return found


def mockup_problem(entry: str, mockup: str, root: Path) -> str | None:
    image = root / mockup
    if mockup.startswith(("http://", "https://")) or not image.is_file():
        return f"Controls: the mockup in `{entry}` must be an image file in the repository, and `{mockup}` is not"
    if os.environ.get("GITHUB_ACTIONS"):
        return None
    if hashlib.sha256(image.read_bytes()).hexdigest() not in looked_hashes(root):
        return f"Controls: the mockup `{mockup}` has no `look` record; run `python3 .hooks/hard-eng.py look {mockup}`"
    return None


def entry_problem(entry: str, root: Path | None) -> str | None:
    if reused := REUSE.fullmatch(entry):
        if root is not None and not (root / reused[1]).exists():
            return f"Controls: the shared part `{reused[1]}` does not exist in the repository"
        return None
    new = NEW.fullmatch(entry)
    if new is None:
        return f"Controls: `{entry}` needs `— reuses `<repo path>`` or `— new `<repo path>` — mockup ![..](..)``"
    if new[2] is None:
        return f"Controls: the new shared part in `{entry}` needs a mockup image"
    return None if root is None else mockup_problem(entry, new[2], root)


def controls_problem(content: str, root: Path | None) -> str | None:
    found = re.findall(r"(?m)^Controls: *(.*)$", content)
    if len(found) != 1 or not found[0].strip():
        return "ux_reference needs one `Controls:` line: each changed or new control with the shared part it reuses, or `None — reason`"
    line = found[0].strip()
    if NONE.fullmatch(line):
        return None
    problems = (entry_problem(entry, root) for entry in line.split("; "))
    return next((problem for problem in problems if problem), None)


def judged_controls(
    content: str, root: Path | None, age: Callable[[], bool] | None
) -> None:
    """A Complete plan untouched since the last Hard Eng update may predate the Controls line."""
    problem = controls_problem(content, root)
    if problem and ("\nControls:" in f"\n{content}" or age is None or age()):
        raise ValueError(problem)
