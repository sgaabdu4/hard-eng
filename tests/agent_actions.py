"""Read the commands, edits and skills each client recorded in its event stream."""

import re
from typing import NamedTuple

SKILL_FILE = re.compile(r"skills/([\w-]+)/SKILL\.md")


class Action(NamedTuple):
    """One command or file edit the client recorded, whether it succeeded, and its output's end."""

    kind: str
    detail: str
    ok: bool
    output: str = ""


def codex_actions(found: list[dict[str, object]]) -> list[Action]:
    actions: list[Action] = []
    for event in found:
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        if item.get("type") == "command_execution":
            ok = item.get("exit_code") == 0
            output = str(item.get("aggregated_output") or "")[-2000:]
            actions.append(Action("command", str(item.get("command")), ok, output))
        elif item.get("type") == "file_change":
            changes = item.get("changes")
            ok = item.get("status") == "completed"
            actions += [
                Action("edit", str(change.get("path")), ok)
                for change in (changes if isinstance(changes, list) else [])
                if isinstance(change, dict)
            ]
    return actions


def claude_actions(found: list[dict[str, object]]) -> list[Action]:
    parts = [
        part
        for event in found
        if isinstance(message := event.get("message"), dict)
        and isinstance(content := message.get("content"), list)
        for part in content
        if isinstance(part, dict)
    ]
    results = {
        part.get("tool_use_id"): part
        for part in parts
        if part.get("type") == "tool_result"
    }
    actions: list[Action] = []
    for part in parts:
        arguments = part.get("input")
        arguments = arguments if isinstance(arguments, dict) else {}
        result = results.get(part.get("id"), {})
        ok = bool(result) and not result.get("is_error")
        if part.get("type") != "tool_use":
            continue
        if part.get("name") == "Bash":
            output = result_text(result.get("content"))
            actions.append(Action("command", str(arguments.get("command")), ok, output))
        elif part.get("name") in {"Edit", "Write", "MultiEdit", "NotebookEdit"}:
            path = arguments.get("file_path", arguments.get("notebook_path"))
            actions.append(Action("edit", str(path), ok))
        elif part.get("name") == "Skill":
            actions.append(Action("skill", str(arguments.get("skill")), ok))
        elif part.get("name") == "Read" and (
            skill := SKILL_FILE.search(str(arguments.get("file_path")))
        ):
            actions.append(Action("skill", skill.group(1), ok))
    return actions


def result_text(content: object) -> str:
    if isinstance(content, list):
        content = "\n".join(
            str(p.get("text", "")) for p in content if isinstance(p, dict)
        )
    return str(content or "")[-2000:]


def loaded_skills(actions: list[Action]) -> set[str]:
    """Skills the client loaded: Claude's Skill tool, or Codex reading a SKILL.md."""
    found = {
        action.detail for action in actions if action.ok and action.kind == "skill"
    }
    for action in actions:
        if action.ok and action.kind == "command":
            found.update(SKILL_FILE.findall(action.detail))
    return found
