"""Keep links, anchors and Mermaid routes in distributed skills resolvable."""

import os
import re
from collections.abc import Iterator
from pathlib import Path

from conftest import SOURCE

FENCE = re.compile(r"^\s*(?:`{3,}|~{3,})\s*([\w-]*)")
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
INLINE_CODE = re.compile(r"`[^`]*`")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
CLICK = re.compile(r'^\s*click\s+\S+\s+(?:href\s+)?"([^"]+)"')
# A node label that is only a path, such as P[../he-plan/SKILL.md], routes like a click.
LABEL = re.compile(r"[\[({]([^\s\[\](){}\"]*(?:/|\.md)[^\s\[\](){}\"]*)[\])}]")
EXTERNAL = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def lines(text: str) -> Iterator[tuple[int, str, str | None]]:
    """Yield each line with its fence language, or None outside a fence."""
    fence: str | None = None
    for number, line in enumerate(text.splitlines(), 1):
        match = FENCE.match(line)
        if match:
            fence = (match.group(1) or "text") if fence is None else None
        else:
            yield number, line, fence


def targets(text: str) -> Iterator[tuple[int, str]]:
    """Real routes: prose links and Mermaid routes; other fences are examples."""
    for number, line, fence in lines(text):
        found: list[str] = []
        if fence == "mermaid":
            click = CLICK.match(line)
            found = [click.group(1)] if click else LABEL.findall(line)
        elif fence is None:
            found = LINK.findall(INLINE_CODE.sub("", line))
        for target in found:
            if not EXTERNAL.match(target):
                yield number, target


def anchors(text: str) -> set[str]:
    """GitHub heading slugs, including the -N suffix of repeated headings."""
    slugs: set[str] = set()
    seen: dict[str, int] = {}
    for _, line, fence in lines(text):
        heading = HEADING.match(line) if fence is None else None
        if heading:
            words = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading.group(1).lower())
            slug = re.sub(r"[^\w\- ]", "", words).replace(" ", "-")
            count = seen.get(slug, 0)
            seen[slug] = count + 1
            slugs.add(f"{slug}-{count}" if count else slug)
    return slugs


def skill_paths(root: Path) -> set[str]:
    """Case-exact installed paths; symlinked skills keep their .agents/skills path."""
    found: set[str] = set()
    for directory, names, files in os.walk(root / ".agents/skills", followlinks=True):
        relative = Path(directory).relative_to(root)
        found.add(relative.as_posix())
        found.update((relative / name).as_posix() for name in names + files)
    return found


def link_failures(root: Path) -> list[str]:
    failures = [
        f"{skill.name}: SKILL.md is missing; is its submodule initialized?"
        for skill in sorted((root / ".agents/skills").iterdir())
        if not (skill / "SKILL.md").is_file()
    ]
    paths = skill_paths(root)
    for source in sorted(name for name in paths if name.endswith(".md")):
        text = (root / source).read_text()
        for number, target in targets(text):
            location, _, fragment = target.partition("#")
            # Resolve lexically so ../ from a symlinked skill stays under .agents/skills.
            resolved = os.path.normpath(Path(source).parent / location)
            where = f"{source}:{number} {target}"
            if location and resolved not in paths:
                failures.append(f"{where}: missing file")
            elif fragment and (not location or resolved.endswith(".md")):
                page = text if not location else (root / resolved).read_text()
                if fragment not in anchors(page):
                    failures.append(f"{where}: missing section")
    return failures


def skill(root: Path, name: str, text: str) -> None:
    (root / name).mkdir(parents=True)
    (root / name / "SKILL.md").write_text(text)


def test_distributed_skill_links_resolve() -> None:
    assert link_failures(SOURCE) == []


def test_broken_links_fail_and_valid_equivalents_pass(tmp_path: Path) -> None:
    skills = tmp_path / ".agents/skills"
    source = tmp_path / ".agents/skill-sources/canonical/skills"
    skill(skills, "he", "# Plan checks\n\n## Plan checks\n")
    skill(skills, "local", "# Local\n")
    (skills / "local/references").mkdir()
    (skills / "local/references/guide.md").write_text("# Guide\n")
    skill(
        source,
        "canonical",
        "# Canonical\n\n"
        "[ok](../he/SKILL.md#plan-checks-1) [ok](#canonical) [web](https://x.test/) [here](#nowhere)\n"
        "[gone](../he/MISSING.md) [anchor](../he/SKILL.md#absent) [case](../HE/SKILL.md)\n"
        "`[code](absent.md)`\n\n"
        "```text\n[example](generated/PLAN.md)\n```\n\n"
        "```mermaid\nflowchart LR\n"
        "  A --> B[../local/references/guide.md]\n"
        "  A --> C[../local/references/lost.md]\n"
        "  A --> D[Compact PLAN.md]\n"
        '  click B "../local/references/guide.md#guide"\n'
        '  click C "../local/references/guide.md#lost"\n'
        "```\n",
    )
    (skills / "canonical").symlink_to(source / "canonical", target_is_directory=True)
    (skills / "uninitialized").symlink_to(source / "absent", target_is_directory=True)

    assert link_failures(tmp_path) == [
        "uninitialized: SKILL.md is missing; is its submodule initialized?",
        ".agents/skills/canonical/SKILL.md:3 #nowhere: missing section",
        ".agents/skills/canonical/SKILL.md:4 ../he/MISSING.md: missing file",
        ".agents/skills/canonical/SKILL.md:4 ../he/SKILL.md#absent: missing section",
        ".agents/skills/canonical/SKILL.md:4 ../HE/SKILL.md: missing file",
        ".agents/skills/canonical/SKILL.md:14 ../local/references/lost.md: missing file",
        (
            ".agents/skills/canonical/SKILL.md:17 ../local/references/guide.md#lost: "
            "missing section"
        ),
    ]
