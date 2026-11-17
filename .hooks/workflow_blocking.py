"""The Hard Eng workflow must block: its check lines are the ones setup generates, and no line turns a failure into a pass."""

import re
from pathlib import PurePosixPath

TOOLS = r'(?:bun x --package="\$MISE_PACKAGE" mise|"\$\{mise_command\[@\]\}")'
GENERATED = re.compile(
    r"^(?:[A-Z_]+=\S+ )*"
    rf"(?:{TOOLS} --no-config exec (?:[\w@.-]+ |\"\$\{{tools\[@\]\}}\" )+-- uv run --no-project --with pyyaml python"
    r"|python3(?: -B)?)"
    r' \.hooks/hard-eng\.py (?:check|impact) --base "\$BASE_SHA"'
    r"(?: --(?:only|skip)-language \w+)?"
    r'(?: --shard (?:rest|merge|"\$SHARD"))?'
    r'(?: >> "\$GITHUB_OUTPUT" \|\| (?:echo docs_only=false|printf \'runner=[\w.-]+\\napple=(?:true|false)\\n\') >> "\$GITHUB_OUTPUT")?$'
)
CHECK_LINE = re.compile(r"\.hooks/hard-eng\.py")
BROKEN = re.compile(
    r"continue-on-error\s*:\s*(?!(?:false|\$\{\{\s*false\s*\}\})\s*(?:#.*)?$)\S"
    r"|^\s*(?:-\s*)?shell\s*:"
    r"|^\s*(?:-\s*)?if\s*:\s*(?:\$\{\{\s*)?(?:false|0|''|\"\")(?:\s*\}\})?\s*$"
    r"|\bset\s+\+e\b|\btrap\s|\bexit\s+0\b"
)


def hard_eng_workflow(name: str) -> bool:
    path = PurePosixPath(name)
    return path.name == "hard-eng.yml" and ".github" in path.parts


def blocking_hit(text: str) -> str | None:
    """What a line of the Hard Eng workflow does to let a failing check pass: a line that calls the hooks but is not a generated check line, or a line that ignores a failure."""
    line = re.sub(r"^\s*(?:-\s*)?(?:run:\s*)?", "", text.rstrip()).strip()
    if CHECK_LINE.search(line) and not GENERATED.fullmatch(re.sub(r"\s+", " ", line)):
        return line
    found = BROKEN.search(text)
    return found[0] if found else None
