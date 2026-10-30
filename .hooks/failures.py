"""Repeat counts: failed checks per checkout, failed tool calls per session."""

import hashlib
import json
import re
import tempfile
from pathlib import Path

from gate_config import JsonObject, JsonValue

NOT_A_MISTAKE = re.compile(
    r"(?i)doesn't want to (?:proceed|take this action)|tool use was rejected|"
    r"permission for this action was denied|denied by|hook error|interrupted|timed out|timeout"
)
ERROR_NOISE = (
    (r"(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>"),
    (r"(?i)\b[0-9a-f]{7,}\b", "<hex>"),
    (r"\d+(?:\.\d+)?", "#"),
)


def repeat_note(root: Path, output: str) -> str:
    """Counts each failure by its failing lines, else all lines, with numbers masked; a second sighting is a repeat."""
    masked = [
        re.sub(r"\d+(?:\.\d+)?", "#", line.strip())
        for line in output.splitlines()
        if line.strip()
    ]
    if not masked:
        return ""
    lines = {line for line in masked if re.search(r"(?i)fail|error", line)} or set(
        masked
    )
    key = hashlib.sha256("\n".join(sorted(lines)).encode()).hexdigest()[:16]
    path = root / ".hard-eng/failures.json"
    try:
        loaded: JsonValue = json.loads(path.read_text())
    except (OSError, ValueError):
        loaded = None
    seen: dict[str, int] = (
        {name: value for name, value in loaded.items() if isinstance(value, int)}
        if isinstance(loaded, dict)
        else {}
    )
    count = seen.pop(key, 0) + 1
    seen[key] = count
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(dict(list(seen.items())[-100:])))
    if count < 2:
        return ""
    return (
        f"\n\nRepeat failure: seen {count} times in this checkout. Before another similar try, "
        "follow .agents/skills/he-learn/SKILL.md: find the shared cause and every place it occurs, "
        "then record them on the plan's Same cause line."
    )


def failure_context(state: Path | None, payload: JsonObject) -> str:
    """Warn from the third sighting of one tool error in a session; refusals and bare exit codes never count."""
    error = payload.get("error")
    if (
        payload.get("is_interrupt") is True
        or not isinstance(error, str)
        or NOT_A_MISTAKE.search(error)
        or not re.sub(r"(?i)exit code|[\d\s]", "", error)
        or state is None
        or not state.is_file()
    ):
        return ""
    for pattern, mark in ERROR_NOISE:
        error = re.sub(pattern, mark, error)
    sighting = f"{payload.get('tool_name')}\0{payload.get('agent_id')}\0{error.strip()}"
    key = hashlib.sha256(sighting.encode()).hexdigest()[:16]
    try:
        saved: JsonValue = json.loads(state.read_text())
    except (OSError, ValueError):
        return ""
    if not isinstance(saved, dict):
        return ""
    seen = saved.get("failures")
    seen = seen if isinstance(seen, dict) else {}
    earlier = seen.get(key)
    count = (earlier if isinstance(earlier, int) else 0) + 1
    # Parallel failed calls share this file; a whole-file replace never leaves it half written.
    with tempfile.NamedTemporaryFile(
        "w", dir=state.parent, suffix=".tmp", delete=False
    ) as out:
        json.dump({**saved, "failures": {**seen, key: count}}, out)
    Path(out.name).replace(state)
    if count < 3:
        return ""
    return (
        f"Same tool error {count} times this session. Stop retrying it: change approach or ask the user. "
        "Repeat cause → .agents/skills/he-learn/SKILL.md."
    )
